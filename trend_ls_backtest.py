# trend_ls_backtest.py - Strategy 1, TRIAL 3: long-short trend following
#
# Rules (fixed 3 Nov 2026 before running on real data - see trials-log.md):
#   Universe = markets available as Trading 212 CFDs (US ETF proxies):
#     SPY (USA 500), FEZ (EU50), VWO (VWO), TLT (USBOND), GLD (Gold), USO (CRUDE)
#   Each month-end: every market gets an inverse-volatility slot (63-day vol),
#   slots add up to 100% of capital (no leverage).
#   12-month return above cash -> LONG its slot (ISA ETF, cost 0.10% per side)
#   12-month return below cash -> SHORT its slot (CFD)
#   Trade 1 trading day after the signal.
#
# CFD short costs (from the Trading 212 app, 3 Nov 2026):
#   spread 0.05% per side (cautious; USA 500 was about 0.004%)
#   overnight interest about 5.1% a year on the short position
#   0.5% FX fee on profit or loss (charged here on the daily short P&L)
#   cash posted against shorts earns nothing (cautious)
#
# Comparisons: the long-only version on the SAME six markets (shorts -> cash),
# Static (same slots, always long), 60/40, SPY.
#
# Run (data_loader.py must be in the same folder):
#   python3 trend_ls_backtest.py --download     (first run)
#   python3 trend_ls_backtest.py

import os
import sys
import numpy as np
import pandas as pd

from data_loader import download_prices, clean_prices

START_DATE = "2004-01-01"
PRICES_FILE = "trend_ls_prices.csv"
UNIVERSE = {"SPY": "USA 500", "FEZ": "EU50", "VWO": "Emerging (VWO)",
            "TLT": "USBOND", "GLD": "Gold", "USO": "CRUDE"}
CASH = "SHY"
BOND = "IEF"   # only for the 60/40 benchmark
ASSETS = list(UNIVERSE)
COLS = ASSETS + [CASH]

LOOKBACK = 12
VOL_DAYS = 63
LONG_COST = 0.001
SHORT_COST = 0.0005
SHORT_FIN_PA = 0.051
FX_ON_PNL = 0.005
LAG = 1
TRAIN_END = "2016-12-31"
GRID = [3, 6, 9, 12]
CRISES = {"GFC 2007-09": ("2007-10-09", "2009-03-09"),
          "COVID 2020": ("2020-02-19", "2020-03-23"),
          "2022 stocks+bonds": ("2022-01-03", "2022-12-30")}


def load(refresh):
    if refresh or not os.path.exists(PRICES_FILE):
        p = download_prices(COLS + [BOND], START_DATE)
        p, rep = clean_prices(p)
        miss = [t for t in COLS + [BOND] if t not in p.columns]
        if miss:
            sys.exit("Missing after download: " + ", ".join(miss) + " - try again")
        if rep["suspicious"]:
            print("Check these big daily moves: " + str(rep["suspicious"]))
        p.to_csv(PRICES_FILE, float_format="%.4f")
        print("Saved " + PRICES_FILE)
    else:
        p = pd.read_csv(PRICES_FILE, index_col=0, parse_dates=True)
        print("Loaded " + PRICES_FILE + " (use --download to refresh)")
    return p


def month_ends(idx):
    ends = list(pd.Series(idx, index=idx).groupby(idx.to_period("M")).max())
    today = pd.Timestamp.today().normalize()
    if ends and ends[-1].to_period("M") == today.to_period("M"):
        if ends[-1] < today + pd.offsets.BMonthEnd(0):
            ends = ends[:-1]
    return ends


def weights(p, me, lookback, mode):
    """mode: 'ls' long-short, 'lo' long-only (losers -> cash), 'static' always long."""
    vol = p[ASSETS].pct_change(fill_method=None).rolling(VOL_DAYS, min_periods=VOL_DAYS).std()
    rows = {}
    for k in range(lookback, len(me)):
        d, d0 = me[k], me[k - lookback]
        mom = p.loc[d, ASSETS] / p.loc[d0, ASSETS] - 1.0
        cm = p.loc[d, CASH] / p.loc[d0, CASH] - 1.0
        v = vol.loc[d]
        ok = mom.notna() & v.notna() & (v > 0)
        if not ok.all():
            continue          # wait until every market has history
        slots = (1.0 / v) / (1.0 / v).sum()
        up = mom > cm
        w = pd.Series(0.0, index=COLS)
        if mode == "ls":
            w[ASSETS] = np.where(up, slots, -slots)
        elif mode == "lo":
            w[ASSETS] = np.where(up, slots, 0.0)
        else:
            w[ASSETS] = slots
        w[CASH] = 1.0 - w[ASSETS].clip(lower=0).sum() - (-w[ASSETS].clip(upper=0)).sum()
        rows[d] = w
    return pd.DataFrame(rows).T


