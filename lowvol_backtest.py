# lowvol_backtest.py - Strategy 2: low-volatility US large caps
#
# Based on "151 Trading Strategies" section 3.4, Robeco's Conservative Formula
# (Blitz & van Vliet 2018) and MSCI Minimum Volatility constraints.
#
# Rules (fixed 3 Nov 2026 before running on real data - see trials-log.md):
#   1. Each quarter-end (Mar/Jun/Sep/Dec), rank eligible stocks by the
#      volatility of their last 36 monthly returns (lowest first).
#   2. Hold the 25 lowest, equal weight, at most 6 per sector (about 25%).
#   3. Buffer: a current holding stays while its rank is within the top 35.
#   4. Trade 1 trading day after the signal.
#   5. Cost 0.25% per side (0.10% spread + 0.15% Trading 212 FX fee).
#
# Key benchmark: equal-weight portfolio of ALL eligible stocks (same
# universe, same survivorship bias, same costs). SPY shown for reference.
#
# WARNING: the universe is today's large caps (survivorship bias). Results
# are inflated for every portfolio here; compare them with each other.
#
# Run from Terminal (data_loader.py must be in the same folder):
#   python3 lowvol_backtest.py --download     (first run)
#   python3 lowvol_backtest.py                (later runs use saved prices)

import os
import sys
import numpy as np
import pandas as pd

from data_loader import download_prices, clean_prices, UNIVERSE

# ---------------- settings (fixed in advance - do not tune) ----------------
START_DATE = "2004-01-01"
PRICES_FILE = "lowvol_prices.csv"
BENCH = "SPY"
RATE_TICKER = "^IRX"

N_HOLD = 25
SECTOR_CAP = 6
BUFFER_RANK = 35
VOL_MONTHS = 36
COST_PER_SIDE = 0.0025
EXEC_LAG_DAYS = 1
MIN_ELIGIBLE = 50
TRAIN_END = "2016-12-31"

# Neighbours for check 4: (name, n_hold, vol_months, sector_cap)
NEIGHBOURS = [
    ("15 stocks", 15, 36, 4),
    ("35 stocks", 35, 36, 9),
    ("12-month vol", 25, 12, 6),
    ("No sector cap", 25, 36, 25),
]

CRISES = {
    "GFC 2007-09": ("2007-10-09", "2009-03-09"),
    "COVID 2020": ("2020-02-19", "2020-03-23"),
    "2022 rate shock": ("2022-01-03", "2022-12-30"),
}

# Current GICS sectors (simplification: held fixed through history)
SECTOR = {
    "AAPL": "Tech", "ABBV": "Health", "ABT": "Health", "ACN": "Tech", "ADBE": "Tech",
    "AIG": "Fin", "AMD": "Tech", "AMGN": "Health", "AMT": "RealEst", "AMZN": "Disc",
    "AVGO": "Tech", "AXP": "Fin", "BA": "Indust", "BAC": "Fin", "BK": "Fin",
    "BKNG": "Disc", "BLK": "Fin", "BMY": "Health", "BRK-B": "Fin", "C": "Fin",
    "CAT": "Indust", "CHTR": "Comm", "CL": "Staples", "CMCSA": "Comm", "COF": "Fin",
    "COP": "Energy", "COST": "Staples", "CRM": "Tech", "CSCO": "Tech", "CVS": "Health",
    "CVX": "Energy", "DE": "Indust", "DHR": "Health", "DIS": "Comm", "DUK": "Util",
    "EMR": "Indust", "F": "Disc", "FDX": "Indust", "GD": "Indust", "GE": "Indust",
    "GILD": "Health", "GM": "Disc", "GOOGL": "Comm", "GS": "Fin", "HD": "Disc",
    "HON": "Indust", "IBM": "Tech", "INTC": "Tech", "INTU": "Tech", "ISRG": "Health",
    "JNJ": "Health", "JPM": "Fin", "KO": "Staples", "LIN": "Materials", "LLY": "Health",
    "LMT": "Indust", "LOW": "Disc", "MA": "Fin", "MCD": "Disc", "MDLZ": "Staples",
    "MDT": "Health", "MET": "Fin", "META": "Comm", "MMM": "Indust", "MO": "Staples",
    "MRK": "Health", "MS": "Fin", "MSFT": "Tech", "NEE": "Util", "NFLX": "Comm",
    "NKE": "Disc", "NOW": "Tech", "NVDA": "Tech", "ORCL": "Tech", "PEP": "Staples",
    "PFE": "Health", "PG": "Staples", "PLTR": "Tech", "PM": "Staples", "PYPL": "Fin",
    "QCOM": "Tech", "RTX": "Indust", "SBUX": "Disc", "SCHW": "Fin", "SO": "Util",
    "SPG": "RealEst", "T": "Comm", "TGT": "Staples", "TMO": "Health", "TMUS": "Comm",
    "TSLA": "Disc", "TXN": "Tech", "UBER": "Indust", "UNH": "Health", "UNP": "Indust",
    "UPS": "Indust", "USB": "Fin", "V": "Fin", "VZ": "Comm", "WFC": "Fin",
    "WMT": "Staples", "XOM": "Energy",
}


