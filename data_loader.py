# data_loader.py - shared price download and cleaning
# Downloads daily adjusted prices (yfinance), cleans them and prints a
# data-quality report. Used by the backtest scripts; can also be run on its
# own to download the large-cap universe plus SPY into prices.csv:
#   python3 data_loader.py

import sys
import pandas as pd
import yfinance as yf

# ---------------- settings ----------------
START_DATE = "2008-01-01"   # early enough to include the 2009 momentum crash
BENCHMARK = "SPY"
OUTPUT_FILE = "prices.csv"
MAX_FFILL_DAYS = 5          # only fill short gaps, never long ones
MIN_HISTORY_DAYS = 252      # drop tickers with under ~1 year of data
SUSPICIOUS_MOVE = 0.5       # flag daily moves above 50% as possible data errors

# Large-cap US universe (roughly the S&P 100).
# WARNING: these are TODAY's large caps, so the list has survivorship bias.
# Companies that shrank or went bust since 2008 are missing, which will make
# backtest results look better than reality. We deal with this in Week 2.
UNIVERSE = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AIG", "AMD", "AMGN", "AMT", "AMZN",
    "AVGO", "AXP", "BA", "BAC", "BK", "BKNG", "BLK", "BMY", "BRK-B", "C",
    "CAT", "CHTR", "CL", "CMCSA", "COF", "COP", "COST", "CRM", "CSCO", "CVS",
    "CVX", "DE", "DHR", "DIS", "DUK", "EMR", "F", "FDX", "GD", "GE",
    "GILD", "GM", "GOOGL", "GS", "HD", "HON", "IBM", "INTC", "INTU", "ISRG",
    "JNJ", "JPM", "KO", "LIN", "LLY", "LMT", "LOW", "MA", "MCD", "MDLZ",
    "MDT", "MET", "META", "MMM", "MO", "MRK", "MS", "MSFT", "NEE", "NFLX",
    "NKE", "NOW", "NVDA", "ORCL", "PEP", "PFE", "PG", "PLTR", "PM", "PYPL",
    "QCOM", "RTX", "SBUX", "SCHW", "SO", "SPG", "T", "TGT", "TMO", "TMUS",
    "TSLA", "TXN", "UBER", "UNH", "UNP", "UPS", "USB", "V", "VZ", "WFC",
    "WMT", "XOM",
]


def download_prices(tickers, start):
    """Download adjusted daily closes. Returns a DataFrame: rows = dates, columns = tickers."""
    print("Downloading " + str(len(tickers)) + " tickers from " + start + " ...")
    data = yf.download(tickers, start=start, auto_adjust=True,
                       progress=True, threads=True)
    if data is None or data.empty:
        sys.exit("Download failed - check your internet connection and try again.")

    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"].copy()
    else:
        prices = data[["Close"]].copy()
        prices.columns = tickers

    # Strip timezone (lesson from v7: avoids merge errors later)
    prices.index = pd.to_datetime(prices.index)
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)

    prices = prices.sort_index()
    prices = prices[~prices.index.duplicated(keep="last")]
    return prices


def clean_prices(prices):
    """Remove bad tickers, fill short gaps, flag suspicious moves."""
    report = {}

    # 1. Tickers that returned no data at all
    failed = [t for t in prices.columns if prices[t].dropna().empty]
    prices = prices.drop(columns=failed)
    report["failed"] = failed

    # 2. Fill short gaps only. Days before a stock listed stay empty,
    #    which is correct: it simply was not in the universe yet.
    prices = prices.ffill(limit=MAX_FFILL_DAYS)

    # 3. Tickers with too little history
    too_short = [t for t in prices.columns
                 if t != BENCHMARK and prices[t].count() < MIN_HISTORY_DAYS]
    prices = prices.drop(columns=too_short)
    report["too_short"] = too_short

    # 4. Suspicious daily moves (possible split or data errors)
    daily = prices.pct_change(fill_method=None)
    big = daily.abs() > SUSPICIOUS_MOVE
    report["suspicious"] = {t: int(big[t].sum())
                            for t in daily.columns if big[t].sum() > 0}

    # 5. Tickers that listed after the start date (enter the universe later)
    first_dates = prices.apply(lambda col: col.first_valid_index())
    cutoff = prices.index[0] + pd.Timedelta(days=10)
    report["late_starters"] = {t: d.strftime("%Y-%m-%d")
                               for t, d in first_dates.items() if d > cutoff}
    return prices, report


def print_report(prices, report):
    print("")
    print("========== DATA REPORT ==========")
    print("Date range:      " + prices.index[0].strftime("%Y-%m-%d")
          + " to " + prices.index[-1].strftime("%Y-%m-%d"))
    print("Trading days:    " + str(len(prices)))
    print("Tickers kept:    " + str(prices.shape[1]) + " (incl. " + BENCHMARK + ")")
    print("Failed download: " + (", ".join(report["failed"]) or "none"))
    print("Too short:       " + (", ".join(report["too_short"]) or "none"))
    print("")
    print("Listed after start (join universe later):")
    if report["late_starters"]:
        for t, d in sorted(report["late_starters"].items(), key=lambda x: x[1]):
            print("  " + t.ljust(6) + " from " + d)
    else:
        print("  none")
    print("")
    print("Days with >" + str(int(SUSPICIOUS_MOVE * 100)) + "% moves (check these):")
    if report["suspicious"]:
        for t, n in report["suspicious"].items():
            print("  " + t.ljust(6) + " " + str(n) + " day(s)")
    else:
        print("  none")
    print("=================================")


def main():
    tickers = UNIVERSE + [BENCHMARK]
    prices = download_prices(tickers, START_DATE)
    prices, report = clean_prices(prices)

    if BENCHMARK not in prices.columns:
        sys.exit("Benchmark " + BENCHMARK + " failed to download - try again.")

    print_report(prices, report)
    prices.to_csv(OUTPUT_FILE, float_format="%.4f")
    print("Saved " + OUTPUT_FILE + " (" + str(prices.shape[0]) + " rows x "
          + str(prices.shape[1]) + " columns)")


if __name__ == "__main__":
    main()