def simulate(rets, w, costs=True):
    """Tracks signed exposures in money. Shorts pay financing and FX on P&L."""
    R = rets[COLS].fillna(0.0).to_numpy()
    dates = rets.index
    pos = {d: i for i, d in enumerate(dates)}
    targets = {pos[d] + LAG: w.loc[d, COLS].to_numpy(float) for d in w.index if pos[d] + LAG < len(dates)}
    start = min(targets)
    fin_day = SHORT_FIN_PA / 365.0 * (365.0 / 252.0)   # per trading day
    V, n = 1.0, None
    eq, turn, drag = [], [], []
    for i in range(start, len(dates)):
        cost_today = 0.0
        if n is not None:
            pnl = n * R[i]
            short = n < 0
            if costs:
                cost_today += fin_day * (-n[short]).sum()
                cost_today += FX_ON_PNL * np.abs(pnl[short]).sum()
            V += pnl.sum() - cost_today
            n = n * (1.0 + R[i])
        t = 0.0
        if i in targets:
            tgt = targets[i] * V
            old = np.zeros(len(COLS)) if n is None else n
            for j in range(len(ASSETS)):
                a, b = old[j], tgt[j]
                if costs:
                    # cost of reducing the old leg and building the new leg
                    if a * b >= 0:
                        side = LONG_COST if max(a, b) > 0 else SHORT_COST
                        c = abs(b - a) * side
                    else:
                        c = abs(a) * (LONG_COST if a > 0 else SHORT_COST) + abs(b) * (LONG_COST if b > 0 else SHORT_COST)
                    V -= c
                    cost_today += c
                t += abs(b - a)
            n = targets[i] * V
        eq.append(V)
        turn.append(t / max(V, 1e-9))
        drag.append(cost_today)
    return pd.DataFrame({"equity": eq, "turnover": turn, "costs": drag}, index=dates[start:])