# ---------------- data ----------------
def load_data(refresh):
    if refresh or not os.path.exists(PRICES_FILE):
        prices = download_prices(UNIVERSE + [BENCH], START_DATE)
        prices, report = clean_prices(prices)
        if report["failed"]:
            print("Failed downloads (dropped): " + ", ".join(report["failed"]))
        if report["suspicious"]:
            print("Check these big daily moves: " + str(report["suspicious"]))
        try:
            import yfinance as yf
            r = yf.download(RATE_TICKER, start=START_DATE, auto_adjust=False, progress=False)
            if isinstance(r.columns, pd.MultiIndex):
                r.columns = r.columns.get_level_values(0)
            r.index = pd.to_datetime(r.index)
            if r.index.tz is not None:
                r.index = r.index.tz_localize(None)
            prices["RatePct"] = r["Close"].reindex(prices.index).ffill().fillna(0.0)
        except Exception:
            print("WARNING: T-bill download failed - cash will earn 0%.")
            prices["RatePct"] = 0.0
        prices.to_csv(PRICES_FILE, float_format="%.4f")
        print("Saved " + PRICES_FILE)
    else:
        prices = pd.read_csv(PRICES_FILE, index_col=0, parse_dates=True)
        print("Loaded " + PRICES_FILE + " (use --download to refresh)")
    return prices


def month_ends(idx):
    ends = list(pd.Series(idx, index=idx).groupby(idx.to_period("M")).max())
    today = pd.Timestamp.today().normalize()
    if ends and ends[-1].to_period("M") == today.to_period("M"):
        if ends[-1] < today + pd.offsets.BMonthEnd(0):
            ends = ends[:-1]
    return ends


# ---------------- selection ----------------
def select(vols, current, n_hold, sector_cap, buffer_rank):
    """vols: Series of volatility for eligible stocks. Returns list of tickers."""
    ranked = list(vols.sort_values().index)
    rank = {t: i for i, t in enumerate(ranked)}
    chosen, count = [], {}
    for t in sorted([t for t in current if t in rank], key=lambda x: rank[x]):
        s = SECTOR.get(t, "Other")
        if rank[t] < buffer_rank and count.get(s, 0) < sector_cap and len(chosen) < n_hold:
            chosen.append(t)
            count[s] = count.get(s, 0) + 1
    for t in ranked:
        if len(chosen) >= n_hold:
            break
        if t in chosen:
            continue
        s = SECTOR.get(t, "Other")
        if count.get(s, 0) < sector_cap:
            chosen.append(t)
            count[s] = count.get(s, 0) + 1
    return chosen


def make_weights(prices, stocks, rebal_dates, mends, n_hold=N_HOLD, vol_months=VOL_MONTHS,
                 sector_cap=SECTOR_CAP, buffer_rank=None, equal_universe=False):
    """Target weights at each rebalance date, using only data up to that date."""
    if buffer_rank is None:
        buffer_rank = int(round(n_hold * BUFFER_RANK / N_HOLD))
    mp = prices.loc[mends, stocks]
    mret = mp.pct_change(fill_method=None)
    rows, current = {}, []
    for d in rebal_dates:
        k = mends.index(d)
        if k < VOL_MONTHS:
            continue
        # Eligibility always needs 36 months of history, so every variant
        # and the benchmark trade the same universe on the same dates.
        hist_full = mret.iloc[k - VOL_MONTHS + 1:k + 1]
        elig = hist_full.columns[hist_full.notna().all()]
        if len(elig) < MIN_ELIGIBLE:
            continue
        w = pd.Series(0.0, index=stocks)
        if equal_universe:
            w[elig] = 1.0 / len(elig)
        else:
            hist = mret.iloc[k - vol_months + 1:k + 1][elig]
            vols = hist.std()
            current = select(vols, current, n_hold, sector_cap, buffer_rank)
            w[current] = 1.0 / len(current)
        rows[d] = w
    return pd.DataFrame(rows).T


