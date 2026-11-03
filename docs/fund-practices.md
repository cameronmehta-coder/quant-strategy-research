# Fund Practices by Strategy

Researched 29 Oct 2026. How professional managers run each of our strategies, which practices conflict between strategies, and the controls that apply to all of them.

**The rule this document is built on:** every technique is a bet about how prices behave. Trend following bets that moves continue; mean reversion bets that they reverse. A technique that helps one usually hurts the other, so a technique belongs to a strategy, never to "professional trading" in general.

The clearest proof is stop-losses. Kaminski & Lo (2014) show mathematically that under a random walk stop-losses always reduce expected return; under momentum they can add value; under mean reversion they are a further drag, because the stop exits just before the reversal it was waiting for. v7 combined trend, mean-reversion and breakout signals with one set of filters and stops, so some rules were always working against some signals.

---

## 1. Conflict map

| Technique | Trend following | Low volatility | IBS mean reversion | Pairs (optional) |
|---|---|---|---|---|
| Price stop-loss | Built in: exit when the signal flips. No extra tight stops | Not used; quarterly rebalance does the job | **No.** Use a time exit instead | Only an extreme divergence stop, plus a time stop |
| Profit target | **Never.** Profits come from a few big trends | Not used | **Yes.** Exit on the bounce | Yes: exit when the spread returns to its mean |
| Cut size when volatility rises | **Yes, core practice** | Already low-risk by selection | **Careful.** The edge is strongest in high volatility | Size by spread volatility |
| Market trend filter (e.g. 200-day) | It *is* the strategy | No: would duplicate strategy 1 | Debated: test once (see section 4) | Not relevant |
| Averaging down | Never | No | Not in version 1 | No: divergence risk |
| Rebalance frequency | Monthly | Quarterly | Daily, at the close | Daily |
| No-trade buffer | Yes | Yes (rank buffer) | No (entries are yes/no) | No |
| Execution timing | Not critical | Not critical | **Critical** | Critical: both legs together |
| Cost sensitivity | Low | Low | **Very high** | **Very high** |
| Consecutive-loss circuit breaker | **No.** Many small losses are normal | No | No | No |
| ML signal filter | No | No | No | No |

---

## 2. Strategy 1: Multi-asset trend following

### What funds do
- **Signals:** AQR and Hurst, Ooi & Pedersen use the sign of 1-, 3- and 12-month excess returns, equally blended. Graham Capital says many managers blend speeds because combining them reduces reliance on any single model specification.
- **Sizing:** each market is sized to the same risk. AQR targets 40% annualised volatility per asset, then scales the whole portfolio to 10%. Volatility is estimated with exponentially weighted averages (60-day centre of mass) or 3-year monthly returns.
- **Breadth:** 58–67 futures markets with average pairwise correlation below 0.1. Breadth is the main source of the Sharpe ratio.
- **Exits:** positions close when the signal reverses. Risk controls are per-market position limits and sector or asset-class caps.
- **Expectations:** about 0.4 gross Sharpe per single market over 1880–2016. The diversified strategy was positive in 8 of the 10 worst 60/40 drawdowns, but its own drawdowns reached 25%.
- **Known weak spots:** fast crashes after bull runs (1987, Q4 2018), choppy markets, and long flat periods. Graham: protection "is not guaranteed", and trend following "should not be treated exclusively as a portfolio hedge".
- **Volatility targeting evidence:** Harvey et al. (2018, Man Group) found it improves Sharpe ratios for equities and credit, has a negligible effect for bonds, commodities and currencies, and reduces extreme losses in every asset class.

### Our version versus theirs (be honest in the write-up)
- **Long-only, no leverage:** we can step aside in a bear market but can't profit from it, so crisis returns will be weaker than a CTA's.
- **8 ETFs, not 60 futures:** less breadth, so expect a lower Sharpe ratio than the published figures.
- **Already matches fund practice:** inverse-volatility slots, a 12-month signal, monthly trading, a one-day lag and a cost charge.

