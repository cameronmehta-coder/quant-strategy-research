# ibs_signal.py - Strategy 3 daily signal for PAPER TRADING (USA 500 CFD)
#
# Run once each US trading day, about 10-15 minutes before the US close
# (normally 20:45 UK; the script tells you the exact UK time each day).
#
#   cd ~/Documents/Trading/portfolio
#   python3 ibs_signal.py
#
# It reads today's SPY high, low and latest price, computes IBS, and tells you
# what to do in the Trading 212 CFD PRACTICE account. After you trade, it asks
# for your fill price and logs everything to ibs_log.csv (the drift monitor).
#
# Rules (same as the backtest, trial 1):
#   Flat:    IBS < 0.2                     -> BUY  (value = account cash, NO leverage)
#   Holding: IBS > 0.8 or held 5 days      -> SELL (close the whole position)
#   Otherwise                              -> do nothing
#
# Safety:
#   - Create a file called STOP in this folder to pause the script completely.
#   - It refuses to signal if the data looks wrong or the market is closed.
#   - It never signals twice on the same day.

import csv
import json
import os
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

ENTRY_IBS = 0.2
EXIT_IBS = 0.8
MAX_HOLD_DAYS = 5
INSTRUMENT = "USA 500"        # the only instrument this script may trade
SIGNAL_TICKER = "SPY"
STATE_FILE = "ibs_state.json"
LOG_FILE = "ibs_log.csv"
STOP_FILE = "STOP"

NY = ZoneInfo("America/New_York")
UK = ZoneInfo("Europe/London")
WINDOW_START = time(15, 40)   # New York time: best window to run
WINDOW_END = time(15, 58)
LOG_FIELDS = ["date", "time_uk", "spy_high", "spy_low", "spy_last", "ibs",
              "action", "days_held", "value_gbp", "cfd_fill", "note"]


# ---------------- state and log ----------------
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"holding": False, "entry_date": None, "entry_fill": None,
            "value_gbp": None, "cash_gbp": None}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        return list(csv.DictReader(f))


def append_log(row):
    new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_FIELDS})


# ---------------- market data ----------------
def fetch_today():
    """Today's regular-session minute bars for SPY, in New York time."""
    import yfinance as yf
    bars = yf.Ticker(SIGNAL_TICKER).history(period="1d", interval="1m", prepost=False)
    daily = yf.Ticker(SIGNAL_TICKER).history(period="1mo", interval="1d")
    return bars, daily


def check_data(bars, now_ny):
    """Return (ok, message, high, low, last)."""
    if bars is None or bars.empty:
        return False, "No intraday data returned.", None, None, None
    idx = bars.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    idx = idx.tz_convert(NY)
    bars = bars.copy()
    bars.index = idx
    if idx[-1].date() != now_ny.date():
        return False, "Data is from %s, not today - market closed today?" % idx[-1].date(), None, None, None
    session = bars.between_time("09:30", "15:59")
    if session.empty:
        return False, "No regular-session bars yet.", None, None, None
    hi = float(session["High"].max())
    lo = float(session["Low"].min())
    last = float(session["Close"].iloc[-1])
    age = (now_ny - session.index[-1]).total_seconds() / 60.0
    if age > 15:
        return False, "Latest price is %.0f minutes old - data is stale." % age, hi, lo, last
    if not (hi > lo > 0):
        return False, "High/low look wrong (high %.2f, low %.2f)." % (hi, lo), hi, lo, last
    if not (lo - 0.01 <= last <= hi + 0.01):
        return False, "Latest price is outside today's range.", hi, lo, last
    return True, "ok", hi, lo, last


def trading_days_held(daily, entry_date, today):
    """Trading days since entry, counting today (entry day = 0)."""
    days = sorted({d.date() for d in daily.index})
    if today not in days:
        days.append(today)
    e = datetime.strptime(entry_date, "%Y-%m-%d").date()
    return sum(1 for d in days if e < d <= today)


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def ask_number(prompt):
    while True:
        s = ask(prompt)
        if s == "":
            return None
        try:
            v = float(s.replace(",", "").replace("$", "").replace("GBP", "").replace(chr(163), ""))
            if v > 0:
                return v
        except ValueError:
            pass
        print("  Please type a number, or press Enter to skip.")


