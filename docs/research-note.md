# Testing Three Systematic Strategies with Pre-Registered Rules

Cameron Mehta - November 2026

## Summary

I tested three systematic strategies drawn from the quantitative finance literature: multi-asset trend following, low-volatility equities and short-term mean reversion on the S&P 500 using Internal Bar Strength (IBS). For every trial the rules, the comparison benchmark and five pass/fail checks were written down before the backtest was run on real data. Of six trials, five failed. The trend and low-volatility research is closed. IBS mean reversion passed every check, including on 13 years of data after the original paper was published, and is now being paper-traded.

## Research protocol

The protocol borrows practices that systematic funds use to avoid fooling themselves:

- **Pre-registration.** Rules and checks fixed in advance and recorded in a trials log. Results cannot move the goalposts.
- **The right benchmark.** Each strategy is judged against the closest thing it claims to improve on: trend following against the same portfolio without the trend rule, low volatility against the same stock universe equally weighted.
- **Out-of-sample testing.** Train and test periods are separated. For IBS the test period starts after publication.
- **Realistic implementation.** A one-day execution lag, transaction costs and the actual fees of the broker I would use, checked in the app.
- **Robustness.** A strategy must also work for nearby parameter choices, not only the selected one.
- **Every trial counted.** All variants are logged so the final result can be judged against the number of attempts.

Data: daily prices from Yahoo Finance via Python (pandas, yfinance), 1993-2026 depending on the instrument.

## Results

| Strategy | Trials | Key test-period result | Verdict |
|---|---|---|---|
| Trend following, long-only (8 ETFs) | 2 | Sharpe 0.55-0.61 vs 0.59 without the trend rule; max drawdown -9% to -11% vs -21% | Failed robustness |
| Trend following, long-short (6 CFD markets) | 1 | Sharpe -0.06 vs 0.67 long-only; cost drag 2.4% a year | Failed all checks |
| Low volatility, own rules | 1 | Sharpe 0.62 vs 0.85 equal-weight universe | Failed (biased test) |
| Low volatility, real funds (SPLV, USMV) | 1 | Sharpe 0.65 and 0.79 vs SPY 0.82, 2011-2026 | Failed |
| IBS mean reversion on SPY | 1 | +0.27% per trade after costs (t = 3.2), Sharpe 0.69, max drawdown -16% vs SPY -34% | **Passed all checks** |

### Trend following

Each month the strategy held ETFs across equities, bonds, gold, commodities and property, sized by inverse volatility, and only those whose 12-month return beat cash. It did what the literature says on the downside: positive in the 2008 crisis (+11% while SPY fell 55%) and roughly half the drawdown of the same portfolio without the rule. But it cost about 1.6% a year of return, so its Sharpe ratio was no better. A blended 3/6/12-month signal reacted faster in 2020 and 2022 but failed the same robustness check.

The published evidence (Hurst, Ooi & Pedersen, 2017) comes from 60-plus futures markets traded long and short. A long-short version through CFDs tested whether shorting closes the gap. It delivered strong crash protection (+32% in 2008, +6.5% in the COVID crash), but repeated losses on short positions during bull-market rallies and about 5% a year in short financing left it below cash after costs. My conclusion is that trend following's edge needs breadth and futures-level costs, which a small retail account does not have.

### Low volatility

Holding the 25 least volatile large US stocks failed against the equal-weight universe. That test had a known flaw: the universe was today's large caps, which includes past high-volatility winners such as NVIDIA and Tesla, and that biases the test against low volatility specifically. I therefore ran a second test on two real low-volatility funds, which have no survivorship bias and include real costs. They beat the S&P 500 on a risk-adjusted basis from 2011 to 2016 but lagged from 2017, with alpha close to zero over the whole period. They protected in slow sell-offs (2018, 2022) but fell as much as the market in the COVID crash and missed most of the recovery. The first result was not just bias.

### IBS mean reversion

IBS measures where the day's close sits within its range: (close - low) / (high - low). The rule buys the S&P 500 at the close when IBS is below 0.2 and sells when it is above 0.8, or after five days. Pagonidis (2014) documented the effect on data to May 2013, so June 2013 onwards is a genuine out-of-sample test.

- **After publication:** 29 trades a year, 66% winners, +0.27% per trade after costs, invested 31% of the time. Sharpe 0.69 (SPY 0.75) with half the drawdown, and +19.6% in 2022 when SPY fell 18.6%.
- **Significance:** a t-statistic of 3.2. That clears a Bonferroni correction for six trials (about 2.6) and the stricter 3.0 hurdle suggested by Harvey, Liu & Zhu (2016).
- **A trend filter hurt.** Adding the popular 200-day moving-average filter cut the Sharpe from 0.69 to 0.38, consistent with the paper's finding that the effect is strongest in falling markets.
- **Costs and timing matter.** The edge disappears at 0.20% per side, and buying at the next open instead of the close keeps only 63% of it.
- **The instrument matters.** The same rules on a London-listed S&P 500 ETF showed no edge. Its trading day barely overlaps the US close, which is when the effect appears. The strategy is therefore implemented with an S&P 500 CFD traded about ten minutes before the US close, where costs are about 0.025% per side, half the backtest assumption.

## Lessons

1. **Techniques belong to strategies.** A stop-loss can add value under momentum but reduces returns under mean reversion (Kaminski & Lo, 2014). My earlier trading system mixed trend, breakout and mean-reversion signals under one set of filters, which is why its rules worked against each other.
2. **Survivorship bias is not neutral.** It flatters some strategies and penalises others.
3. **Implementation can decide the result.** The same signal worked on one listing of the S&P 500 and not on another.
4. **Small Sharpe differences are noise.** Over ten years the uncertainty is about 0.2, so pre-registered checks should be designed with significance in mind.
5. **Stopping is part of the method.** Each closed strategy failed its own pre-set test; re-tuning it on data already seen would have been data mining.

## Limitations

The IBS result rests on one market and one sample. The backtest assumes trading at the close, while I trade slightly before it. Yahoo Finance data is free but not institutional quality. A single strategy invested a third of the time is not a diversified portfolio.

## Next steps

1. Paper-trade IBS for three months against pre-set process rules: signals executed on time, no leverage, and fills tracking the model. Then trade it live with a small amount.
2. Test IBS on other US index markets (Nasdaq 100, Russell 2000) under a new pre-registration, as a first step towards diversification.

## References

- Blitz, D. & van Vliet, P. (2018). The Conservative Formula. *Journal of Portfolio Management*.
- Harvey, C., Liu, Y. & Zhu, H. (2016). ...and the Cross-Section of Expected Returns. *Review of Financial Studies*.
- Hurst, B., Ooi, Y. H. & Pedersen, L. H. (2017). A Century of Evidence on Trend-Following Investing. *Journal of Portfolio Management*.
- Kakushadze, Z. & Serur, J. A. (2018). *151 Trading Strategies*. Palgrave Macmillan.
- Kaminski, K. & Lo, A. (2014). When Do Stop-Loss Rules Stop Losses? *Journal of Financial Markets*.
- Pagonidis, A. (2014). The IBS Effect: Mean Reversion in Equity ETFs. NAAIM.

Full trial records: [trials-log.md](trials-log.md). Fund practices by strategy: [fund-practices.md](fund-practices.md).
