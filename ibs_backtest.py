# ibs_backtest.py - Strategy 3: IBS mean reversion on the S&P 500
#
# Based on "151 Trading Strategies" section 4.4 and Pagonidis (2014),
# "The IBS Effect: Mean Reversion in Equity ETFs".
#
#   IBS = (Close - Low) / (High - Low)     0 = closed at the low, 1 = at the high
#
# Rules (fixed 3 Nov 2026 before running on real data - see trials-log.md):
#   Entry: at the close, if flat and IBS < 0.2           -> buy at that close
#   Exit:  at the close, if IBS > 0.8 OR held 5 days       -> sell at that close
#   No price stop-loss. Whole sleeve in or out. Cash earns the T-bill rate.
#   Cost 0.05% per side (London-listed GBP ETF spread; no FX fee).
#
# Train: Feb 1993 - May 2013 (the paper's sample ended May 2013)
# Test:  Jun 2013 onwards = genuinely after publication
#
# Run from Terminal (in ~/Documents/Trading/portfolio):
#   python3 ibs_backtest.py --download     (first run)
#   python3 ibs_backtest.py                (later runs use saved prices)

import os
import sys
import numpy as np
import pandas as pd

# ---------------- settings (fixed in advance - do not tune) ----------------
TICKER = "SPY"
RATE_TICKER = "^IRX"          # 13-week T-bill yield, for cash returns
LIVE_CHECK_TICKER = "VUSA.L"  # London-listed S&P 500 ETF (information only)
START_DATE = "1993-01-01"
PRICES_FILE = "ibs_prices.csv"
LIVE_FILE = "ibs_prices_vusa.csv"

ENTRY_IBS = 0.2
EXIT_IBS = 0.8
MAX_HOLD_DAYS = 5
COST_PER_SIDE = 0.0005        # 0.05%
COST_GRID = [0.0, 0.0005, 0.001, 0.002]
TREND_FILTER_DAYS = 200       # variant B only

TRAIN_END = "2013-05-31"
TEST_START = "2013-06-01"


# ---------------- data ----------------
def _download_ohlc(ticker, start):
    import yfinance as yf
    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df[~df.index.duplicated(keep="last")].sort_index().dropna()
    return df


def load_data(refresh):
    if refresh or not os.path.exists(PRICES_FILE):
        print("Downloading " + TICKER + " and T-bill rates ...")
        px = _download_ohlc(TICKER, START_DATE)
        if px is None:
            sys.exit("Download failed - check internet and try again.")
        rate = _download_ohlc(RATE_TICKER, START_DATE)
        if rate is None:
            print("WARNING: T-bill download failed - cash will earn 0%.")
            px["RatePct"] = 0.0
        else:
            px["RatePct"] = rate["Close"].reindex(px.index).ffill().fillna(0.0)
        bad = px[(px["High"] < px["Low"]) | (px["Close"] > px["High"] * 1.0001)
                 | (px["Close"] < px["Low"] * 0.9999)]
        if len(bad):
            print("WARNING: %d rows with inconsistent High/Low/Close" % len(bad))
        px.to_csv(PRICES_FILE, float_format="%.4f")
        print("Saved " + PRICES_FILE)
        live = _download_ohlc(LIVE_CHECK_TICKER, "2012-01-01")
        if live is not None:
            live["RatePct"] = px["RatePct"].reindex(live.index).ffill().fillna(0.0)
            live.to_csv(LIVE_FILE, float_format="%.4f")
            print("Saved " + LIVE_FILE)
    else:
        px = pd.read_csv(PRICES_FILE, index_col=0, parse_dates=True)
        print("Loaded " + PRICES_FILE + " (use --download to refresh)")
    return px


