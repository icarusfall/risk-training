---
number: 8
slug: cross-sectional
title: The cross-sectional factor model
summary: Regress returns on stock characteristics each week to estimate factor returns.
time: 2-3 hours
---

Module 7 ran one regression per stock, through time. This module turns the
problem around and runs **one regression per week, across stocks**.

Most commercial equity risk models are built this way, so it also makes vendor
documentation much easier to follow.

## The idea

The question here is which characteristics were rewarded in a given week.

<div class="formula">r<sub>i,t</sub> = &Sigma;<sub>k</sub> X<sub>i,k</sub> f<sub>k,t</sub> + &epsilon;<sub>i,t</sub></div>

The **exposures** X are known in advance &mdash; you can look up a company's size
and industry today. The **factor returns** f are what you solve for. Each week
you regress that week's returns across all 81 stocks on their characteristics,
and the coefficients tell you what the market paid, *that week*, for being large,
or for having momentum, or for being a miner.

The roles are reversed compared with Module 7. There, the factor return (the
market) was observed and beta was estimated. Here the exposure is observed and
the factor return is estimated.

!!! tip "An advantage over the time-series model"
    Exposures are observable *now*. A company that listed three months ago has no
    usable return history, so Module 7 has nothing to say about it, but you know
    its market cap and industry today, so a cross-sectional model can give it a
    covariance with everything else immediately. This is one of the main reasons
    commercial models use this approach.

## Step 1: build the exposures

We fix exposures as at **Wednesday 27 September 2023** and regress every week
*after* that date. Freezing them keeps the exercise reproducible, and measuring
them before the returns they explain avoids look-ahead. A production model
refreshes exposures monthly, but the method is the same.

Four factor groups, all buildable from your existing download:

| Factor | Definition |
|---|---|
| **Size** | natural log of market cap |
| **Momentum** | 12-month return skipping the most recent month |
| **Low volatility** | negative of trailing 1-year daily volatility |
| **Industry** | 11 ICB dummies from the `Universe` tab |

Each style factor is **z-scored** across the universe and then clipped at
&plusmn;3:

<div class="formula">X<sub>i</sub> = clip( (x<sub>i</sub> &minus; mean(x)) / stdev(x), &minus;3, +3 )</div>

Z-scoring is needed because the raw units are not comparable: log market cap is
around 23, while momentum is around 0.1. Standardising puts every factor return
in the same unit, the return to a one-standard-deviation exposure.

Clipping matters because one silly value would otherwise become the factor.

!!! excel "Building the exposure matrix"
    Market cap is on the `Universe` tab. For size:
    ```
    raw       =LN(mcap)
    z-score   =(LN(mcap) - AVERAGE(logcaps)) / STDEV.S(logcaps)
    clipped   =MAX(-3, MIN(3, zscore))
    ```
    Momentum, using daily prices and the 12-1 convention:
    ```
    =INDEX(B:B, n-21) / INDEX(B:B, n-252) - 1
    ```
    where `n` is the row of 27 September 2023. The most recent month is skipped
    because returns over that month tend to reverse, which would dilute the
    signal.

    Industry dummies, with industry names across row 1:
    ```
    =--($D2 = E$1)
    ```
    The double-negative coerces TRUE/FALSE to 1/0.

!!! warning "Do not add an intercept"
    Your 11 industry dummies already sum to 1 for every stock, so they act as an
    intercept. Add another column of ones and the matrix is rank-deficient,
    `LINEST` returns garbage or an error, and the factor returns become
    arbitrary. This is a common way to break the model.

    With 81 stocks and 14 columns you should have full rank 14. To check, the
    industry columns must sum, row by row, to exactly 1.

## Step 2: one regression per week

Regress that week's 81 returns on the 14 exposure columns, with no intercept.

Weight the regression by the **square root of market cap**. Residuals vary with
size (small companies are noisier), and without weights the smallest names in
the index have too much influence on the factor returns. Square-root-of-cap is
the usual convention: it reduces the influence of small names without letting
the largest ones take over.

