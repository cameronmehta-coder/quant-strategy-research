# trend_backtest.py - Strategy 1: multi-asset trend following
#
# Based on "151 Trading Strategies" sections 4.6 (multi-asset trend following)
# and 10.4 (volatility-scaled trend). Long-only, monthly, ETFs.
#
# Rules:
#   1. Each month-end, every asset gets a risk "slot" sized by inverse
#      volatility (calmer assets get bigger slots), computed over the whole
#      universe whether or not the asset is trending.
#   2. An asset fills its slot only if its 12-month return beats cash.
#      Otherwise that slot is held in cash.
#   3. Trades happen one trading day after the signal (EXEC_LAG_DAYS).
#
# The key benchmark is the SAME portfolio without the trend filter ("Static").
# If the trend rule cannot beat that, it adds nothing.
#
# Run from Terminal (data_loader.py must be in the same folder):
#   cd ~/Documents/Trading/portfolio
#   python3 trend_backtest.py --download     (first run: downloads prices)
#   python3 trend_backtest.py                (later runs: trial 2, saved prices)
#   python3 trend_backtest.py --trial 1      (re-run trial 1 for comparison)

import os
import sys
import numpy as np
import pandas as pd

from data_loader import download_prices, clean_prices

# ---------------- settings (fixed in advance - do not tune) ----------------
START_DATE = "2005-01-01"
PRICES_FILE = "trend_prices.csv"

# US-listed proxies used for the BACKTEST (long price history).
# Live trading in the ISA will use London-listed UCITS equivalents.
UNIVERSE = {
    "SPY": "US equities",
    "EFA": "Developed ex-US equities",
    "EEM": "Emerging market equities",
    "VNQ": "US property (REITs)",
    "IEF": "US Treasuries 7-10y",
    "TLT": "US Treasuries 20y+",
    "GLD": "Gold",
    "DBC": "Broad commodities",
}
CASH = "SHY"            # 1-3y Treasuries, stands in for cash

LOOKBACK_MONTHS = 12    # trend signal length (standard in the literature)
VOL_DAYS = 63           # about 3 months of daily returns for volatility
COST_PER_SIDE = 0.001   # 0.10% of each pound traded (spread + slippage)
EXEC_LAG_DAYS = 1       # trade 1 trading day after the month-end signal

TRAIN_END = "2016-12-31"   # 'train' = up to here, 'test' = after
GRID_LOOKBACKS = [3, 6, 9, 12]

# Trials (see trials-log.md). Choose with --trial 1 or --trial 2 (default 2).
# Trial 1: single 12-month signal (failed checks 1 and 3 on 3 Nov 2026).
# Trial 2: blended 3/6/12-month signal - each lookback votes on/off and the
#          asset fills the average of the votes. Pre-registered 29 Oct 2026.
TRIAL_SIGNALS = {1: 12, 2: [3, 6, 12]}

# Trial 2, check 3 (fixed 3 Nov 2026 BEFORE running on real data):
# the blend must beat its matching Static in at least 3 of these 4 neighbours.
# (name, lookbacks, slot weighting, vol window days)
TRIAL2_NEIGHBOURS = [
    ("Blend 1/3/12 (AQR)", [1, 3, 12], "invvol", 63),
    ("Blend 3/6/9/12", [3, 6, 9, 12], "invvol", 63),
    ("Blend 3/6/12, equal slots", [3, 6, 12], "equal", 63),
    ("Blend 3/6/12, 126-day vol", [3, 6, 12], "invvol", 126),
]

CRISES = {
    "GFC 2007-09": ("2007-10-09", "2009-03-09"),
    "COVID 2020": ("2020-02-19", "2020-03-23"),
    "2022 stocks+bonds": ("2022-01-03", "2022-12-30"),
}

ASSETS = list(UNIVERSE.keys())
ALL_COLS = ASSETS + [CASH]


