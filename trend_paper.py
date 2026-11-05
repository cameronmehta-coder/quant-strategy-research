# trend_paper.py - Strategy 1 (trend, long-only) MONTHLY PAPER TRACKING
#
# The fund's defensive sleeve (discretionary allocation, 4 Nov 2026):
#   GBP 500 fund = about GBP 333 IBS (CFD) + about GBP 167 trend (ISA).
# Trend is paper-tracked first. Rules = trend trial 1 (see trials-log.md):
#   each month-end, inverse-volatility slots (63-day) across 8 ETFs; an asset
#   fills its slot only if its 12-month return beats cash (SHY), else cash.
#
# Run ONCE A MONTH, on the evening of the last US trading day of the month
# (after 21:00 UK) or any day in the following week:
#   cd ~/Documents/Trading/portfolio
#   python3 trend_paper.py
#
# It downloads fresh prices, values the paper portfolio since the last
# rebalance, prints the new target holdings in GBP, and logs everything.
# Paper tracking uses the US ETF proxies (as in the backtest). Before going
# live we map each one to a London-listed UCITS fund available in the ISA.

import json
import os
import sys
import numpy as np
import pandas as pd

import trend_backtest as tb
from data_loader import download_prices, clean_prices

START_CAPITAL = 167.0
COST_PER_SIDE = 0.001
STATE_FILE = "trend_paper_state.json"
LOG_FILE = "trend_paper_log.csv"
BENCH = "SPY"


def today():
    return pd.Timestamp.today().normalize()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return None


def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2)


def main():
    print("")
    print("=" * 66)
    print("TREND SLEEVE - MONTHLY PAPER TRACKING (long-only, 8 ETFs)")
    print("=" * 66)
    prices = download_prices(tb.ALL_COLS, "2004-01-01")
    prices, _ = clean_prices(prices)
    missing = [t for t in tb.ALL_COLS if t not in prices.columns]
    if missing:
        sys.exit("Download incomplete (%s) - try again later." % ", ".join(missing))
    prices = prices[tb.ALL_COLS]
    me = tb.month_end_dates(prices)
    signal_date = me[-1]

    state = load_state()
    if state is None and (today() - signal_date).days > 7:
        nxt = (signal_date + pd.offsets.BMonthEnd(1)).date()
        print("The first paper rebalance must be run within a week of a month-end,")
        print("so it is not back-dated. Last month-end was %s." % signal_date.date())
        print("Start on the evening of %s (after 21:00 UK) or in the week after." % nxt)
        return
    if state and state["last_rebalance"] >= str(signal_date.date()):
        print("Already rebalanced for month-end %s. Next run: after the last US trading"
              " day of next month." % state["last_rebalance"])
        print("Paper value: GBP %.2f (started GBP %.2f on %s)"
              % (state["value"], START_CAPITAL, state["start_date"]))
        return

    w = tb.make_weights(prices, me, 12).loc[signal_date, tb.ALL_COLS]
    if abs(w.sum() - 1.0) > 1e-6 or (w < -1e-9).any():
        sys.exit("Weights failed a sanity check - nothing logged.")

    # 1. Value the paper portfolio since the last rebalance (buy and hold).
    if state is None:
        value = START_CAPITAL
        bench_units = None
        print("First run: starting paper portfolio with GBP %.2f." % value)
        old_w = pd.Series(0.0, index=tb.ALL_COLS)
        month_ret = 0.0
    else:
        prev = pd.Timestamp(state["last_rebalance"])
        old_w = pd.Series(state["weights"])
        growth = (prices.loc[signal_date, tb.ALL_COLS] / prices.loc[prev, tb.ALL_COLS]).fillna(1.0)
        gross = float((old_w * growth).sum())
        month_ret = gross - 1.0
        value = state["value"] * gross
        drifted = old_w * growth / gross
        old_w = drifted

    # 2. Rebalance to the new targets (cost on non-cash turnover).
    turnover = float((w - old_w).abs()[tb.ASSETS].sum())
    cost = value * turnover * COST_PER_SIDE
    value -= cost

    if state is None:
        start_date = str(signal_date.date())
        bench_start = float(prices.loc[signal_date, BENCH])
    else:
        start_date = state["start_date"]
        bench_start = state["bench_start"]
    bench_value = START_CAPITAL * float(prices.loc[signal_date, BENCH]) / bench_start

    print("Month-end: %s" % signal_date.date())
    if state is not None:
        print("Last month: %+.2f%%  | paper value GBP %.2f  (SPY buy-and-hold: GBP %.2f)"
              % (100 * month_ret, value, bench_value))
    print("Rebalance cost: GBP %.2f (turnover %.0f%%)" % (cost, 100 * turnover))
    print("")
    print("NEW TARGET HOLDINGS (paper - do not trade real money yet)")
    print("  %-4s %-26s %7s %9s %10s" % ("", "Asset", "Weight", "GBP", "Change"))
    for t in tb.ALL_COLS:
        label = tb.UNIVERSE.get(t, "Cash (short-term bonds)")
        chg = (w[t] - old_w.get(t, 0.0)) * value
        print("  %-4s %-26s %6.1f%% %9.2f %+10.2f" % (t, label, 100 * w[t], w[t] * value, chg))

    row = {"month_end": str(signal_date.date()), "value_gbp": round(value, 2),
           "month_return": round(month_ret, 5), "cost_gbp": round(cost, 2),
           "spy_value_gbp": round(bench_value, 2)}
    row.update({"w_" + t: round(float(w[t]), 4) for t in tb.ALL_COLS})
    new = not os.path.exists(LOG_FILE)
    pd.DataFrame([row]).to_csv(LOG_FILE, mode="a", header=new, index=False)
    save_state({"start_date": start_date, "bench_start": bench_start,
                "last_rebalance": str(signal_date.date()), "value": value,
                "weights": {t: float(w[t]) for t in tb.ALL_COLS}})
    print("")
    print("Logged to %s. Next run: after the last US trading day of next month." % LOG_FILE)


if __name__ == "__main__":
    main()
