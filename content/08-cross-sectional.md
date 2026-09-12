---
number: 8
slug: cross-sectional
title: The cross-sectional factor model
summary: Stop asking what moves with the market. Start asking what characteristics get paid.
time: 2-3 hours
status: soon
---

!!! warning "Being written"
    The data you need is already in your download - `Universe` carries the ICB
    industry for every name. Here is the shape of it so you can start early.

Module 7 ran one regression per stock through time. This one turns the problem
ninety degrees: **one regression per week, across stocks**.

<div class="formula">r<sub>i,t</sub> = &Sigma;<sub>k</sub> X<sub>i,k</sub> f<sub>k,t</sub> + &epsilon;<sub>i,t</sub></div>

The exposures **X** are known in advance - size, momentum, industry. The factor
returns **f** are what you solve for. Each week you run a cross-sectional
regression of that week's returns on last week's characteristics, and the
coefficients tell you what the market paid for being large, or cheap, or a bank,
*that week*.

Stack those coefficients into a time series and you have factor returns. Take
their covariance and you have a factor covariance matrix **F**. Then:

<div class="formula">&Sigma; = X F X&prime; + &Delta;</div>

This is what BARRA and Axioma sell. The exposures are observable today, so the
model says something about a stock that listed last month - which a time-series
model estimated on five years of history simply cannot.

### Exposures you can build from this data

| Factor | How |
|---|---|
| Size | log market cap, z-scored across the universe |
| Momentum | 12-month return skipping the last month |
| Low volatility | negative trailing 1-year vol |
| Industry | 11 ICB dummies from the `Universe` tab |

### The one you cannot

**Value.** Book-to-price needs book value, and we have no free point-in-time
source for it. Dividend yield is the usual stand-in and it is a poor one - it
conflates value with payout policy and quality. Worth knowing where the free data
runs out.

### Things that will bite you

- **Collinearity.** Industry dummies plus an intercept is rank-deficient. Either
  drop the intercept or constrain the industry returns to sum to zero.
- **Weighting.** Regress weighted by square root of market cap. Residuals are
  heteroskedastic in size, and unweighted the smallest names set the factor.
- **Look-ahead.** Exposures must be known *before* the returns they explain. Lag
  them by one period, always.
