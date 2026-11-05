# Trials Log

Every strategy variant tested goes here, including failures. Rules and pass/fail checks were written down before each trial was run on real data. Needed for the multiple-testing haircut (Harvey & Liu) and the Deflated Sharpe Ratio. Never delete a row.

Summary (3 Nov 2026): 6 trials across 3 strategies. Trend: 3 trials, all failed - CLOSED. Low vol: 2 trials, both failed (trial 2 on real funds confirms trial 1 was not just survivorship bias) - CLOSED. IBS: 1 trial, passed all checks on SPY - PAPER TRADING on a USA 500 CFD.

## Strategy 1: Multi-asset trend following - CLOSED after 3 trials

### Trial 1 (3 Nov 2026) - v1 as pre-registered
- Rules: 12-month return vs cash on/off, inverse-vol slots (63-day), monthly, 1-day lag, 0.10% cost per side
- Data: yfinance, 2005-01 onwards; evaluation from 2007-03; train to 2016, test 2017-Oct 2026
- Data check: 12-month returns to 30 Oct 2026 confirmed against Yahoo/Google (GLD -3.4%, DBC +51.8%)
- Test period: Trend CAGR 4.7%, vol 5.8%, Sharpe 0.55, MaxDD -11.0% | Static CAGR 6.3%, Sharpe 0.59, MaxDD -20.6% | 60/40 Sharpe 0.75 | SPY Sharpe 0.75, MaxDD -33.7%
- Full period: Trend Sharpe 0.50, MaxDD -11.0% | Static 0.51, -21.6% | SPY 0.52, -55.2%
- Crises: GFC Trend +11.1% vs SPY -55.2%; COVID -6.1% vs -33.7%; 2022 -9.5% vs -18.6%
- Grid (test Sharpe, inv-vol): 3m 0.63, 6m 0.54, 9m 0.74, 12m 0.55 vs Static 0.59 - beats Static in 2 of 4
- Costs: turnover 198% a year, drag 0.2% a year
- Go-live checks: FAIL 1, PASS 2, FAIL 3 (2/4), PASS 4, PASS 5
- VERDICT: does not go live. Halved drawdowns, protected in the GFC, cost about 1.6% a year of return, Sharpe unchanged within noise (about 0.2 for 10 years).

### Trial 2 (3 Nov 2026) - blended 3/6/12 signal, rules fixed before running
- Rules: as trial 1, but 3-, 6- and 12-month returns each vote on/off vs cash; asset fills the average of the votes
- Test period: Trend CAGR 4.7%, vol 5.4%, Sharpe 0.61, MaxDD -9.0% | Static 6.3%, 0.59, -20.6%
- Train period: Trend Sharpe 0.39 vs Static 0.43
- Crises: GFC +8.0%; COVID -3.7%; 2022 -7.3%
- Neighbours: 2 of 4 (1/3/12 no; 3/6/9/12 yes; equal slots tie = no; 126-day vol yes)
- Go-live checks: PASS 1 (within noise), PASS 2, FAIL 3, PASS 4, PASS 5
- VERDICT: does not go live. Same picture as trial 1.

### Trial 3 (3 Nov 2026) - long-short via CFDs, rules fixed before running
- Universe = Trading 212 CFD markets, US ETF proxies: SPY (USA 500), FEZ (EU50), VWO (VWO), TLT (USBOND), GLD (Gold), USO (CRUDE)
- Rules: trial 1's 12-month signal. Inverse-vol slots summing to 100% of capital, no leverage. Above cash -> long (ISA ETF, 0.10% per side); below -> short (CFD)
- Short costs: overnight interest about 5.1% a year, spread 0.05% per side, 0.5% FX on P&L, no interest on cash posted against shorts
- TEST: Long-short CAGR 0.8%, vol 9.2%, Sharpe -0.06, MaxDD -29.8% | Long-only same markets 6.9%, 0.67, -14.0% | Static 9.1%, 0.70, -24.4% | SPY 14.9%, 0.76
- TRAIN: Long-short Sharpe -0.28 vs long-only 0.21
- FULL: Long-short CAGR -0.8%, MaxDD -54.5%
- Crises: GFC +32.1% (SPY -55.2%); COVID +6.5% (SPY -33.7%); 2022 -11.7% (no help)
- Whipsaw years: 2009 -19.8%, 2011 -14.3%, 2016 -12.1%, 2019 -4.5%
- Shorts: average 34% of capital short; 92% of months had a short
- Costs (test): turnover 345% a year, drag 2.4% a year; excess over cash -1.0% a year (gross about +1.4%)
- Robustness: 0 of 4 lookbacks beat long-only (3m 0.02 vs 0.81; 6m -0.08 vs 0.64; 9m 0.01 vs 0.77; 12m -0.06 vs 0.67)
- Go-live checks: all 5 FAIL
- VERDICT: does not go live. Shorting added excellent crash protection but lost money the rest of the time; financing plus costs took 2.4% a year; 6 markets is too little breadth.