# ---------------- summary ----------------
def print_summary(log):
    trades, open_buy = [], None
    for r in log:
        if r["action"] == "BUY" and r["cfd_fill"]:
            open_buy = r
        elif r["action"] == "SELL" and r["cfd_fill"] and open_buy:
            ret = float(r["cfd_fill"]) / float(open_buy["cfd_fill"]) - 1.0
            trades.append(ret)
            open_buy = None
    if trades:
        wins = sum(1 for t in trades if t > 0)
        total = 1.0
        for t in trades:
            total *= 1.0 + t
        print("Paper record: %d closed trades, %d winners, average %.2f%%, total %.2f%% (before costs)"
              % (len(trades), wins, 100 * sum(trades) / len(trades), 100 * (total - 1.0)))
    else:
        print("Paper record: no closed trades yet.")


def current_time():
    return datetime.now(NY)


def finish_pending(prev, today):
    """Record the fill for a BUY or SELL signalled earlier today."""
    state = load_state()
    side = "BUY" if prev["action"] == "BUY_PENDING" else "SELL"
    print("Earlier today the signal was %s, but no fill was recorded." % side)
    fill = ask_number("Type the %s price shown in the app (Enter if you did NOT trade): " % side)
    row = dict(prev)
    row["time_uk"] = current_time().astimezone(UK).strftime("%H:%M")
    if not fill:
        row["action"] = side + "_SKIPPED"
        row["note"] = "signal not traded"
        print("Logged as not traded. Position unchanged.")
    elif side == "BUY":
        row.update({"action": "BUY", "cfd_fill": fill, "note": "fill recorded later"})
        state.update({"holding": True, "entry_date": str(today), "entry_fill": fill,
                      "value_gbp": float(prev["value_gbp"]) if prev.get("value_gbp") else state.get("cash_gbp")})
        save_state(state)
        print("Position marked OPEN.")
    else:
        row.update({"action": "SELL", "cfd_fill": fill, "note": "fill recorded later"})
        if state.get("entry_fill"):
            print("Trade result: %.2f%% (before costs)" % (100 * (fill / float(state["entry_fill"]) - 1.0)))
        state.update({"holding": False, "entry_date": None, "entry_fill": None, "value_gbp": None})
        save_state(state)
        print("Position marked CLOSED.")
    append_log(row)
    print_summary(read_log())