# ---------------- data ----------------
def load_prices(refresh):
    if refresh or not os.path.exists(PRICES_FILE):
        prices = download_prices(ALL_COLS, START_DATE)
        prices, report = clean_prices(prices)
        missing = [t for t in ALL_COLS if t not in prices.columns]
        if missing:
            sys.exit("Missing tickers after download: " + ", ".join(missing)
                     + " - run again with --download")
        if report["suspicious"]:
            print("Check these big daily moves: " + str(report["suspicious"]))
        prices.to_csv(PRICES_FILE, float_format="%.4f")
        print("Saved " + PRICES_FILE)
    else:
        prices = pd.read_csv(PRICES_FILE, index_col=0, parse_dates=True)
        print("Loaded " + PRICES_FILE + " (use --download to refresh)")
    return prices[ALL_COLS]


def month_end_dates(prices):
    """Last trading day of each month. Drops the current, unfinished month."""
    idx = prices.index
    ends = pd.Series(idx, index=idx).groupby(idx.to_period("M")).max()
    ends = list(ends)
    today = pd.Timestamp.today().normalize()
    if ends and ends[-1].to_period("M") == today.to_period("M"):
        last_bday = today + pd.offsets.BMonthEnd(0)
        if ends[-1] < last_bday:
            ends = ends[:-1]   # month not finished yet
    return ends


# ---------------- signals ----------------
def make_weights(prices, me_dates, lookback, weighting="invvol", use_trend=True,
                 vol_days=None):
    """Target weights at each month-end. Uses only data up to that date.

    lookback can be one number (e.g. 12) or a list (e.g. [3, 6, 12]).
    With a list, each lookback gives an on/off vote and the asset fills
    the average of the votes (0, 1/3, 2/3 or 1 of its slot).
    """
    lbs = list(lookback) if isinstance(lookback, (list, tuple)) else [lookback]
    vd = vol_days if vol_days else VOL_DAYS
    rets = prices.pct_change(fill_method=None)
    vol = rets.rolling(vd, min_periods=vd).std() * np.sqrt(252)
    rows = {}
    for k in range(max(lbs), len(me_dates)):
        d = me_dates[k]
        votes = []
        ok = pd.Series(True, index=ASSETS)
        for lb in lbs:
            d0 = me_dates[k - lb]
            mom = prices.loc[d, ASSETS] / prices.loc[d0, ASSETS] - 1.0
            cash_mom = prices.loc[d, CASH] / prices.loc[d0, CASH] - 1.0
            ok = ok & mom.notna()
            votes.append((mom > cash_mom).astype(float))
        v = vol.loc[d, ASSETS]
        ok = ok & v.notna() & (v > 0)
        if ok.sum() == 0:
            continue
        names = list(ok[ok].index)
        if weighting == "invvol":
            raw = 1.0 / v[names]
            slots = raw / raw.sum()
        else:
            slots = pd.Series(1.0 / len(names), index=names)
        if use_trend:
            on = (sum(votes) / len(votes))[names]
        else:
            on = pd.Series(1.0, index=names)
        w = pd.Series(0.0, index=ALL_COLS)
        w[names] = slots * on
        w[CASH] = 1.0 - w[ASSETS].sum()
        rows[d] = w
    return pd.DataFrame(rows).T


def fixed_weights(dates, mix):
    w = pd.DataFrame(0.0, index=dates, columns=ALL_COLS)
    for k, v in mix.items():
        w[k] = v
    return w


# ---------------- simulation ----------------
def simulate(rets, weights, lag=EXEC_LAG_DAYS, cost=COST_PER_SIDE):
    """Daily simulation with drifting weights. Returns equity and turnover."""
    R = rets[ALL_COLS].fillna(0.0).to_numpy()
    dates = rets.index
    pos = {d: i for i, d in enumerate(dates)}
    targets = {}
    for d in weights.index:
        i = pos[d] + lag
        if i < len(dates):
            targets[i] = weights.loc[d, ALL_COLS].to_numpy(dtype=float)
    if not targets:
        sys.exit("No rebalance dates to simulate.")
    noncash = np.array([c != CASH for c in ALL_COLS])
    start = min(targets)
    h = None
    value = 1.0
    eq, turn = [], []
    for i in range(start, len(dates)):
        if h is not None:
            grown = h * (1.0 + R[i])
            total = grown.sum()
            value *= total
            h = grown / total
        t = 0.0
        if i in targets:
            tgt = targets[i]
            if h is None:
                t = np.abs(tgt[noncash]).sum()
            else:
                t = np.abs(tgt - h)[noncash].sum()
            value *= (1.0 - t * cost)
            h = tgt.copy()
        eq.append(value)
        turn.append(t)
    return pd.DataFrame({"equity": eq, "turnover": turn}, index=dates[start:])