# ---------------- simulation ----------------
def simulate(rets, weights, cash, cost=COST_PER_SIDE, lag=EXEC_LAG_DAYS):
    cols = list(weights.columns)
    R = rets[cols].fillna(0.0).to_numpy()
    C = cash.to_numpy()
    dates = rets.index
    pos = {d: i for i, d in enumerate(dates)}
    targets = {}
    for d in weights.index:
        i = pos[d] + lag
        if i < len(dates):
            targets[i] = weights.loc[d, cols].to_numpy(dtype=float)
    start = min(targets)
    h, hc = None, 0.0
    value = 1.0
    eq, turn = [], []
    for i in range(start, len(dates)):
        if h is not None:
            grown = h * (1.0 + R[i])
            gc = hc * (1.0 + C[i])
            total = grown.sum() + gc
            value *= total
            h, hc = grown / total, gc / total
        t = 0.0
        if i in targets:
            tgt = targets[i]
            t = np.abs(tgt).sum() if h is None else np.abs(tgt - h).sum()
            value *= 1.0 - t * cost
            h = tgt.copy()
            hc = 1.0 - tgt.sum()
        eq.append(value)
        turn.append(t)
    return pd.DataFrame({"equity": eq, "turnover": turn}, index=dates[start:])


def stats(eq, cash):
    eq = eq.dropna()
    r = eq.pct_change().dropna()
    c = cash.reindex(r.index).fillna(0.0)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0
    ex = r - c
    dd = (eq / eq.cummax() - 1.0).min()
    yearly = eq.groupby(eq.index.year).last() / eq.groupby(eq.index.year).first() - 1.0
    return {"CAGR": cagr, "Vol": r.std() * np.sqrt(252),
            "Sharpe": ex.mean() / ex.std() * np.sqrt(252), "MaxDD": dd,
            "WorstYr": yearly.min(), "_r": r}


def pct(x):
    return "%.1f%%" % (100 * x)


def table(rows, spy_r):
    out = {}
    for k, s in rows.items():
        beta = s["_r"].cov(spy_r.reindex(s["_r"].index)) / spy_r.reindex(s["_r"].index).var()
        out[k] = {"CAGR": pct(s["CAGR"]), "Vol": pct(s["Vol"]), "Sharpe": "%.2f" % s["Sharpe"],
                  "MaxDD": pct(s["MaxDD"]), "WorstYr": pct(s["WorstYr"]), "Beta": "%.2f" % beta}
    return pd.DataFrame(out).T.to_string()


def window(e, a, b):
    s = e.loc[a:b]
    return s / s.iloc[0]


