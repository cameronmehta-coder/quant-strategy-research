# portfolio_combo.py - How should the fund combine IBS with a defensive sleeve?
#
# PORTFOLIO-CONSTRUCTION ANALYSIS, not a new strategy trial. Both sleeves were
# already tested (trials-log.md), so this measures known costs and benefits.
#
#   IBS sleeve   = IBS trial 1 on SPY (CFD account). Idle cash shown two ways:
#                  earning T-bills, and earning nothing (cautious - CFD cash)
#   Trend sleeve = trend trial 1 rules (long-only, 8 ETFs, ISA)
#   Index sleeve = SPY buy and hold (the plain alternative to trend)
#
# Portfolios (50/50 = about GBP 250 each of GBP 500), rebalanced once a year
# (moving money between the ISA and the CFD account is manual):
#   A. 50% IBS + 50% Trend      B. 50% IBS + 50% Index
#   C. 100% IBS                 D. 100% Index
#
# Decision rule (written 4 Nov 2026 before running):
#   Choose A over B only if A's max drawdown is at least one third smaller AND
#   A gives up no more than 2% a year of return versus B.
#
# Run (needs trend_prices.csv and ibs_prices.csv from earlier runs, plus
# trend_backtest.py, ibs_backtest.py and data_loader.py in this folder):
#   python3 portfolio_combo.py

import os
import sys
import numpy as np
import pandas as pd

import trend_backtest as tb
import ibs_backtest as ib

CRISES = {"GFC 2007-09": ("2007-10-09", "2009-03-09"),
          "Q4 2018": ("2018-09-20", "2018-12-24"),
          "COVID 2020": ("2020-02-19", "2020-03-23"),
          "2022": ("2022-01-03", "2022-12-30")}


def trend_daily():
    if not os.path.exists(tb.PRICES_FILE):
        sys.exit("Missing " + tb.PRICES_FILE + " - run: python3 trend_backtest.py --download")
    p = pd.read_csv(tb.PRICES_FILE, index_col=0, parse_dates=True)[tb.ALL_COLS]
    rets = p.pct_change(fill_method=None)
    me = tb.month_end_dates(p)
    w = tb.make_weights(p, me, 12)
    vol = rets.rolling(tb.VOL_DAYS, min_periods=tb.VOL_DAYS).std()
    for k in range(12, len(me)):
        if p.loc[me[k - 12], tb.ASSETS].notna().all() and vol.loc[me[k], tb.ASSETS].notna().all():
            start = me[k]
            break
    eq = tb.simulate(rets, w.loc[w.index >= start])["equity"]
    return eq.pct_change().dropna()


def ibs_daily(cash_earns):
    if not os.path.exists(ib.PRICES_FILE):
        sys.exit("Missing " + ib.PRICES_FILE + " - run: python3 ibs_backtest.py --download")
    px = pd.read_csv(ib.PRICES_FILE, index_col=0, parse_dates=True)
    cash = (1 + px["RatePct"] / 100) ** (1 / 252) - 1   # real T-bill, for Sharpe
    sim = px.copy()
    if not cash_earns:
        sim["RatePct"] = 0.0
    d, _, _ = ib.simulate(sim)
    spy = px["Close"].pct_change()
    return d, spy, cash


def combine(a, b, wa):
    """Two sleeves, weights reset to target on the first trading day of each year."""
    df = pd.concat([a, b], axis=1).dropna()
    va, vb, out = wa, 1 - wa, []
    year = df.index[0].year
    for d, (ra, rb) in zip(df.index, df.to_numpy()):
        if d.year != year:
            tot = va + vb
            va, vb, year = tot * wa, tot * (1 - wa), d.year
        prev = va + vb
        va *= 1 + ra
        vb *= 1 + rb
        out.append((va + vb) / prev - 1)
    return pd.Series(out, index=df.index)


def stats(r, cash):
    eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    ex = r - cash.reindex(r.index).fillna(0)
    y = (1 + r).groupby(r.index.year).prod() - 1
    return {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "Vol": r.std() * np.sqrt(252),
            "Sharpe": ex.mean() / ex.std() * np.sqrt(252),
            "MaxDD": (eq / eq.cummax() - 1).min(), "WorstYr": y.min()}


def pct(x):
    return "%.1f%%" % (100 * x)


def main():
    trend = trend_daily()
    for label, earns in [("IBS idle cash earns T-bills", True),
                         ("IBS idle cash earns NOTHING (cautious)", False)]:
        ibs, spy, cash = ibs_daily(earns)
        common = trend.index.intersection(ibs.index).intersection(spy.dropna().index)
        t, i, s = trend.loc[common], ibs.loc[common], spy.loc[common]
        ports = {"A. 50% IBS + 50% Trend": combine(i, t, 0.5),
                 "B. 50% IBS + 50% Index": combine(i, s, 0.5),
                 "C. 100% IBS": i, "D. 100% Index (SPY)": s,
                 "Trend alone": t}
        print("")
        print("=" * 78)
        print("FUND PORTFOLIO OPTIONS - %s" % label)
        print("%s to %s, sleeves rebalanced yearly" % (common[0].strftime("%Y-%m"), common[-1].strftime("%Y-%m")))
        print("=" * 78)
        st = {k: stats(v, cash) for k, v in ports.items()}
        tab = pd.DataFrame({k: {c: ("%.2f" % v[c] if c == "Sharpe" else pct(v[c])) for c in v}
                            for k, v in st.items()}).T
        print(tab.to_string())
        print("")
        print("Correlation of daily returns: IBS vs Trend %.2f | IBS vs Index %.2f | Trend vs Index %.2f"
              % (i.corr(t), i.corr(s), t.corr(s)))
        print("")
        print("CRISES")
        cr = {n: {k: (1 + v.loc[a:b]).prod() - 1 for k, v in ports.items()}
              for n, (a, b) in CRISES.items() if pd.Timestamp(a) >= common[0]}
        print(pd.DataFrame(cr).T.apply(lambda col: col.map(pct)).to_string())
        A, B = st["A. 50% IBS + 50% Trend"], st["B. 50% IBS + 50% Index"]
        dd_ok = A["MaxDD"] >= B["MaxDD"] * (2.0 / 3.0)
        cost_ok = (B["CAGR"] - A["CAGR"]) <= 0.02
        print("")
        print("DECISION RULE (fixed before running): A over B needs drawdown 1/3 smaller AND <= 2%/yr less return")
        print("  Drawdown: A %s vs B %s -> %s" % (pct(A["MaxDD"]), pct(B["MaxDD"]), "PASS" if dd_ok else "FAIL"))
        print("  Return given up: %s a year -> %s" % (pct(B["CAGR"] - A["CAGR"]), "PASS" if cost_ok else "FAIL"))
        print("  -> " + ("CHOOSE A (IBS + Trend)" if dd_ok and cost_ok else "CHOOSE B (IBS + Index)"))


if __name__ == "__main__":
    main()