### Conclusion: trend research closed
- Long-only trend = drawdown reducer with no extra risk-adjusted return. Long-short trend = crisis insurance too expensive at retail CFD costs and 6 markets.
- Revisit only with genuinely new conditions (many more markets, futures-level costs), pre-registered from scratch.

## Strategy 3: IBS mean reversion - PAPER TRADING

### Trial 1 (3 Nov 2026) - rules fixed before running
- Instrument: SPY daily OHLC (yfinance, Feb 1993 onwards); cash earns 13-week T-bill (^IRX)
- Rules: buy at the close when IBS < 0.2 (if flat); sell at the close when IBS > 0.8 or after 5 days; no price stop; 0.05% cost per side
- Train: Feb 1993 - May 2013 (end of Pagonidis' sample). Test: Jun 2013 onwards (after publication)
- TEST (close entry): CAGR 9.0%, vol 10.9%, Sharpe 0.69, MaxDD -16.2%, 29 trades/yr, avg trade +0.27% (t = 3.2), win rate 66%, in market 31% | SPY: CAGR 14.0%, Sharpe 0.75, MaxDD -33.7%
- TRAIN: CAGR 9.9%, Sharpe 0.57, avg trade +0.25% (t = 3.2)
- Costs (test): 0% Sharpe 0.95; 0.05% 0.69; 0.10% 0.42; 0.20% -0.12
- Variant B (200-day filter): test Sharpe 0.38 vs 0.69 - NOT adopted
- Variant C (next-open entry): avg trade 0.17% vs 0.27% (keeps 63%)
- Go-live checks: all 5 PASS
- INFO: same rules on VUSA.L (London-listed): Sharpe 0.11, avg trade +0.06%, t = 0.8 - the edge does NOT appear on the London ETF, whose trading day barely overlaps the US close
- VERDICT: edge confirmed on SPY after publication; must be traded at the US close (USA 500 CFD), not via a London-listed ETF.

### Implementation costs (Trading 212 USA 500 CFD, checked 3 Nov 2026)
- Spread about 0.007% round trip; overnight interest about 3% a year (long), about 5.1% (short); 0.5% FX fee on profit or loss
- Estimated cost per IBS round trip about 0.05% (about 0.025% per side) - half the backtest assumption
- Rule: no leverage - position size never above account cash
- Unmodelled: trading about 10 minutes before the close; US close is 20:00 UK for about 3 weeks in March (handled by ibs_signal.py)

### Paper trading (started 3 Nov 2026)
- ibs_signal.py run about 20:45 UK each US trading day in a CFD practice account; every signal and fill logged
- Go-live (fixed 3 Nov 2026): 3 months of paper trading; no more than 3 missed signal days; no rule breaks or leverage; average fill gap vs model under 0.05%. Then live with GBP 200. These test the process, not profitability (about 7 trades in 3 months is too few to judge returns)

## Strategy 2: Low volatility - CLOSED after 2 trials

### Trial 1 (3 Nov 2026) - own rules on today's large caps
- Rules: each quarter-end, rank by volatility of the last 36 monthly returns; hold the 25 lowest, equal weight, at most 6 per sector; buffer rank 35; trade 1 day later; 0.25% cost per side. 101 stocks
- TEST: Low vol CAGR 11.1%, vol 15.1%, Sharpe 0.62, MaxDD -33.3%, beta 0.66 | EW universe 17.1%, 17.6%, 0.85, -33.9% | SPY 14.8%, 18.1%, 0.72, -33.7%
- TRAIN: Low vol Sharpe 0.59 vs EW 0.67
- Crises: GFC -40.1% (SPY -55.2%); COVID -33.2% (same as market); 2022 -4.7% (SPY -18.6%)
- Neighbours: 0 of 4 beat EW
- Go-live checks: FAIL 1, FAIL 2 (vol only 14% lower), PASS 3, FAIL 4 (0/4), PASS 5
- VERDICT: does not go live. Survivorship bias (today's large caps include past high-volatility winners such as NVDA and TSLA) tilted the test against low vol, so judged inconclusive pending trial 2.

### Trial 2 (3 Nov 2026) - real low-vol funds, rules fixed before running
- Funds: SPLV (S&P 500 Low Volatility), USMV (MSCI USA Min Vol) vs SPY; RSP for information. Oct 2011 - Nov 2026
- FULL: SPLV CAGR 10.4%, vol 14.3%, Sharpe 0.65, MaxDD -36.3%, beta 0.67, alpha 0.0% | USMV 11.8%, 13.3%, 0.79, -33.1%, beta 0.71, alpha +0.8% (t 0.5) | SPY 14.9%, 16.6%, 0.82, -33.7%
- 2011-2016: low vol WON (Sharpe SPLV 1.14, USMV 1.29 vs SPY 1.08)
- 2017 onwards: low vol LOST (SPLV 0.46, USMV 0.60 vs SPY 0.73)
- Episodes: protected in the 2015-16 sell-off (-2% vs -13%), Q4 2018 (-10% vs -19%) and 2022 (-5% vs -18%); fell as much as SPY in COVID (-36% vs -33%); lagged the COVID recovery (+38% vs +66%) and 2023 (+0.5% vs +26%)
- Checks: FAIL 1, FAIL 2, FAIL 3, FAIL 4, PASS 5 (alphas about zero, not significant)
- VERDICT: low vol did not beat the market risk-adjusted in investable form since 2011. Trial 1 was not just survivorship bias. A point-in-time rebuild is not justified.

## Portfolio construction (4 Nov 2026) - what sits alongside IBS?

Not a new strategy trial: both sleeves were already tested, so this measures known costs and benefits. Decision rule written in the script before running.

- Options (50/50, sleeves rebalanced yearly): A = IBS + long-only trend (trial 1 rules); B = IBS + S&P 500 index; C = IBS alone; D = index alone. 2007-03 to 2026-11
- Decision rule: choose A over B only if A's max drawdown is at least a third smaller AND A gives up no more than 2% a year of return
- Results (IBS idle cash earning T-bills; the cautious no-interest case was about 0.5% a year lower and gave the same decision):
  - A: CAGR 8.1%, vol 7.8%, Sharpe 0.86, MaxDD -12.2%
  - B: CAGR 11.8%, vol 14.6%, Sharpe 0.74, MaxDD -26.7%
  - C: CAGR 11.3%, vol 12.8%, Sharpe 0.79, MaxDD -20.6%
  - D: CAGR 10.9%, vol 19.6%, Sharpe 0.55, MaxDD -55.2%
- Correlations: IBS vs trend 0.22, IBS vs index 0.66, trend vs index 0.37
- Crises: A was positive in the GFC (+19%), COVID (+3%) and 2022 (+5%); B fell 19% in the GFC and 11% in COVID
- Rule: drawdown PASS (-12.2% vs -26.7%), return cost FAIL (3.6% a year vs a 2% limit)
- DECISION: B - IBS (CFD account) + S&P 500 index fund (ISA), 50/50, rebalanced yearly. A had the best Sharpe and half the drawdown, but cost more return than the rule allowed; the rule was not changed after seeing results.

## Fund allocation (4 Nov 2026) - DISCRETIONARY

- Chosen by preference for diversification and downside protection, NOT by the pre-set rule (which picked IBS + index). Weights were not fitted to historical data.
- GBP 500 fund, 2:1 split: about GBP 333 IBS (CFD account) + about GBP 167 long-only trend (ISA, trial 1 rules), rebalanced between sleeves yearly
- Known trade-off from the portfolio analysis: trend lowers drawdowns and has low correlation with IBS (0.22) but cost about 3.6% a year of return at a 50/50 split in 2007-2026, mostly from holding non-US assets while US stocks led
- Phasing: IBS paper trading (from 3 Nov 2026) -> GBP 200 live -> full allocation if live tracks the model. Trend paper-tracked monthly from the 30 Nov 2026 month-end (trend_paper.py), on US ETF proxies; mapped to London-listed UCITS funds before going live
