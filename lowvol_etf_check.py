# lowvol_etf_check.py - Strategy 2, TRIAL 2: do real low-volatility funds work?
#
# Real funds have no survivorship bias and their returns already include costs.
#   SPLV = Invesco S&P 500 Low Volatility (100 least volatile S&P 500 stocks)
#   USMV = iShares MSCI USA Min Vol (optimised minimum-variance portfolio)
#   SPY  = S&P 500 (the parent market); RSP = equal-weight S&P 500 (information)
#
# Checks (fixed 3 Nov 2026 before running - see trials-log.md):
#   1. SPLV Sharpe above SPY          2. USMV Sharpe above SPY
#   3. Both funds' volatility at least 20% below SPY
#   4. Both funds' max drawdown smaller than SPY's
#   5. Both funds' CAPM alpha (vs SPY) positive
#   Checks 1-4 must pass to justify the bigger point-in-time rebuild (option B).
#
# Run: python3 lowvol_etf_check.py

import sys
import numpy as np
import pandas as pd

TICKERS = ["SPLV", "USMV", "SPY", "RSP"]
START = "2011-01-01"
SPLIT = "2016-12-31"
CRISES = {"2015-16 sell-off": ("2015-07-20", "2016-02-11"),
          "Q4 2018": ("2018-09-20", "2018-12-24"),
          "COVID 2020": ("2020-02-19", "2020-03-23"),
          "COVID recovery": ("2020-03-23", "2020-12-31"),
          "2022 rate shock": ("2022-01-03", "2022-12-30"),
          "2023 rally": ("2023-01-03", "2023-12-29")}


def download():
    import yfinance as yf
    px = yf.download(TICKERS, start=START, auto_adjust=True, progress=False)["Close"]
    r = yf.download("^IRX", start=START, auto_adjust=False, progress=False)
    if isinstance(r.columns, pd.MultiIndex):
        r.columns = r.columns.get_level_values(0)
    for d in (px, r):
        d.index = pd.to_datetime(d.index)
        if d.index.tz is not None:
            d.index = d.index.tz_localize(None)
    px["RatePct"] = r["Close"].reindex(px.index).ffill().fillna(0.0)
    return px


def stats(r, c, mkt):
    eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    ex, mx = r - c, mkt - c
    beta = ex.cov(mx) / mx.var()
    alpha_d = ex.mean() - beta * mx.mean()
    resid = ex - (alpha_d + beta * mx)
    sd = resid.std()
    t_alpha = alpha_d / (sd / np.sqrt(len(r))) if sd > 1e-12 else float("nan")
    return {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "Vol": r.std() * np.sqrt(252),
            "Sharpe": ex.mean() / ex.std() * np.sqrt(252),
            "MaxDD": (eq / eq.cummax() - 1).min(), "Beta": beta,
            "Alpha": alpha_d * 252, "Alpha t": t_alpha}


def show(rows):
    out = {}
    for k, s in rows.items():
        out[k] = {"CAGR": "%.1f%%" % (100 * s["CAGR"]), "Vol": "%.1f%%" % (100 * s["Vol"]),
                  "Sharpe": "%.2f" % s["Sharpe"], "MaxDD": "%.1f%%" % (100 * s["MaxDD"]),
                  "Beta": "%.2f" % s["Beta"], "Alpha/yr": "%.1f%%" % (100 * s["Alpha"]),
                  "Alpha t": "%.1f" % s["Alpha t"]}
    return pd.DataFrame(out).T.to_string()


def main():
    px = download()
    funds = [t for t in TICKERS if t in px.columns]
    if "SPY" not in funds or "SPLV" not in funds or "USMV" not in funds:
        sys.exit("Download incomplete - try again.")
    px = px.dropna(subset=["SPLV", "USMV", "SPY"])
    rets = px[funds].pct_change().dropna()
    cash = ((1 + px["RatePct"] / 100) ** (1 / 252) - 1).reindex(rets.index)

    print("")
    print("=" * 74)
    print("STRATEGY 2: LOW VOLATILITY - TRIAL 2 - REAL FUNDS (no survivorship bias)")
    print("=" * 74)
    periods = {"FULL %s to %s" % (rets.index[0].strftime("%Y-%m"), rets.index[-1].strftime("%Y-%m")):
               (rets.index[0], rets.index[-1]),
               "2011-2016": (rets.index[0], pd.Timestamp(SPLIT)),
               "2017 onwards": (pd.Timestamp(SPLIT) + pd.Timedelta(days=1), rets.index[-1])}
    full = {}
    for name, (a, b) in periods.items():
        r, c = rets.loc[a:b], cash.loc[a:b]
        rows = {t: stats(r[t], c, r["SPY"]) for t in funds}
        if name.startswith("FULL"):
            full = rows
        print("")
        print(name)
        print(show(rows))

    print("")
    print("EPISODES (total return)")
    ep = {n: {t: (1 + rets[t].loc[a:b]).prod() - 1 for t in funds} for n, (a, b) in CRISES.items()}
    print(pd.DataFrame(ep).T.apply(lambda col: col.map(lambda x: "%.1f%%" % (100 * x))).to_string())

    print("")
    print("YEARLY RETURNS")
    yr = (1 + rets).groupby(rets.index.year).prod() - 1
    print(yr.apply(lambda col: col.map(lambda x: "%.1f%%" % (100 * x))).to_string())

    s, u, m = full["SPLV"], full["USMV"], full["SPY"]
    checks = [("1. SPLV Sharpe above SPY", s["Sharpe"] > m["Sharpe"]),
              ("2. USMV Sharpe above SPY", u["Sharpe"] > m["Sharpe"]),
              ("3. Both volatilities at least 20% below SPY", s["Vol"] <= 0.8 * m["Vol"] and u["Vol"] <= 0.8 * m["Vol"]),
              ("4. Both max drawdowns smaller than SPY's", s["MaxDD"] > m["MaxDD"] and u["MaxDD"] > m["MaxDD"]),
              ("5. Both CAPM alphas positive", s["Alpha"] > 0 and u["Alpha"] > 0)]
    print("")
    print("CHECKS (fixed before seeing results)")
    for label, ok in checks:
        print("  " + ("PASS  " if ok else "FAIL  ") + label)
    go = all(ok for _, ok in checks[:4])
    print("  -> " + ("Checks 1-4 pass: worth the point-in-time rebuild (option B)."
                     if go else "Checks 1-4 not all passed: option B not justified."))


if __name__ == "__main__":
    main()