def stats(e, cash):
    e = e.dropna()
    r = e.pct_change().dropna()
    c = cash.reindex(r.index).fillna(0.0)
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    ex = r - c
    dd = (e / e.cummax() - 1.0).min()
    y = e.groupby(e.index.year).last() / e.groupby(e.index.year).first() - 1.0
    return {"CAGR": (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1, "Vol": r.std() * np.sqrt(252),
            "Sharpe": ex.mean() / ex.std() * np.sqrt(252), "MaxDD": dd, "WorstYr": y.min()}


def win(e, a, b):
    s = e.loc[a:b]
    return s / s.iloc[0]


def pct(x):
    return "%.1f%%" % (100 * x)


def table(rows, spy_m):
    out = {}
    for k, (s, e) in rows.items():
        m = e.groupby(e.index.to_period("M")).last().pct_change().dropna()
        out[k] = {"CAGR": pct(s["CAGR"]), "Vol": pct(s["Vol"]), "Sharpe": "%.2f" % s["Sharpe"],
                  "MaxDD": pct(s["MaxDD"]), "WorstYr": pct(s["WorstYr"]),
                  "Corr SPY": "%.2f" % m.corr(spy_m.reindex(m.index))}
    return pd.DataFrame(out).T.to_string()


def main():
    p = load("--download" in sys.argv)
    rets = p.pct_change(fill_method=None)
    cash = rets[CASH].fillna(0.0)
    me = month_ends(p.index)

    w_ls = weights(p, me, LOOKBACK, "ls")
    w_lo = weights(p, me, LOOKBACK, "lo")
    w_st = weights(p, me, LOOKBACK, "static")
    start = w_ls.index[0]
    reb = [d for d in me if d >= start]
    w_6040 = pd.DataFrame(0.0, index=reb, columns=COLS)
    w_spy = w_6040.copy()
    w_spy["SPY"] = 1.0

    rets2 = rets.copy()
    rets2[CASH] = rets[CASH]
    res = {"Long-short trend": simulate(rets2, w_ls),
           "Long-only trend": simulate(rets2, w_lo),
           "Static": simulate(rets2, w_st),
           "SPY": simulate(rets2, w_spy)}
    # 60/40 uses IEF, which is outside COLS: simulate it simply
    r6040 = (0.6 * rets["SPY"] + 0.4 * rets[BOND]).fillna(0.0)
    gross = simulate(rets2, w_ls, costs=False)

    common = res["Long-short trend"].index
    eqs = {k: v.loc[common, "equity"] for k, v in res.items()}
    eqs["60/40 SPY/IEF"] = (1.0 + r6040.loc[common]).cumprod()
    spy_m = eqs["SPY"].groupby(common.to_period("M")).last().pct_change().dropna()
    test_start = pd.Timestamp(TRAIN_END) + pd.Timedelta(days=1)

    print("")
    print("=" * 78)
    print("STRATEGY 1: LONG-SHORT TREND FOLLOWING - BACKTEST - TRIAL 3")
    print("12-month signal | 6 CFD markets | shorts: %.1f%% a year financing, %.2f%% spread, 0.5%% FX on P&L"
          % (100 * SHORT_FIN_PA, 100 * SHORT_COST))
    print("=" * 78)
    test_rows = {}
    for name, (a, b) in {"FULL %s to %s" % (common[0].strftime("%Y-%m"), common[-1].strftime("%Y-%m")): (common[0], common[-1]),
                         "TRAIN to 2016": (common[0], pd.Timestamp(TRAIN_END)),
                         "TEST 2017 onwards": (test_start, common[-1])}.items():
        rows = {k: (stats(win(e, a, b), cash), win(e, a, b)) for k, e in eqs.items()}
        if name.startswith("TEST"):
            test_rows = {k: v[0] for k, v in rows.items()}
        print("")
        print(name)
        print(table(rows, spy_m))

    print("")
    print("CRISIS RETURNS")
    cr = {c: {k: win(e, a, b).iloc[-1] - 1 for k, e in eqs.items()}
          for c, (a, b) in CRISES.items() if pd.Timestamp(a) >= common[0]}
    print(pd.DataFrame(cr).T.apply(lambda col: col.map(pct)).to_string())

    print("")
    print("YEARLY RETURNS")
    yr = {k: e.groupby(e.index.year).last() / e.groupby(e.index.year).first() - 1 for k, e in eqs.items()}
    print(pd.DataFrame(yr).apply(lambda col: col.map(pct)).to_string())

    # Short side exposure and costs (test period)
    sh = (-w_ls[ASSETS].clip(upper=0)).sum(axis=1)
    t = res["Long-short trend"].loc[test_start:]
    yrs = (t.index[-1] - t.index[0]).days / 365.25
    net = test_rows["Long-short trend"]["CAGR"]
    gr = stats(win(gross.loc[common, "equity"], test_start, common[-1]), cash)["CAGR"]
    c_eq = (1 + cash.loc[test_start:common[-1]]).cumprod()
    excess = net - (c_eq.iloc[-1] ** (1 / yrs) - 1)
    print("")
    print("SHORT SIDE: average %.0f%% of capital short (test); months with any short: %.0f%%"
          % (100 * sh.loc[test_start:].mean(), 100 * (sh.loc[test_start:] > 0).mean()))
    print("COSTS (test): turnover %.0f%% a year, total cost drag %s a year, excess over cash %s a year"
          % (100 * t["turnover"].sum() / yrs, pct(gr - net), pct(excess)))

    print("")
    print("ROBUSTNESS (test Sharpe): long-short vs long-only on the same markets")
    beats = 0
    for lb in GRID:
        s_ls = stats(win(simulate(rets2, weights(p, me, lb, "ls"))["equity"].reindex(common).dropna(), test_start, common[-1]), cash)["Sharpe"]
        s_lo = stats(win(simulate(rets2, weights(p, me, lb, "lo"))["equity"].reindex(common).dropna(), test_start, common[-1]), cash)["Sharpe"]
        beats += int(s_ls > s_lo)
        print("  %2d months: %.2f vs %.2f  %s" % (lb, s_ls, s_lo, "beats" if s_ls > s_lo else "does not beat"))

    tl, to, ts = test_rows["Long-short trend"], test_rows["Long-only trend"], test_rows["Static"]
    checks = [
        ("1. Test Sharpe above the long-only version (shorting adds value)", tl["Sharpe"] > to["Sharpe"]),
        ("2. Test Sharpe above Static", tl["Sharpe"] > ts["Sharpe"]),
        ("3. Test max drawdown under 20%", tl["MaxDD"] > -0.20),
        ("4. Beats long-only in at least 3 of 4 lookbacks", beats >= 3),
        ("5. Cost drag under a third of excess return", excess > 0 and (gr - net) < excess / 3),
    ]
    print("")
    print("GO-LIVE CHECKS (fixed before seeing results)")
    for label, ok in checks:
        print("  " + ("PASS  " if ok else "FAIL  ") + label)

    last = w_ls.index[-1]
    print("")
    print("LATEST SIGNAL (month-end %s) - information only" % last.strftime("%Y-%m-%d"))
    for tk in ASSETS:
        x = w_ls.loc[last, tk]
        print("  %-4s %-16s %-5s %s" % (tk, UNIVERSE[tk], "LONG" if x > 0 else "SHORT", pct(abs(x)).rjust(6)))

    pd.DataFrame(eqs).to_csv("trend_ls_results.csv", float_format="%.6f")
    print("")
    print("Saved trend_ls_results.csv")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        for k, e in eqs.items():
            ax[0].plot(e.index, e.values, label=k, linewidth=1.4 if k.startswith("Long-short") else 1.0)
            ax[1].plot(e.index, (e / e.cummax() - 1) * 100, linewidth=1.0)
        ax[0].set_yscale("log")
        ax[0].axvline(test_start, color="grey", linestyle="--", linewidth=0.8)
        ax[0].legend(loc="upper left")
        ax[0].set_title("Trend following - trial 3 (long-short)")
        ax[1].set_ylabel("Drawdown %")
        fig.tight_layout()
        fig.savefig("trend_ls_equity.png", dpi=120)
        print("Saved trend_ls_equity.png")
    except ImportError:
        print("Chart skipped - install matplotlib")


if __name__ == "__main__":
    main()