# ---------------- main ----------------
def main():
    print("")
    print("=" * 64)
    print("IBS DAILY SIGNAL - PAPER TRADING (" + INSTRUMENT + " CFD, practice account)")
    print("=" * 64)

    if os.path.exists(STOP_FILE):
        print("STOPPED: a file called STOP exists in this folder. Delete it to resume.")
        return

    now_ny = current_time()
    today = now_ny.date()
    close_ny = datetime.combine(today, time(16, 0), tzinfo=NY)
    close_uk = close_ny.astimezone(UK)
    print("US close today: %s UK time. Run between %s and %s UK."
          % (close_uk.strftime("%H:%M"),
             datetime.combine(today, WINDOW_START, tzinfo=NY).astimezone(UK).strftime("%H:%M"),
             datetime.combine(today, WINDOW_END, tzinfo=NY).astimezone(UK).strftime("%H:%M")))

    log = read_log()
    todays = [r for r in log if r["date"] == str(today)]
    if any(r["action"] in ("BUY", "SELL", "HOLD", "NOTHING") for r in todays):
        print("Already signalled today - see ibs_log.csv. Nothing to do.")
        print_summary(log)
        return
    pending = [r for r in todays if r["action"] in ("BUY_PENDING", "SELL_PENDING")]
    if pending:
        finish_pending(pending[-1], today)
        return

    if now_ny.weekday() >= 5:
        print("Weekend - US market closed. Nothing to do.")
        return
    t = now_ny.time()
    if t >= time(16, 0):
        print("US market has CLOSED. Today's signal can no longer be traded at the close.")
        print("Run earlier tomorrow. (Missed days are logged as notes only.)")
        return
    if t < time(9, 30):
        print("US market not open yet.")
        return
    if not (WINDOW_START <= t <= WINDOW_END):
        print("WARNING: outside the best window - the day's range may still change.")
        if ask("Continue anyway? (y/n): ").lower() != "y":
            return

    try:
        bars, daily = fetch_today()
    except Exception as e:
        print("NO SIGNAL - download failed: %s" % e)
        return
    ok, msg, hi, lo, last = check_data(bars, now_ny)
    if not ok:
        print("NO SIGNAL - data check failed: " + msg)
        append_log({"date": today, "time_uk": now_ny.astimezone(UK).strftime("%H:%M"),
                    "action": "DATA_FAIL", "note": msg})
        return

    ibs = (last - lo) / (hi - lo)
    print("")
    print("SPY today: high %.2f  low %.2f  latest %.2f   ->  IBS = %.2f" % (hi, lo, last, ibs))

    state = load_state()
    row = {"date": today, "time_uk": now_ny.astimezone(UK).strftime("%H:%M"),
           "spy_high": "%.2f" % hi, "spy_low": "%.2f" % lo, "spy_last": "%.2f" % last,
           "ibs": "%.3f" % ibs}

    if state["holding"]:
        held = trading_days_held(daily, state["entry_date"], today)
        row["days_held"] = held
        print("Position: HOLDING since %s (%d trading days)." % (state["entry_date"], held))
        if ibs > EXIT_IBS or held >= MAX_HOLD_DAYS:
            reason = "IBS above %.1f" % EXIT_IBS if ibs > EXIT_IBS else "%d-day time limit" % MAX_HOLD_DAYS
            print("")
            print(">>> SELL: close your whole %s position now (%s)." % (INSTRUMENT, reason))
            fill = ask_number("After closing, type the SELL price shown in the app (Enter to skip): ")
            row.update({"action": "SELL", "cfd_fill": fill or "", "value_gbp": state.get("value_gbp", ""),
                        "note": reason if fill else reason + "; fill not recorded"})
            if fill:
                ret = fill / float(state["entry_fill"]) - 1.0 if state.get("entry_fill") else None
                if ret is not None:
                    print("Trade result: %.2f%% (before costs)" % (100 * ret))
                state.update({"holding": False, "entry_date": None, "entry_fill": None, "value_gbp": None})
                save_state(state)
            else:
                print("Position NOT marked closed. Run again today after you trade to record it.")
                row["action"] = "SELL_PENDING"
        else:
            print("")
            print(">>> HOLD: keep the position. Nothing to do today.")
            row["action"] = "HOLD"
    else:
        if ibs < ENTRY_IBS:
            cash = ask_number("Practice account cash in GBP (Enter = %s): "
                              % (state.get("cash_gbp") or "not set"))
            cash = cash or state.get("cash_gbp")
            if not cash:
                print("NO TRADE - account cash is needed to size the position.")
                return
            print("")
            print(">>> BUY: %s, VALUE GBP %.2f (equal to cash - no leverage)." % (INSTRUMENT, cash))
            print("    Check: the order's VALUE must not be above GBP %.2f." % cash)
            fill = ask_number("After buying, type the BUY price shown in the app (Enter to skip): ")
            row.update({"action": "BUY", "value_gbp": "%.2f" % cash, "cfd_fill": fill or "",
                        "days_held": 0})
            state["cash_gbp"] = cash
            if fill:
                state.update({"holding": True, "entry_date": str(today), "entry_fill": fill,
                              "value_gbp": cash})
            else:
                print("Position NOT marked open. Run again today after you trade to record it.")
                row["action"] = "BUY_PENDING"
            save_state(state)
        else:
            print("")
            print(">>> NOTHING: no position, no signal today (IBS not below %.1f)." % ENTRY_IBS)
            row["action"] = "NOTHING"

    append_log(row)
    print("")
    print("Logged to " + LOG_FILE + ".")
    print_summary(read_log())


if __name__ == "__main__":
    main()