# ---------------- statistics ----------------
def month_end_values(series):
    return series.groupby(series.index.to_period("M")).last()


def stats(eq, cash_eq, spy_eq):
    eq = eq.dropna()
    r = eq.pct_change().dropna()
    c = cash_eq.pct_change().reindex(r.index).fillna(0.0)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0
    vol = r.std() * np.sqrt(252)
    ex = r - c
    sharpe = ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1.0).min()
    m = month_end_values(eq).pct_change().dropna()
    ms = month_end_values(spy_eq.reindex(eq.index)).pct_change().dropna()
    corr = m.corr(ms.reindex(m.index))
    yearly = eq.groupby(eq.index.year).last() / eq.groupby(eq.index.year).first() - 1.0
    return {
        "CAGR": cagr,
        "Vol": vol,
        "Sharpe": sharpe,
        "MaxDD": dd,
        "Calmar": cagr / abs(dd) if dd < 0 else np.nan,
        "WorstYr": yearly.min(),
        "Up months": (m > 0).mean(),
        "Corr SPY": corr,
    }


def window(eq, start, end):
    s = eq.loc[start:end]
    return s / s.iloc[0]


def fmt_table(rows):
    df = pd.DataFrame(rows).T
    out = df.copy().astype(object)
    for col in df.columns:
        for idx in df.index:
            v = df.loc[idx, col]
            if col in ("Sharpe", "Calmar", "Corr SPY"):
                out.loc[idx, col] = "%.2f" % v
            else:
                out.loc[idx, col] = "%.1f%%" % (100 * v)
    return out.to_string()


def pct(x):
    return "%.1f%%" % (100 * x)


