---
number: 10
slug: bake-off
title: The bake-off
summary: Four models, one portfolio. Which would you have trusted in March 2020?
time: half a day
---

Everything so far has been construction. This module is judgement, which is the
part of the job that does not come out of a textbook.

You now hold four estimates of the same covariance matrix:

| # | Model | Parameters | Built in |
|---|---|---|---|
| 1 | Sample covariance | 3,321 | Module 3 |
| 2 | EWMA covariance | 3,321 | Module 5 |
| 3 | Single-factor | 163 | Module 7 |
| 4 | Cross-sectional | 186 | Module 8 |
| 5 | Statistical / PCA | ~490 | Module 9 |

They disagree. The exercise is to work out **which disagreements matter**, and to
form a defensible view. There is no answer key for the last section of this
module &mdash; write half a page and we will talk about it.

## First, the trap

Compute your portfolio's realised volatility over a window. Then compute the
Module 3 sample-covariance prediction over the same window.

They will match almost exactly. On the equal-weighted portfolio over the 156
weeks to September 2026, both come out at **13.05%**.

This is not evidence that the model is any good. The sample covariance is *fitted to*
that window, so of course it reproduces it &mdash; asking a model to predict the
data it was estimated on tells you nothing at all about forecasting.

Almost every bad backtest you will ever be shown is a version of this mistake.
Learn to spot it in one question: **what data did the model see before it made
this prediction?**

## The bias statistic

Here is the honest test, and the single most useful number in this whole
programme.

For each week, predict the volatility using **only data available before that
week**. Then standardise what actually happened:

<div class="formula">b<sub>t</sub> = r<sub>t</sub> / &sigma;<sub>predicted, t</sub></div>

If the model is calibrated, these standardised returns should have a standard
deviation of **1**. So:

<div class="formula">bias = stdev(b<sub>t</sub>)</div>

- **bias &gt; 1** &mdash; you understated risk. Returns came out bigger than
  predicted.
- **bias &lt; 1** &mdash; you overstated risk. Capital held against nothing.
- **bias &asymp; 1** &mdash; calibrated.

!!! excel "The rolling forecast"
    With portfolio returns in column B:
    ```
    prediction   =STDEV.S(OFFSET(B2, ROW()-106, 0, 104, 1))
    ratio        =B107 / C107
    bias         =STDEV.S(D107:D1114)
    ```
    The prediction for week *t* must use weeks *t*&minus;104 to *t*&minus;1
    **inclusive of neither t itself**. Getting this off by one row is the classic
    error and it flatters the model, because the return you are predicting is
    sitting inside the window you used to predict it.

    For the EWMA version, update the variance **after** recording each forecast:
    ```
    forecast_t  =SQRT(var_t)
    var_(t+1)   =0.94*var_t + 0.06*r_t^2
    ```
    Same discipline. Predict, then learn.

### What you should get

On the equal-weighted portfolio over the full sample:

| Forecast method | Bias | Weeks with abs(b) &gt; 3 |
|---|---|---|
| Rolling 52 weeks | 1.098 | 17 |
| Rolling 104 weeks | 1.100 | 21 |
| Rolling 260 weeks | 0.964 | 11 |
| EWMA &lambda; = 0.94 | **1.060** | **10** |
| EWMA &lambda; = 0.97 | 1.040 | 15 |

Three things to take from this table.

**Everything understates risk except the long window.** Biases above 1 across the
board. Volatility clustering means the big weeks arrive together, and a forecast
built on a calm stretch is always caught out.

**EWMA wins, and not only on the bias.** &lambda; = 0.94 has the fewest extreme
outliers &mdash; 10 against 21 for a flat 104-week window. Responsiveness does
not just move the average closer to 1; it reduces how *badly* wrong you are in
the worst weeks, which is the thing that actually costs money.

**The 260-week window scores 0.964, and that is not a win.** It looks closest to
1, but it gets there by being permanently too high &mdash; consistently
overstating in calm periods and still understating in crises. A single summary
statistic can hide compensating errors, which is why you look at the outlier
count as well.

## Test 2: the crises, one at a time

An average across twenty years tells you about the average week, which is rarely the week anyone is worried about.

Run your forecasts through each episode and compare EWMA(0.94) with a rolling
104-week window:

| Episode | EWMA(0.94) | Rolling 104w |
|---|---|---|
| Calm, H1 2007 | 10.8% | 11.8% |
| GFC peak, Q4 2008 | **34.6%** | 23.5% |
| Covid, Mar&ndash;Apr 2020 | **37.0%** | 21.2% |
| Gilt/LDI, Sep&ndash;Oct 2022 | 15.1% | 14.8% |
| Latest | 12.2% | 13.5% |

In the two big equity crises, EWMA is 11 and 16 percentage points higher. The
rolling window is still averaging in years of calm; by the time it catches up the
crisis is over. If you had been quoting the 104-week number in March 2020 you
would have been telling a portfolio manager their risk was about half what it
actually was.

And note the fourth row, which is the most interesting one: **the 2022 gilt crisis
barely registers in equity volatility at all**. It was the defining risk event of
recent UK financial history, it nearly broke the LDI industry, and aggregate FTSE
100 equity vol went from 14.8% to 15.1%.

That is worth understanding rather than filing away. The shock transmitted
through gilt yields, so it hit long-duration equity &mdash; real estate ran at 1.6
times its calm-period volatility, utilities 1.25 &mdash; while banks, which earn
more when rates rise, did not move at all. An equity risk model was the wrong
instrument for that crisis. Knowing which instrument answers which question is
most of what a risk function is for.

## Test 3: where the models disagree most

Build three portfolios and price each under all five matrices:

1. **Five banks.** Concentrated in one industry.
2. **Five names from five different industries.** Well spread.
3. **Your own portfolio.**

The pattern to look for: the single-factor model should understate the
concentrated portfolio, because all it can see is market exposure. The
cross-sectional model should handle it better, because the shared
`ind_Financials` exposure knows that banks move together for bank reasons. The
sample covariance will look fine in-sample and is the least trustworthy out of it.

## Test 4: minimum variance, out of sample

This is the one that changes how people think.

For each &Sigma;, find the minimum-variance portfolio &mdash; the weights
minimising w&prime;&Sigma;w subject to weights summing to 1. Use Solver, or
directly:

<div class="formula">w = &Sigma;<sup>&minus;1</sup>1 / (1&prime;&Sigma;<sup>&minus;1</sup>1)</div>

!!! excel "The closed form"
    ```
    =MMULT(MINVERSE(Cov), ones) / SUM(MMULT(MINVERSE(Cov), ones))
    ```
    Estimate each &Sigma; on data up to a cut-off date, then measure what the
    resulting portfolio actually realised *after* it. That is the only
    comparison that means anything.

What you should find: the **sample covariance produces the most extreme weights
and the worst out-of-sample result**, often including large negative positions if
you allow them.

The reason is worth stating precisely, because it is the deepest idea in this
programme. Matrix inversion amplifies the smallest eigenvalues, and the smallest
eigenvalues of a sample covariance matrix estimated from 3,321 parameters and
1,114 observations are almost pure noise. The optimiser then loads up on exactly
those directions, because they look like free diversification. It is not
diversification; it is estimation error.

So the matrix that fits history best forecasts worst. Factor models win **because**
they throw information away.

!!! tip "What this is called, and what it fixes"
    This is the bias-variance trade-off, and the mainstream fixes are worth
    knowing by name: **Ledoit-Wolf shrinkage** pulls the sample matrix toward a
    structured target; **random matrix theory** filters eigenvalues
    indistinguishable from noise; **factor models** impose structure directly.
    All three do the same job &mdash; accept some bias to cut variance.

## The question to answer

> It is 24 February 2020. A portfolio manager asks you for one tracking-error
> number for your portfolio. Which model, which window, what number do you give,
> and what do you say about the uncertainty around it?

Write half a page. Some things a good answer tends to include:

- A **choice**, made explicitly, with the reason stated.
- An acknowledgement that on that date **every one of these models was about to
  be wrong**, and roughly by how much.
- Something about the difference between the number and the **conversation** &mdash;
  what you would tell the manager to watch, not just what the spreadsheet says.
- The honest admission that a model estimated on survivorship-biased data from
  today's index constituents has a floor on how good it can be.

There is no correct answer. There are answers that show you understood what you
built, and answers that show you operated a spreadsheet.

---

## That is the programme

You have built an equity risk model from a column of prices, four different ways,
and you know why they disagree. You have found bad data by looking at it. You know
what tracking error is, where risk comes from in a portfolio, what VaR does and
does not tell you, and why the model that fits best forecasts worst.

Come and find me &mdash; I would like to hear which part surprised you most.