# ---------------- main ----------------
def main():
    prices = load_data("--download" in sys.argv)
    stocks = [t for t in UNIVERSE if t in prices.columns]
    cash = (1.0 + prices["RatePct"] / 100.0) ** (1.0 / 252) - 1.0
    rets = prices[stocks + [BENCH]].pct_change(fill_method=None)
    mends = month_ends(prices.index)
    rebal = [d for d in mends if d.month in (3, 6, 9, 12)]

    w_lv = make_weights(prices, stocks, rebal, mends)
    w_ew = make_weights(prices, stocks, rebal, mends, equal_universe=True)
    w_spy = pd.DataFrame({BENCH: 1.0}, index=w_ew.index)

    res = {"Low vol": simulate(rets, w_lv, cash),
           "Equal-weight universe": simulate(rets, w_ew, cash),
           "SPY": simulate(rets, w_spy, cash)}
    gross = simulate(rets, w_lv, cash, cost=0.0)
    common = res["Low vol"].index
    for v in res.values():
        common = common.intersection(v.index)
    eqs = {k: v.loc[common, "equity"] for k, v in res.items()}
    spy_r = eqs["SPY"].pct_change().dropna()

    test_start = pd.Timestamp(TRAIN_END) + pd.Timedelta(days=1)
    periods = {
        "FULL %s to %s" % (common[0].strftime("%Y-%m"), common[-1].strftime("%Y-%m")): (common[0], common[-1]),
        "TRAIN to " + TRAIN_END[:4]: (common[0], pd.Timestamp(TRAIN_END)),
        "TEST %d onwards" % test_start.year: (test_start, common[-1]),
    }

    print("")
    print("=" * 78)
    print("STRATEGY 2: LOW-VOLATILITY US LARGE CAPS - BACKTEST - TRIAL 1")
    print("%d stocks | %d-month vol | max %d per sector | buffer rank %d | quarterly | cost %.2f%% per side"
          % (N_HOLD, VOL_MONTHS, SECTOR_CAP, BUFFER_RANK, 100 * COST_PER_SIDE))
    print("Universe: %d stocks (today's large caps - survivorship bias)" % len(stocks))
    print("=" * 78)

    test_stats = {}
    for name, (a, b) in periods.items():
        rows = {k: stats(window(e, a, b), cash) for k, e in eqs.items()}
        if name.startswith("TEST"):
            test_stats = rows
        print("")
        print(name)
        print(table(rows, spy_r))

    print("")
    print("CRISIS RETURNS")
    cr = {}
    for cname, (a, b) in CRISES.items():
        if pd.Timestamp(a) >= common[0]:
            cr[cname] = {k: window(e, a, b).iloc[-1] - 1.0 for k, e in eqs.items()}
    print(pd.DataFrame(cr).T.apply(lambda col: col.map(pct)).to_string())

    print("")
    print("YEARLY RETURNS")
    yr = {k: e.groupby(e.index.year).last() / e.groupby(e.index.year).first() - 1.0 for k, e in eqs.items()}
    print(pd.DataFrame(yr).apply(lambda col: col.map(pct)).to_string())

    # Costs (test period)
    t = res["Low vol"].loc[test_start:]
    years = (t.index[-1] - t.index[0]).days / 365.25
    turnover_pa = t["turnover"].sum() / years
    net = test_stats["Low vol"]["CAGR"]
    gr = stats(window(gross.loc[common, "equity"], test_start, common[-1]), cash)["CAGR"]
    drag = gr - net
    cash_eq = (1.0 + cash.loc[test_start:common[-1]]).cumprod()
    cash_cagr = cash_eq.iloc[-1] ** (1.0 / years) - 1.0
    excess = net - cash_cagr
    print("")
    print("COSTS (test): turnover %.0f%% a year, cost drag %s a year, excess over cash %s a year"
          % (100 * turnover_pa, pct(drag), pct(excess)))

    # Neighbour check
    ew_sharpe = test_stats["Equal-weight universe"]["Sharpe"]
    print("")
    print("NEIGHBOUR CHECK (test Sharpe vs equal-weight universe %.2f)" % ew_sharpe)
    beats = 0
    for nm, n, vm, cap in NEIGHBOURS:
        w = make_weights(prices, stocks, rebal, mends, n_hold=n, vol_months=vm, sector_cap=cap)
        e = simulate(rets, w, cash)["equity"].reindex(common).dropna()
        s = stats(window(e, test_start, common[-1]), cash)["Sharpe"]
        win = s > ew_sharpe
        beats += int(win)
        print("  %-16s %.2f  %s" % (nm, s, "beats" if win else "does not beat"))

    tl, te, ts = test_stats["Low vol"], test_stats["Equal-weight universe"], test_stats["SPY"]
    checks = [
        ("1. Test Sharpe above equal-weight universe", tl["Sharpe"] > te["Sharpe"]),
        ("2. Test volatility at least 20% below equal-weight universe", tl["Vol"] <= 0.8 * te["Vol"]),
        ("3. Test max drawdown smaller than SPY's", tl["MaxDD"] > ts["MaxDD"]),
        ("4. Beats equal-weight universe in at least 3 of 4 neighbours", beats >= 3),
        ("5. Cost drag under a third of excess return", excess > 0 and drag < excess / 3.0),
    ]
    print("")
    print("GO-LIVE CHECKS (fixed before seeing results)")
    for label, ok in checks:
        print("  " + ("PASS  " if ok else "FAIL  ") + label)

    # Sector mix and latest holdings
    last = w_lv.index[-1]
    held = list(w_lv.loc[last][w_lv.loc[last] > 0].index)
    mix = pd.Series([SECTOR.get(t, "Other") for t in held]).value_counts()
    print("")
    print("LATEST HOLDINGS (quarter-end %s): %d stocks" % (last.strftime("%Y-%m-%d"), len(held)))
    print("  " + ", ".join(sorted(held)))
    print("  Sectors: " + ", ".join("%s %d" % (k, v) for k, v in mix.items()))

    pd.DataFrame(eqs).to_csv("lowvol_results.csv", float_format="%.6f")
    print("")
    print("Saved lowvol_results.csv")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        for k, e in eqs.items():
            ax[0].plot(e.index, e.values, label=k, linewidth=1.4 if k == "Low vol" else 1.0)
            ax[1].plot(e.index, (e / e.cummax() - 1.0).values * 100, linewidth=1.0)
        ax[0].set_yscale("log")
        ax[0].axvline(test_start, color="grey", linestyle="--", linewidth=0.8)
        ax[0].legend(loc="upper left")
        ax[0].set_title("Low-volatility large caps vs benchmarks - trial 1")
        ax[1].set_ylabel("Drawdown %")
        fig.tight_layout()
        fig.savefig("lowvol_equity.png", dpi=120)
        print("Saved lowvol_equity.png")
    except ImportError:
        print("Chart skipped - install matplotlib")


if __name__ == "__main__":
    main()