!!! excel "Weighted least squares"
    You do not need a special function. Multiply **both** sides by the square root
    of the weight and run an ordinary regression:
    ```
    y*  =return   * SQRT(mcap)
    X*  =exposure * SQRT(mcap)
    ```
    Then `LINEST(y*, X*, FALSE, FALSE)`, where the third argument `FALSE`
    suppresses the intercept.

!!! danger "LINEST returns coefficients in reverse order"
    `LINEST` hands back the slopes in **reverse column order**: the coefficient
    for your last X column comes first. With 14 factors this scrambles the model
    without producing an error, and everything downstream looks plausible.

    Either reverse them with `INDEX`, or lay your exposure columns out in reverse
    to begin with. Check it on a single factor first: run `LINEST` with one X
    column, confirm it matches `SLOPE`, then add the rest.

Drag that down for every week after 27 September 2023. You will end up with
roughly 154 rows, which is a time series of factor returns.

## Step 3: what the factor returns look like

Annualise the volatility of each factor return series. On this data you should
see something close to:

| Factor | Annualised vol |
|---|---|
| Size | 4.6% |
| Momentum | 6.1% |
| Low volatility | 7.0% |
| Industry: Industrials | 14.8% |
| Industry: Basic Materials | 25.3% |
| Industry: Energy | 25.3% |

Two things stand out.

**Style factors are much less volatile than stocks.** A typical FTSE 100 name runs
at 25&ndash;35% annualised; the size factor at under 5%. Diversification across
81 names reduces the volatility of a common signal, so a style tilt has to be
large to have much effect.

**Industry factors are much more volatile than styles**, because they include the
market. Our specification has no separate market factor: with the dummies acting
as the intercept, each industry factor return is roughly *that industry's*
return, market included. Commercial models often extract a market factor
explicitly so that the industry factors become market-*relative*, which is worth
knowing when comparing vendor factor volatilities with ours.

## Step 4: the covariance matrix

Now assemble it:

<div class="formula">&Sigma; = X F X&prime; + &Delta;</div>

- **X** is 81 &times; 14 &mdash; the exposures.
- **F** is 14 &times; 14 &mdash; the covariance matrix of your factor returns.
- **&Delta;** is 81 &times; 81 diagonal &mdash; the variance of each stock's
  regression residuals.

!!! excel "Three MMULTs and a diagonal"
    ```
    F         =MMULT(TRANSPOSE(Fdev), Fdev) / (COUNT-1)      ' 14x14
    XFX'      =MMULT(MMULT(X, F), TRANSPOSE(X))              ' 81x81
    residual  =VAR.S(residuals for each stock)               ' down the diagonal
    ```
    The residual for stock *i* in week *t* is its actual return minus
    `SUMPRODUCT(exposures_i, factor_returns_t)`.

On this data the median specific volatility comes out around **21% annualised**,
with a range of roughly 5% to 40%. So a typical FTSE 100 stock has about 21
points of volatility that no factor in our model explains. That is expected:
specific risk is real, and it is the part a stock-picker is paid to take.

### Count the parameters

| Model | Free parameters |
|---|---|
| Sample covariance (Module 3) | **3,321** |
| Single-factor (Module 7) | 163 |
| Cross-sectional (this one) | **186** |

Fourteen factors use almost as few parameters as one, while capturing more of the
correlation structure: two miners are now correlated through their shared
industry as well as through beta.

## What you should find

Compute your portfolio's volatility under this &Sigma; and compare with Module 3.
They will be close but not equal.

Then run the concentration test. Build four equally-weighted portfolios and price
each under the sample, single-factor and cross-sectional matrices, comparing
against what each actually realised over the same 154 weeks:

| Portfolio | Realised | Single-factor | Cross-sectional |
|---|---|---|---|
| Five banks | 24.7% | &minus;3.7pp | **&minus;4.0pp** |
| Five miners | 32.5% | &minus;7.0pp | &minus;2.5pp |
| Five utilities | 19.1% | &minus;5.2pp | +2.5pp |
| One per industry | 17.2% | +0.9pp | &minus;0.1pp |