# ---------------- simulation ----------------
def simulate(px, cost=COST_PER_SIDE, entry="close", trend_filter=False):
    """Day-by-day simulation. Returns (daily returns, trades list, in-market flags).

    entry="close": buy at the signal day's close (the paper's method).
    entry="open":  buy at the NEXT day's open (fill-timing test).
    Exits are always at a close.
    """
    o = px["Open"].to_numpy()
    h = px["High"].to_numpy()
    l = px["Low"].to_numpy()
    c = px["Close"].to_numpy()
    rng = h - l
    ibs = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), np.nan)
    sma = pd.Series(c).rolling(TREND_FILTER_DAYS).mean().to_numpy()
    cash = (1.0 + px["RatePct"].to_numpy() / 100.0) ** (1.0 / 252) - 1.0

    n = len(c)
    ret = np.zeros(n)
    inmkt = np.zeros(n, dtype=bool)
    trades = []
    holding = False
    pending = False      # open-entry order waiting for next open
    held = 0
    t_ret = 1.0
    t_start = None

    for i in range(1, n):
        # 1. today's return from yesterday's position
        if holding:
            r = c[i] / c[i - 1] - 1.0
            ret[i] = r
            t_ret *= 1.0 + r
            held += 1
            inmkt[i] = True
        elif pending:
            r = c[i] / o[i] - 1.0          # bought at today's open
            ret[i] = (1.0 - cost) * (1.0 + r) - 1.0
            t_ret = (1.0 - cost) * (1.0 + r)
            holding, pending, held = True, False, 1
            t_start = px.index[i]
            inmkt[i] = True
        else:
            ret[i] = cash[i]

        # 2. decisions at today's close
        if holding:
            if (not np.isnan(ibs[i]) and ibs[i] > EXIT_IBS) or held >= MAX_HOLD_DAYS:
                ret[i] = (1.0 + ret[i]) * (1.0 - cost) - 1.0
                t_ret *= 1.0 - cost
                trades.append((t_start, px.index[i], held, t_ret - 1.0))
                holding, held = False, 0
        elif not pending:
            signal = not np.isnan(ibs[i]) and ibs[i] < ENTRY_IBS
            if signal and trend_filter:
                signal = (not np.isnan(sma[i])) and c[i] > sma[i]
            if signal:
                if entry == "close":
                    ret[i] = (1.0 + ret[i]) * (1.0 - cost) - 1.0
                    holding, held, t_ret = True, 0, 1.0 - cost
                    t_start = px.index[i]
                else:
                    pending = True

    daily = pd.Series(ret, index=px.index)
    tr = pd.DataFrame(trades, columns=["entry", "exit", "days", "ret"])
    return daily, tr, pd.Series(inmkt, index=px.index)


# ---------------- statistics ----------------
def summary(daily, cash_daily, trades, inmkt, a, b):
    r = daily.loc[a:b]
    c = cash_daily.loc[a:b]
    eq = (1.0 + r).cumprod()
    years = (r.index[-1] - r.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1.0 / years) - 1.0
    ex = r - c
    sharpe = ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1.0).min()
    t = trades[(trades["entry"] >= pd.Timestamp(a)) & (trades["exit"] <= pd.Timestamp(b))]
    n = len(t)
    mean_t = t["ret"].mean() if n else np.nan
    tstat = mean_t / (t["ret"].std() / np.sqrt(n)) if n > 2 and t["ret"].std() > 0 else np.nan
    yearly = eq.groupby(eq.index.year).last() / eq.groupby(eq.index.year).first() - 1.0
    cash_eq = (1.0 + c).cumprod()
    cash_y = cash_eq.groupby(cash_eq.index.year).last() / cash_eq.groupby(cash_eq.index.year).first() - 1.0
    return {
        "CAGR": cagr, "Vol": r.std() * np.sqrt(252), "Sharpe": sharpe, "MaxDD": dd,
        "Trades/yr": n / years, "Avg trade": mean_t,
        "Win rate": (t["ret"] > 0).mean() if n else np.nan,
        "Trade t-stat": tstat, "In market": inmkt.loc[a:b].mean(),
        "Yrs beat cash": (yearly > cash_y.reindex(yearly.index)).mean(),
        "_yearly": yearly,
    }