# ---------------- main ----------------
def main():
    refresh = "--download" in sys.argv
    trial = 2
    if "--trial" in sys.argv:
        i = sys.argv.index("--trial")
        try:
            trial = int(sys.argv[i + 1])
        except (IndexError, ValueError):
            sys.exit("Use --trial 1 or --trial 2")
    if trial not in TRIAL_SIGNALS:
        sys.exit("Unknown trial %d. Choose from %s" % (trial, sorted(TRIAL_SIGNALS)))
    prices = load_prices(refresh)
    rets = prices.pct_change(fill_method=None)
    me = month_end_dates(prices)

    # Common start: first month-end where every asset has 12 months of history
    # and a volatility estimate, so all variants are compared over the same dates.
    vol = rets.rolling(VOL_DAYS, min_periods=VOL_DAYS).std()
    maxlb = max(GRID_LOOKBACKS)
    eval_start = None
    for k in range(maxlb, len(me)):
        if prices.loc[me[k - maxlb], ASSETS].notna().all() and vol.loc[me[k], ASSETS].notna().all():
            eval_start = me[k]
            break
    if eval_start is None:
        sys.exit("Not enough history for every asset.")

    def run(w, cost=COST_PER_SIDE):
        w = w.loc[w.index >= eval_start]
        return simulate(rets, w, cost=cost)

    reb = [d for d in me if d >= eval_start]
    signal = TRIAL_SIGNALS[trial]
    w_trend = make_weights(prices, me, signal)
    w_static = make_weights(prices, me, LOOKBACK_MONTHS, use_trend=False)

    res = {
        "Trend": run(w_trend),
        "Static (no trend)": run(w_static),
        "60/40 SPY/IEF": run(fixed_weights(reb, {"SPY": 0.6, "IEF": 0.4})),
        "SPY": run(fixed_weights(reb, {"SPY": 1.0})),
    }
    gross = run(w_trend, cost=0.0)

    # Align every curve to the same dates
    common = res["Trend"].index
    for k in res:
        common = common.intersection(res[k].index)
    eqs = {k: v.loc[common, "equity"] for k, v in res.items()}
    cash_eq = (1.0 + rets[CASH].loc[common].fillna(0.0)).cumprod()
    spy_eq = eqs["SPY"]

    test_start = pd.Timestamp(TRAIN_END) + pd.Timedelta(days=1)
    periods = {
        "FULL " + common[0].strftime("%Y-%m") + " to " + common[-1].strftime("%Y-%m"): (common[0], common[-1]),
        "TRAIN to " + TRAIN_END[:4]: (common[0], pd.Timestamp(TRAIN_END)),
        "TEST " + str(test_start.year) + " onwards": (test_start, common[-1]),
    }

    print("")
    print("=" * 78)
    print("STRATEGY 1: MULTI-ASSET TREND FOLLOWING - BACKTEST - TRIAL %d" % trial)
    sig_txt = "/".join(str(x) for x in (signal if isinstance(signal, list) else [signal]))
    print("Signal %s months | vol window %d days | cost %.2f%% per side | lag %d day"
          % (sig_txt, VOL_DAYS, 100 * COST_PER_SIDE, EXEC_LAG_DAYS))
    print("=" * 78)

    test_stats = {}
    for name, (a, b) in periods.items():
        rows = {}
        for k, e in eqs.items():
            rows[k] = stats(window(e, a, b), cash_eq.loc[a:b], spy_eq.loc[a:b])
        if name.startswith("TEST"):
            test_stats = rows
        print("")
        print(name)
        print(fmt_table(rows))

    print("")
    print("CRISIS RETURNS")
    crisis_rows = {}
    for cname, (a, b) in CRISES.items():
        if pd.Timestamp(a) < common[0] or pd.Timestamp(b) > common[-1]:
            continue
        crisis_rows[cname] = {k: window(e, a, b).iloc[-1] - 1.0 for k, e in eqs.items()}
    if crisis_rows:
        ct = pd.DataFrame(crisis_rows).T
        print(ct.apply(lambda col: col.map(pct)).to_string())

    print("")
    print("YEARLY RETURNS")
    yr = {}
    for k, e in eqs.items():
        yr[k] = e.groupby(e.index.year).last() / e.groupby(e.index.year).first() - 1.0
    print(pd.DataFrame(yr).apply(lambda col: col.map(pct)).to_string())

    # Costs and turnover (test period)
    t = res["Trend"].loc[test_start:]
    years = (t.index[-1] - t.index[0]).days / 365.25
    turnover_pa = t["turnover"].sum() / years
    g = gross.loc[common, "equity"]
    net_cagr = test_stats["Trend"]["CAGR"]
    gross_cagr = stats(window(g, test_start, common[-1]), cash_eq.loc[test_start:], spy_eq.loc[test_start:])["CAGR"]
    drag = gross_cagr - net_cagr
    cash_cagr = (cash_eq.loc[test_start:].iloc[-1] / cash_eq.loc[test_start:].iloc[0]) ** (1.0 / years) - 1.0
    excess = net_cagr - cash_cagr
    print("")
    print("COSTS (test period): turnover %.0f%% a year, cost drag %s a year, excess over cash %s a year"
          % (100 * turnover_pa, pct(drag), pct(excess)))

    # Robustness grid (test period Sharpe / MaxDD)
    print("")
    print("ROBUSTNESS GRID (test period)")
    grid = {}
    for wt in ["invvol", "equal"]:
        st = run(make_weights(prices, me, LOOKBACK_MONTHS, weighting=wt, use_trend=False))
        st_s = stats(window(st["equity"].loc[common], test_start, common[-1]),
                     cash_eq.loc[test_start:], spy_eq.loc[test_start:])
        for lb in GRID_LOOKBACKS:
            r = run(make_weights(prices, me, lb, weighting=wt))
            s = stats(window(r["equity"].loc[common], test_start, common[-1]),
                      cash_eq.loc[test_start:], spy_eq.loc[test_start:])
            grid[(wt, lb)] = {"Sharpe": s["Sharpe"], "MaxDD": s["MaxDD"],
                              "Static Sharpe": st_s["Sharpe"],
                              "Beats static": s["Sharpe"] > st_s["Sharpe"]}
    gdf = pd.DataFrame(grid).T
    gdf.index.names = ["weighting", "lookback"]
    show = gdf.copy().astype(object)
    show["Sharpe"] = gdf["Sharpe"].map(lambda v: "%.2f" % v)
    show["Static Sharpe"] = gdf["Static Sharpe"].map(lambda v: "%.2f" % v)
    show["MaxDD"] = gdf["MaxDD"].map(pct)
    print(show.to_string())

    def test_sharpe(w):
        e = run(w)["equity"].reindex(common).dropna()
        return stats(window(e, test_start, common[-1]),
                     cash_eq.loc[test_start:], spy_eq.loc[test_start:])["Sharpe"]

    if trial == 1:
        beats = sum(1 for lb in GRID_LOOKBACKS if grid[("invvol", lb)]["Beats static"])
        check3 = ("3. Beats Static in at least 3 of 4 lookbacks", beats >= 3)
    else:
        print("")
        print("TRIAL 2 NEIGHBOUR CHECK (test period Sharpe vs matching Static)")
        beats = 0
        for name, lbs, wt, vd in TRIAL2_NEIGHBOURS:
            s_n = test_sharpe(make_weights(prices, me, lbs, weighting=wt, vol_days=vd))
            s_st = test_sharpe(make_weights(prices, me, LOOKBACK_MONTHS, weighting=wt,
                                            use_trend=False, vol_days=vd))
            win = s_n > s_st
            beats += int(win)
            print("  %-28s %.2f vs %.2f  %s" % (name, s_n, s_st, "beats" if win else "does not beat"))
        check3 = ("3. Beats Static in at least 3 of 4 neighbours", beats >= 3)

    # Pre-registered go-live checks
    ts, ss = test_stats["Trend"], test_stats["Static (no trend)"]
    checks = [
        ("1. Test Sharpe above Static", ts["Sharpe"] > ss["Sharpe"]),
        ("2. Test MaxDD smaller than Static and under 20%",
         ts["MaxDD"] > ss["MaxDD"] and ts["MaxDD"] > -0.20),
        check3,
    ]
    if "GFC 2007-09" in crisis_rows:
        gfc = crisis_rows["GFC 2007-09"]
        checks.append(("4. GFC loss less than half of SPY's", gfc["Trend"] > 0.5 * gfc["SPY"]))
    checks.append(("5. Cost drag under a third of excess return", excess > 0 and drag < excess / 3.0))
    print("")
    print("GO-LIVE CHECKS (fixed before seeing results)")
    for label, ok in checks:
        print("  " + ("PASS  " if ok else "FAIL  ") + label)

    # Latest signal (information only - not a trade instruction yet)
    last = w_trend.index[-1]
    print("")
    print("LATEST SIGNAL (month-end " + last.strftime("%Y-%m-%d") + ")")
    for tk in ALL_COLS:
        label = UNIVERSE.get(tk, "Cash")
        print("  " + tk.ljust(4) + " " + label.ljust(26) + " " + pct(w_trend.loc[last, tk]).rjust(6))

    # Save outputs
    out = pd.DataFrame(eqs)
    out.to_csv("trend_results_t%d.csv" % trial, float_format="%.6f")
    print("")
    print("Saved trend_results_t%d.csv" % trial)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
        for k, e in eqs.items():
            ax[0].plot(e.index, e.values, label=k, linewidth=1.4 if k == "Trend" else 1.0)
            ax[1].plot(e.index, (e / e.cummax() - 1.0).values * 100, linewidth=1.0)
        ax[0].set_yscale("log")
        ax[0].set_ylabel("Growth of 1 (log)")
        ax[0].axvline(test_start, color="grey", linestyle="--", linewidth=0.8)
        ax[0].legend(loc="upper left")
        ax[0].set_title("Multi-asset trend following vs benchmarks - trial %d" % trial)
        ax[1].set_ylabel("Drawdown %")
        ax[1].axvline(test_start, color="grey", linestyle="--", linewidth=0.8)
        fig.tight_layout()
        fig.savefig("trend_equity_t%d.png" % trial, dpi=120)
        print("Saved trend_equity_t%d.png" % trial)
    except ImportError:
        print("Chart skipped - install with: pip3 install matplotlib")


if __name__ == "__main__":
    main()