The single-factor model **understates every concentrated portfolio**, by between
3.7 and 7 points, as in Module 7. It only sees market exposure, so it misses
co-movement that is not driven by the market.

The cross-sectional model improves the estimate for the miners and the utilities.
It does not help for the **banks**, where it is slightly worse.

### Why it does not work for banks

Compare the actual average pairwise correlation with what the model implies:

| Portfolio | Actual | Model |
|---|---|---|
| Five banks | **0.673** | **0.555** |
| Five miners | 0.708 | 0.688 |
| Five utilities | 0.578 | 0.605 |
| One per industry | 0.153 | 0.138 |

The model gets every group roughly right except the banks, whose correlation it
understates by 0.12.

The reason is our industry classification. `ind_Financials` contains 27 names:
five banks, but also life insurers, general insurers, asset managers, private
equity vehicles and a couple of investment trusts. Barclays, Aviva and 3i all load
1.0 on the same factor. So the Financials factor return is an average across a
heterogeneous set of businesses, which dilutes the common movement among the
banks.

The miners do not have this problem: `ind_Basic Materials` is seven names, nearly
all of them miners, so the factor is more specific.

!!! tip "Classification granularity"
    **How finely you classify industries affects the results.** We used the 11
    ICB industries because 40 sectors left single-name groups that made the
    regression rank-deficient (Module 1 covers that trade-off). But 11 is too
    coarse for the FTSE 100's financial sector, and the model understates the
    risk of a UK bank portfolio as a result, which is a practical concern for a
    UK investor.

    Commercial models handle this by using finer groups where the data supports
    it, with banks separate from insurance and from financial services. They can
    do this because they cover thousands of stocks rather than 81, so a narrow
    group still contains enough names.

    Try it: split `ind_Financials` into `ind_Banks` and `ind_OtherFinancials` and
    re-run. The bank portfolio's estimate should improve, and something else get
    slightly worse. Each choice improves some estimates at the expense of others.

!!! danger "Labels that mix different businesses"
    Look up the sector labels our source provides, on the [data page](/data). Two
    of them group companies with very different economics under one heading:

    | Source label | Contains |
    |---|---|
    | Personal Goods | Burberry **and** Unilever |
    | Household Goods & Home Construction | Barratt, Persimmon **and** Reckitt |

    Burberry sells £2,000 trench coats; Unilever sells Domestos. One is about as cyclical as a business gets and the other is about as defensive. They carry the same
    label, so our mapping puts both in Consumer Discretionary. The same applies
    to the housebuilders and Reckitt.

    A rule based on the *label* cannot fix this, because the label does not
    distinguish them. It needs a per-company override, which means someone has to
    make and maintain 100 judgement calls.

    We have left this in deliberately so you can see its effect on the model:
    `ind_Consumer Discretionary` is a mix of luxury, retail, housebuilding and two
    large defensive companies, so its factor return averages businesses that do
    not move together. Any portfolio built from those names will have its risk
    estimated through a factor that does not represent them well.

    When a vendor describes a model with many industry factors, it is worth asking
    how the classification was decided, as well as how many factors there are.

A factor model depends heavily on how its factors are defined, and that is the
main point of this module.

## A missing factor: value

**Value.** Book-to-price needs book value, and there is no free point-in-time
source for it. Dividend yield is often used instead, but it is a weak substitute:
it mixes cheapness with payout policy and with quality, and it drops to zero for
any company that suspends its dividend, which tends to happen when the stock has
become cheap.

In practice, **the quality of the exposures limits a cross-sectional model** more
than the regression does. The regressions are quick to set up; clean,
point-in-time, survivorship-free fundamental data is much harder to obtain, and
it is a large part of what vendors charge for.

!!! warning "Point-in-time, and why it matters"
    Our exposures use *today's* share count, so the size exposure for 2023 is
    approximate (see the note in Module 1 about NatWest). A production model uses
    the share count as it was reported at the time, along with the accounts as
    they were known *then*, not as they were later restated. Getting this wrong builds a backtest that quietly knows the future.