def pct(x, d=1):
    return ("%." + str(d) + "f%%") % (100 * x)


def show(rows):
    cols = ["CAGR", "Vol", "Sharpe", "MaxDD", "Trades/yr", "Avg trade",
            "Win rate", "Trade t-stat", "In market", "Yrs beat cash"]
    out = {}
    for name, s in rows.items():
        out[name] = {
            "CAGR": pct(s["CAGR"]), "Vol": pct(s["Vol"]), "Sharpe": "%.2f" % s["Sharpe"],
            "MaxDD": pct(s["MaxDD"]),
            "Trades/yr": "%.0f" % s["Trades/yr"] if not np.isnan(s["Trades/yr"]) else "-",
            "Avg trade": pct(s["Avg trade"], 2) if not np.isnan(s["Avg trade"]) else "-",
            "Win rate": pct(s["Win rate"], 0) if not np.isnan(s["Win rate"]) else "-",
            "Trade t-stat": "%.1f" % s["Trade t-stat"] if not np.isnan(s["Trade t-stat"]) else "-",
            "In market": pct(s["In market"], 0),
            "Yrs beat cash": pct(s["Yrs beat cash"], 0),
        }
    return pd.DataFrame(out).T[cols].to_string()


# ---------------- main ----------------
def main():
    px = load_data("--download" in sys.argv)
    cash = (1.0 + px["RatePct"] / 100.0) ** (1.0 / 252) - 1.0
    first = px.index[1]
    last = px.index[-1]
    periods = {
        "FULL %s to %s" % (first.strftime("%Y-%m"), last.strftime("%Y-%m")): (first, last),
        "TRAIN to May 2013 (paper's sample)": (first, pd.Timestamp(TRAIN_END)),
        "TEST Jun 2013 onwards (after publication)": (pd.Timestamp(TEST_START), last),
    }

    base_d, base_t, base_m = simulate(px)
    open_d, open_t, open_m = simulate(px, entry="open")
    filt_d, filt_t, filt_m = simulate(px, trend_filter=True)
    spy_d = px["Close"].pct_change().fillna(0.0)
    no_trades = pd.DataFrame(columns=["entry", "exit", "days", "ret"])
    all_in = pd.Series(True, index=px.index)

    print("")
    print("=" * 78)
    print("STRATEGY 3: IBS MEAN REVERSION ON %s - BACKTEST - TRIAL 1" % TICKER)
    print("Entry IBS < %.1f at close | exit IBS > %.1f or %d days | cost %.2f%% per side"
          % (ENTRY_IBS, EXIT_IBS, MAX_HOLD_DAYS, 100 * COST_PER_SIDE))
    print("=" * 78)

    test_rows = {}
    train_rows = {}
    for pname, (a, b) in periods.items():
        rows = {
            "A. IBS (close entry)": summary(base_d, cash, base_t, base_m, a, b),
            "B. IBS + 200-day filter": summary(filt_d, cash, filt_t, filt_m, a, b),
            "C. IBS (next-open entry)": summary(open_d, cash, open_t, open_m, a, b),
            "SPY buy and hold": summary(spy_d, cash, no_trades, all_in, a, b),
        }
        if pname.startswith("TEST"):
            test_rows = rows
        if pname.startswith("TRAIN"):
            train_rows = rows
        print("")
        print(pname)
        print(show(rows))

    a, b = pd.Timestamp(TEST_START), last
    print("")
    print("COST SENSITIVITY (test period, A. close entry)")
    cost_res = {}
    for cst in COST_GRID:
        d, t, m = simulate(px, cost=cst)
        s = summary(d, cash, t, m, a, b)
        cost_res[cst] = s
        print("  %.2f%% per side: CAGR %s, Sharpe %.2f, avg trade %s"
              % (100 * cst, pct(s["CAGR"]), s["Sharpe"], pct(s["Avg trade"], 2)))

    print("")
    print("YEARLY RETURNS (test period)")
    yr = pd.DataFrame({k: v["_yearly"] for k, v in test_rows.items()})
    print(yr.apply(lambda col: col.map(pct)).to_string())

    # Correlation with SPY on days the strategy is invested vs overall
    corr = base_d.loc[a:b].corr(spy_d.loc[a:b])
    print("")
    print("Daily correlation with SPY (test, A): %.2f" % corr)

    # Pre-registered go-live checks (fixed before seeing results)
    tA, trA = test_rows["A. IBS (close entry)"], train_rows["A. IBS (close entry)"]
    tC = test_rows["C. IBS (next-open entry)"]
    tS = test_rows["SPY buy and hold"]
    checks = [
        ("1. Test: average trade significant (t-stat above 2)", tA["Trade t-stat"] > 2.0),
        ("2. Test: still profitable at double costs (0.10% per side)",
         cost_res[0.001]["Avg trade"] > 0 and cost_res[0.001]["CAGR"] > 0),
        ("3. Test: next-open entry keeps at least half the average trade",
         tA["Avg trade"] > 0 and tC["Avg trade"] >= 0.5 * tA["Avg trade"]),
        ("4. Average trade positive in BOTH train and test",
         trA["Avg trade"] > 0 and tA["Avg trade"] > 0),
        ("5. Test: max drawdown smaller than SPY's", tA["MaxDD"] > tS["MaxDD"]),
    ]
    print("")
    print("GO-LIVE CHECKS (fixed before seeing results)")
    for label, ok in checks:
        print("  " + ("PASS  " if ok else "FAIL  ") + label)
    tB = test_rows["B. IBS + 200-day filter"]
    adopt = tB["Sharpe"] > tA["Sharpe"]
    print("  200-day filter (variant B): %s (test Sharpe %.2f vs %.2f)"
          % ("ADOPT" if adopt else "do not adopt", tB["Sharpe"], tA["Sharpe"]))

    # Information only: same rules on the London-listed ETF we would trade
    if os.path.exists(LIVE_FILE):
        lv = pd.read_csv(LIVE_FILE, index_col=0, parse_dates=True)
        if len(lv) > 300:
            lcash = (1.0 + lv["RatePct"] / 100.0) ** (1.0 / 252) - 1.0
            d, t, m = simulate(lv)
            s = summary(d, lcash, t, m, lv.index[1], lv.index[-1])
            print("")
            print("INFO: same rules on %s (%s to %s, London hours, GBP):"
                  % (LIVE_CHECK_TICKER, lv.index[0].strftime("%Y-%m"), lv.index[-1].strftime("%Y-%m")))
            print("  CAGR %s, Sharpe %.2f, %d trades/yr, avg trade %s, t-stat %.1f"
                  % (pct(s["CAGR"]), s["Sharpe"], s["Trades/yr"], pct(s["Avg trade"], 2), s["Trade t-stat"]))

    base_t.to_csv("ibs_trades.csv", index=False)
    print("")
    print("Saved ibs_trades.csv")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 5))
        for name, d in [("A. IBS (close)", base_d), ("B. IBS + 200d filter", filt_d),
                        ("C. IBS (next open)", open_d), ("SPY", spy_d)]:
            eq = (1.0 + d).cumprod()
            ax.plot(eq.index, eq.values, label=name, linewidth=1.3 if name.startswith("A") else 1.0)
        ax.set_yscale("log")
        ax.axvline(pd.Timestamp(TEST_START), color="grey", linestyle="--", linewidth=0.8)
        ax.set_title("IBS mean reversion vs SPY (dashed line = paper's sample ends)")
        ax.legend(loc="upper left")
        fig.tight_layout()
        fig.savefig("ibs_equity.png", dpi=120)
        print("Saved ibs_equity.png")
    except ImportError:
        print("Chart skipped - install matplotlib")


if __name__ == "__main__":
    main()
