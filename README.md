# Quant Strategy Research

Testing systematic trading strategies used by asset managers and hedge funds, the way a fund's research team would: rules and pass/fail criteria are fixed **before** each backtest is run, every attempt is logged (including failures), and only a strategy that passes is paper-traded.

Built in Python with free daily data (yfinance), by Cameron Mehta.

## Results so far (6 trials, 3 strategies)

| Strategy | Source | Trials | Result |
|---|---|---|---|
| Multi-asset trend following | Kakushadze & Serur (2018) 4.6, 10.4; Hurst, Ooi & Pedersen (2017) | 3 | **Closed.** Long-only halved drawdowns (-11% vs -21%, +11% in the 2008 crash) but did not improve risk-adjusted return. Long-short via CFDs gave strong crash protection (+32% in 2008) but financing and bull-market whipsaws left it below cash. |
| Low-volatility US equities | Kakushadze & Serur 3.4; Blitz & van Vliet (2018) | 2 | **Closed.** Own backtest failed but was biased by survivorship; real low-vol funds (SPLV, USMV) confirmed it: Sharpe 0.65-0.79 vs SPY 0.82 since 2011, alpha about zero. |
| IBS mean reversion on the S&P 500 | Kakushadze & Serur 4.4; Pagonidis (2014) | 1 | **Passed all five checks.** After publication (Jun 2013 onwards): +0.27% per trade after costs (t = 3.2), Sharpe 0.69, max drawdown -16% vs SPY -34%, +19.6% in 2022. Paper trading from Nov 2026. |

**Research note (2 pages): [docs/research-note.md](docs/research-note.md)**

Full details of every trial, including the checks set in advance: [docs/trials-log.md](docs/trials-log.md).

## What the failures taught

- **A technique belongs to a strategy, not to "professional trading".** Stop-losses help trend following and hurt mean reversion (Kaminski & Lo, 2014). See [docs/fund-practices.md](docs/fund-practices.md).
- **Survivorship bias is not neutral.** Testing on today's large caps flattered high-volatility winners and penalised low volatility specifically.
- **Where you trade matters.** IBS works on the US-listed S&P 500 ETF but not on the London-listed one, whose trading day barely overlaps the US close.
- **Ten years of data cannot separate small Sharpe differences** (noise of about 0.2), so pre-registered checks need to be built with significance in mind.
- **Stop when the pre-registered test fails.** Re-tuning on a test period you have already seen is data mining.

## Files

| File | Purpose |
|---|---|
| `data_loader.py` | Shared price download and cleaning, with a data-quality report |
| `trend_backtest.py` | Trend following, trials 1-2 (`--trial 1` or `--trial 2`) |
| `trend_ls_backtest.py` | Trend following, trial 3 (long-short with CFD costs) |
| `lowvol_backtest.py` | Low volatility, trial 1 |
| `lowvol_etf_check.py` | Low volatility, trial 2 (real funds) |
| `ibs_backtest.py` | IBS mean reversion backtest |
| `ibs_signal.py` | Daily IBS signal for paper trading, with data checks, a kill switch and a fill log |

## How to run

Python 3 with `pandas`, `numpy`, `yfinance` and `matplotlib`:

```
pip3 install pandas numpy yfinance matplotlib
python3 trend_backtest.py --download
python3 ibs_backtest.py --download
```

Each backtest prints its results, the pre-registered go-live checks (PASS/FAIL) and saves a chart.

## Method

- Train and test periods are fixed in advance; for IBS the test starts after the original paper was published.
- Costs, a one-day execution lag and realistic broker fees are included.
- Robustness: each strategy must also work for nearby parameter settings, not just the chosen one.
- Every variant tried is logged, for an honest multiple-testing adjustment.

## Disclaimer

Personal research and learning. Not investment advice. Past and backtested performance does not predict future returns.