### Version 2 candidates (one test each, each logged as a trial)
1. **Blended signal:** average of the 3-, 6- and 12-month on/off signals. This is for robustness, not optimisation.
2. **No-trade buffer:** skip any trade that changes a weight by less than about 2 percentage points. NBIM (Norway's sovereign fund, 2018) found a 6-point band cut rebalancing costs by about 60% versus continuous rebalancing, at the price of a small tracking error.
3. **Asset-class cap:** for example, US Treasuries (IEF plus TLT) at most 35% combined.

### Do not import
Stop-losses, profit targets, VIX filters, ML filters, or the consecutive-loss circuit breaker from v7. Trend following has many small losses by design, so a breaker would switch it off just before the big trends.

---

## 3. Strategy 2: Low-volatility US large caps

### What funds do
- **Robeco's Conservative Formula** (Blitz & van Vliet, 2018): take the 1,000 largest stocks, keep the 500 with the lowest 36-month volatility, then pick the 100 with the best combined rank of 12-1 month momentum and net payout yield. Equal weights, quarterly rebalance. Robeco says the extra screens avoid the low-vol pitfalls of "high valuations and weak momentum".
- **MSCI Minimum Volatility indexes:** single stock at most 1.5%, sector weights within ±5% of the parent index, one-way turnover capped at 10% per review, semi-annual rebalance.
- **Why it works:** leverage-constrained investors overpay for high-beta stocks (Frazzini & Pedersen, *Betting Against Beta*, 2014).

### Known risks
- **Interest rates:** low-vol stocks behave partly like bonds. Rate exposure explains roughly 20% to 80% of the anomaly, depending on assumptions (Driessen et al., 2019).
- **Valuation and crowding:** in September 2022, the USMV low-vol ETF traded at a P/E of 18.8, versus 9.1 for a value ETF (Swedroe).
- **Lagging rallies:** low-vol fell about as much as the market in COVID, then lagged the recovery (Blitz, 2022).

### Our adaptation
- Hold the 20–30 lowest 36-month-volatility stocks from our universe, with **at most 25% of names in any one sector**.
- Rebalance quarterly with a **rank buffer**: keep a current holding until it falls well outside the cut-off, to cut turnover.
- Optional later: a momentum tilt, Conservative-Formula style. Payout data (buybacks) is hard to get free, so it would be momentum only. Note that this raises correlation with strategy 1.
- Survivorship bias from the existing universe list applies here too.

### Do not import
A market-timing filter (strategy 1 already does this job), stop-losses, or profit targets.

---

## 4. Strategy 3: IBS mean reversion on an S&P 500 ETF

### What the evidence shows
- **Pagonidis** (33 ETFs, inception to May 2013): when IBS was below 0.2, the next day averaged +0.35%; above 0.8, it averaged −0.13%. The effect was stronger in high volatility and in bear markets (negative 200-day return). Results are before costs, and the paper says "commissions will greatly decrease the returns".
- **Execution:** the paper's trades happen at the close, and it suggests the closing auction to avoid the bid-ask spread.
- **Costs dominate short-term reversal** (de Groot, Huij & Zhou, 2012). Most of the cost drag came from small caps. Staying in large caps and limiting turnover is what lets the strategy survive costs.

### Our adaptation
- **Entry:** IBS below 0.2 at the close. Automated around 16:25 UK on the London-listed, sterling-priced ETF, which avoids the 0.15% FX fee.
- **Exit:** IBS above 0.8, or a time stop after 5 days, whichever comes first.
- **Sizing:** a fixed size per trade, with **no price stop-loss**. Account-level limits (section 6) cap the damage instead.
- **Fill-timing test:** compare buying at the close with buying the next morning before trusting any result.
- **One pre-registered regime test:** a 200-day trend filter. Connors-style systems use one, but the paper found the effect *largest* in bear markets, so the filter removes the best trades. It would also make this strategy behave more like strategy 1. Adopt it only if it improves the test period.

### Do not import from trend following
Cutting size when volatility rises (that removes the best trades), stop-losses, or waiting for confirmation.

---

## 5. Optional: pairs trading (CFD, manual)

### What the evidence shows
- **Classic method** (Gatev, Goetzmann & Rouwenhorst, 2006): 12-month formation period, then a 6-month trading period. Open when the spread diverges by more than 2 standard deviations, close on convergence, at period end or on delisting.
- **Cointegration tests** give a sounder statistical basis than simple distance.
- **Decay:** profits have declined. In Do & Faff (2010), 32% of selected pairs never converge.
- **Speed and costs:** in Bowen et al. (2010), about 20% a year of intraday pairs profits were wiped out by 15 basis points of costs plus a 60-minute execution delay.

### Our rules if we build it
- Sector-matched, cointegrated pairs.
- Re-estimate hedge ratios every period.
- A time stop plus an extreme-divergence stop.
- No trades around earnings or mergers.
- CFD financing charged on both legs.

---

## 6. Firm-wide controls (apply to every strategy)

These govern process, not signals, so they never conflict.

### Research discipline
1. **Pre-register** rules and pass/fail thresholds before seeing results. Already done for strategy 1.
2. **Log every variant tried** in a trials log. Harvey & Liu (2015): the required haircut depends on how many tests you ran, and is "almost always above" 50% for Sharpe ratios under 0.4. Their example: with 200 tests, a Sharpe of 0.75 falls to about 0.32.
3. **Report a Deflated Sharpe Ratio** (Bailey & López de Prado, 2014). It corrects for selection bias and non-normal returns, and it's a strong point for the write-up.
4. **Parameter stability:** "small changes to parameters should not flip the strategy from 'great' to 'dead'" (Resonanz Capital).
5. **Gross-to-net waterfall:** show how returns go from gross, to after costs, to after FX fees.

### Live operations
- **Evidence tiers:** simulated, then paper, then live. Only live net results count as a track record (Resonanz).
- **Pre-trade checks in code, before any API order:**
  - maximum order value and maximum position percentage
  - an allowed-instrument list
  - no duplicate orders
  - price sanity checks against the last close
  - dry-run mode as the default
- **Kill switch:** one command that cancels open orders and stops the scheduler.
- **Change control:** version every release in git, test in demo before live, delete dead code, and never change live parameters without rerunning the backtest and logging it as a trial. Knight Capital lost over $460m in about 45 minutes in 2012. Dormant old code was triggered by a reused flag after a deployment that missed one of eight servers and wasn't reviewed by a second person.
- **Reconciliation and drift monitor:** compare broker positions and fills with the model after every rebalance.

### When to stop a strategy
- Write stop rules in advance (Resonanz), but base them on **process breaks**: execution drift, data errors, or broken assumptions.
- Don't stop on profit-and-loss alone. A strategy with a true Sharpe of 1.5 can still have a two-year drawdown (Robot Wealth).
- **Our rule:** a drawdown deeper than 1.5 times the worst backtest drawdown triggers a review, not an automatic stop.

### Portfolio level
- Keep each strategy as a separate sleeve with its own accounting.
- Combine sleeves with inverse-volatility weights, rebalance between them quarterly, and measure their real correlations.

---

## 7. Adoption order
1. **Strategy 1, version 1:** run as pre-registered, with no changes.
2. **Start the trials log** (`trials.csv`); version 1 is trial 1.
3. Then test the version 2 candidates (section 2), one at a time, each logged.
4. Write the pre-trade checks module **before** any Trading 212 API order code.
5. Strategies 3 and 2, each applying only its own column of the conflict map.

---

## Sources
- Kaminski & Lo (2014), "When Do Stop-Loss Rules Stop Losses?", *Journal of Financial Markets* 18: https://dspace.mit.edu/handle/1721.1/114876
- Hurst, Ooi & Pedersen (2017), "A Century of Evidence on Trend-Following Investing", *Journal of Portfolio Management*: https://fairmodel.econ.yale.edu/ec439/hurst.pdf
- AQR (2013), "Demystifying Managed Futures", *Journal of Investment Management*: https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf
- Graham Capital (2026), Trend Following Primer: https://www.grahamcapital.com/wp-content/uploads/2026/05/Trend-Following-Primer_May-26.pdf
- Harvey et al. (2018), "The Impact of Volatility Targeting": https://quantpedia.com/the-impact-of-volatility-targeting-on-equities-bonds-commodities-and-currencies
- NBIM (2018), "No-Trade Band Rebalancing Rules", Discussion Note 01/2018: https://www.nbim.no/contentassets/8cb41f89dce345f5a6a295238f7872fb/no-trade-band-rebalancing-rules-expected-returns-and-transaction-costs.pdf
- Blitz & van Vliet (2018), "The Conservative Formula": https://alphaarchitect.com/the-conservative-formula-quantitative-investing-made-easy/ and https://robeco.com/en-uk/insights/2022/05/conservative-investing-stands-the-test-of-time
- MSCI Minimum Volatility Advanced Indexes Methodology (2025): https://www.msci.com/indexes/documents/methodology/3_MSCI_Minimum_Volatility_Advanced_Indexes_Methodology_20250203.pdf
- Driessen et al. (2019), "Does interest rate exposure explain the low-volatility anomaly?", *Journal of Banking & Finance* 103: https://www.sciencedirect.com/science/article/abs/pii/S0378426619300688
- Swedroe (2023), "Beware of Low-Volatility Portfolios": https://www.advisorperspectives.com/articles/2023/02/27/beware-of-low-volatility-portfolios
- Pagonidis (2014), "The IBS Effect: Mean Reversion in Equity ETFs", NAAIM: https://www.naaim.org/wp-content/uploads/2014/04/00V_Alexander_Pagonidis_The-IBS-Effect-Mean-Reversion-in-Equity-ETFs-1.pdf
- de Groot, Huij & Zhou (2012), "Another Look at Trading Costs and Short-Term Reversal Profits", *Journal of Banking & Finance* 36(2): https://ideas.repec.org/a/eee/jbfina/v36y2012i2p371-382.html
- Krauss (2015), "Statistical Arbitrage Pairs Trading Strategies: Review and Outlook": https://www.iwf.rw.fau.de/files/2016/03/09-2015.pdf
- Harvey & Liu (2015), "Backtesting": https://www.cmegroup.com/education/files/backtesting.pdf
- Bailey & López de Prado (2014), "The Deflated Sharpe Ratio": https://papers.ssrn.com/abstract=2460551
- Resonanz Capital, "Underwriting Backtests in Systematic Investing": https://resonanzcapital.com/insights/evaluating-backtests-and-simulated-track-records-in-systematic-investing
- Robot Wealth, "A Quant's Approach to Drawdown": https://robotwealth.com/a-quants-approach-to-drawdown/
- SEC order on Knight Capital, summarised: https://www.jrvarma.in/blog/Y2013/Knight-Capital.html
