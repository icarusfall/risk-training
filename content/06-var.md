---
number: 6
slug: var
title: Value at Risk
summary: Parametric VaR is one formula. Historical VaR makes fewer assumptions. Then test whether either one worked.
time: 75 min
---

Volatility describes the whole distribution. VaR asks a narrower question: **how
bad is a bad week?**

> VaR at 99% over one week is the loss that should be exceeded in only 1 week in
> 100.

## Parametric VaR

Assume returns are normal. Then the 99th percentile is 2.326 standard deviations
below the mean, and:

<div class="formula">VaR<sub>99%</sub> = &minus;(&mu; &times; h + z<sub>0.01</sub> &times; &sigma; &times; &radic;h)</div>

With &mu; set to zero over a one-week horizon (the estimate is mostly noise at
this horizon), this reduces to 2.326 &times; the weekly volatility.

!!! excel "One cell"
    ```
    =-NORM.S.INV(0.01) * SQRT(PVar)
    ```
    `NORM.S.INV(0.01)` is &minus;2.326, so the minus sign gives a positive loss.
    Note `SQRT(PVar)` is the **weekly** volatility &mdash; do not annualise first.
    Scaling a one-week VaR to ten days uses the same &radic;T rule, and relies on
    the same iid assumption discussed in Module 2.

## Historical VaR: the honest one

Historical VaR makes no distributional assumption and uses the portfolio's own
history.

1. Compute your portfolio's realised return for every week:
   `=MMULT(ReturnsW!B2:M1115, weights)` &mdash; one number per week.
2. Take the 1st percentile of that series.

!!! excel "One cell again"
    ```
    =-PERCENTILE.INC(PortRet, 0.01)
    ```
    Use `PERCENTILE.INC` for consistency with the answer key. `PERCENTILE.EXC`
    interpolates differently in the tails and will put you outside tolerance.

## Compare them

Historical VaR will come out **larger** than parametric, typically by 15&ndash;25%
on this data.

The gap reflects the fat left tail of equity returns: extreme moves happen more
often than a normal distribution predicts. The normal distribution says a
&minus;5% week should occur about once a decade. Count them in your own series.

!!! warning "Historical VaR has its own problem"
    It cannot produce a loss bigger than the worst one in your sample. Estimated
    on 2004&ndash;2007 data, historical VaR would have put the worst week at
    about &minus;6%. It also weights a week from 2009 exactly as heavily as last
    week, which is the window problem from Module 5, back again. A common fix is to
    EWMA-weight the historical observations.

## Expected shortfall

VaR gives the threshold but says nothing about losses beyond it. Expected
shortfall (conditional VaR) is the *average* loss given that you breached:

```
=-AVERAGEIF(PortRet, "<"&PERCENTILE.INC(PortRet,0.01))
```

It is typically 1.3&ndash;1.6&times; the VaR. Regulators have largely moved to ES,
partly because VaR says nothing about the size of losses beyond the threshold,
and partly because VaR is not sub-additive: the VaR of a combined book can exceed the sum of its parts, which is absurd for a risk measure. ES does not have that problem.

## Backtesting

A VaR number is a **prediction**, so it can be tested against what happened.

At 99% over 1,114 weeks you expect about **11 exceptions**. Count your actual
ones:

```
=COUNTIF(PortRet, "<"&-VaR)
```

Too many and you are understating risk. Too few and you are holding capital
against losses that do not happen.

### The Kupiec test

Is your exception count statistically plausible? The proportion-of-failures
test:

<div class="formula">
LR = &minus;2 ln[ (1&minus;p)<sup>n&minus;x</sup> p<sup>x</sup> ] + 2 ln[ (1&minus;x/n)<sup>n&minus;x</sup> (x/n)<sup>x</sup> ]
</div>

with *n* observations, *x* exceptions and *p* = 0.01. Under the null that your
model is calibrated, LR follows &chi;&sup2; with one degree of freedom. Reject at
95% if LR > 3.841.

```
=CHISQ.DIST.RT(LR, 1)
```

!!! tip "What Kupiec misses"
    It counts exceptions but ignores **when** they happened. Eleven exceptions
    spread evenly over twenty years suggests a reasonable model; eleven
    exceptions all in October 2008 suggests a model that failed in the period
    that mattered most. The Christoffersen test adds a clustering check, and in
    practice clustering is often the more serious problem.

Run the backtest on both your parametric and your historical VaR. One of them will
do noticeably better. Form a view on why.
