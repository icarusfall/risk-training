---
number: 8
slug: cross-sectional
title: The cross-sectional factor model
summary: Stop asking what moves with the market. Start asking what characteristics get paid.
time: 2-3 hours
---

Module 7 ran one regression per stock, through time. This module turns the
problem ninety degrees and runs **one regression per week, across stocks**.

It is the single most important idea in commercial equity risk modelling, and
once you have seen it the vendor documentation stops being mysterious.

## The idea

Instead of asking *what does this stock move with*, ask *what characteristics
were rewarded this week*.

<div class="formula">r<sub>i,t</sub> = &Sigma;<sub>k</sub> X<sub>i,k</sub> f<sub>k,t</sub> + &epsilon;<sub>i,t</sub></div>

The **exposures** X are known in advance &mdash; you can look up a company's size
and industry today. The **factor returns** f are what you solve for. Each week
you regress that week's returns across all 81 stocks on their characteristics,
and the coefficients tell you what the market paid, *that week*, for being large,
or for having momentum, or for being a miner.

Note what has swapped places. In Module 7 the factor return (the market) was
observable and beta was estimated. Here the exposure is observable and the factor
return is estimated.

!!! tip "Why this beats a time-series model"
    Exposures are observable *now*. A company that listed three months ago has no
    usable return history, so Module 7 has nothing to say about it &mdash; but you
    know its market cap, its industry and its size today, so a cross-sectional
    model gives it a covariance with everything else immediately. Risk models at
    LGIM and everywhere else are built this way for exactly that reason.

## Step 1: build the exposures

We fix exposures as at **Wednesday 27 September 2023** and regress every week
*after* that date. Freezing them keeps the exercise reproducible, and measuring
them before the returns they explain means no look-ahead. A production model
refreshes exposures monthly; that changes the plumbing, not the idea.

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

Z-scoring matters because the raw units are meaningless next to each other &mdash;
log market cap is around 23, momentum is around 0.1. Standardising puts every
factor return in the same unit: *the return to a one-standard-deviation bet*.

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
    where `n` is the row of 27 September 2023. Skipping the last month is not
    fussiness &mdash; the most recent month tends to *reverse*, and including it
    dilutes the signal.

    Industry dummies, with industry names across row 1:
    ```
    =--($D2 = E$1)
    ```
    The double-negative coerces TRUE/FALSE to 1/0.

!!! warning "Do not add an intercept"
    Your 11 industry dummies already sum to 1 for every stock, so they *are* an
    intercept. Add another column of ones and the matrix is rank-deficient,
    `LINEST` returns garbage or an error, and the "factor returns" become
    arbitrary. This is the single most common way to break this model.

    With 81 stocks and 14 columns you should have full rank 14. If you want to
    check: the industry columns must sum, row by row, to exactly 1.

## Step 2: one regression per week

Regress that week's 81 returns on the 14 exposure columns. No intercept.

Weight the regression by the **square root of market cap**. Residuals are
heteroskedastic in size &mdash; small companies are simply noisier &mdash; and
unweighted, the smallest names in the index end up setting the factor returns.
Square-root-of-cap is the industry convention: it damps the small names without
letting the mega-caps take over entirely.

!!! excel "Weighted least squares, the easy way"
    You do not need a special function. Multiply **both** sides by the square root
    of the weight and run an ordinary regression:
    ```
    y*  =return   * SQRT(mcap)
    X*  =exposure * SQRT(mcap)
    ```
    Then `LINEST(y*, X*, FALSE, FALSE)` &mdash; the third argument `FALSE`
    suppresses the intercept, which is what you want.

!!! danger "LINEST returns coefficients BACKWARDS"
    `LINEST` hands back the slopes in **reverse column order**: the coefficient
    for your last X column comes first. With 14 factors this will silently
    scramble your entire model and everything downstream will look plausible and
    be wrong.

    Either reverse them with `INDEX`, or lay your exposure columns out in reverse
    to begin with. Check it on a single factor first: run `LINEST` with one X
    column, confirm it matches `SLOPE`, then add the rest.

Drag that down for every week after 27 September 2023. You will end up with
roughly 154 rows &mdash; a time series of factor returns.

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

Two things to notice.

**Style factors are far less volatile than stocks.** A typical FTSE 100 name runs
at 25&ndash;35% annualised; the size factor at under 5%. That is what
diversification across 81 names does to a common signal &mdash; and it is why a
style bet has to be large to matter.

**Industry factors are much more volatile than styles**, because they contain the
market. Our specification has no separate market factor: with dummies acting as
the intercept, each industry factor return is roughly *that industry's* return,
market included. Commercial models often extract a market factor explicitly so
the industry factors become market-*relative*. Worth knowing when you read a
vendor's factor list and wonder why the numbers look nothing like ours.

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
points of volatility that no factor in our model explains. That is expected: specific risk is real, and it is the part a stock-picker is paid to take.

### Count the parameters

| Model | Free parameters |
|---|---|
| Sample covariance (Module 3) | **3,321** |
| Single-factor (Module 7) | 163 |
| Cross-sectional (this one) | **186** |

Fourteen factors buy you nearly as much economy as a single one, and a far richer
correlation structure &mdash; two miners are now correlated because they are both
miners, not merely because they both have high beta.

## What you should find, including where it fails

Compute your portfolio's volatility under this &Sigma; and compare with Module 3.
They will be in the same neighbourhood but not equal.

Then run the concentration test properly. Build four equally-weighted portfolios
and price each under the sample, single-factor and cross-sectional matrices,
comparing against what each actually realised over the same 154 weeks:

| Portfolio | Realised | Single-factor | Cross-sectional |
|---|---|---|---|
| Five banks | 24.7% | &minus;3.7pp | **&minus;4.0pp** |
| Five miners | 32.5% | &minus;7.0pp | &minus;2.5pp |
| Five utilities | 19.1% | &minus;5.2pp | +2.5pp |
| One per industry | 17.2% | +0.9pp | &minus;0.1pp |

The single-factor model **understates every concentrated portfolio**, by between
3.7 and 7 points, exactly as Module 7 predicted. All it can see is market
exposure, so any co-movement that is not market co-movement is invisible to it.

The cross-sectional model fixes that for the miners and the utilities. For the
**banks it does not** &mdash; it is marginally worse.

### Why the banks defeat it

This is the most instructive result in the module, so do not skip past it.

Compare actual average pairwise correlation with what the model implies:

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
equity vehicles and a couple of investment trusts. Barclays and Aviva and 3i all
load 1.0 on the same factor. So the "Financials" factor return is an average
across a heterogeneous set of businesses, and it is far too diluted to
capture the thing that makes *banks* move together.

The miners have no such problem: `ind_Basic Materials` is seven names, nearly all
of them actual miners, so the factor means something specific.

!!! tip "The lesson, which generalises"
    **The granularity of your classification is a modelling choice with real
    consequences.** We used the 11 ICB industries because 40 sectors left
    singletons that made the regression rank-deficient (Module 1 covers that
    trade-off). But 11 is too coarse for the FTSE 100's financial sector, and the
    result is a model that will understate the risk of a UK bank portfolio &mdash;
    which, at a firm like ours, is not a hypothetical worry.

    Commercial models handle this by going finer where the data supports it:
    Banks separate from Insurance separate from Financial Services. They can
    afford to, because they run thousands of stocks rather than 81, so a narrow
    bucket still has enough names in it.

    Try it: split `ind_Financials` into `ind_Banks` and `ind_OtherFinancials` and
    re-run. Watch the bank portfolio's estimate improve and something else get
    slightly worse. Neither choice is free; it comes down to where you would rather be wrong.

!!! danger "And our classification has a worse problem than granularity"
    Look up the sector labels our source actually provides, on the
    [data page](/data). Two of them bundle companies with opposite economics
    under one heading:

    | Source label | Contains |
    |---|---|
    | Personal Goods | Burberry **and** Unilever |
    | Household Goods & Home Construction | Barratt, Persimmon **and** Reckitt |

    Burberry sells £2,000 trench coats; Unilever sells Domestos. One is about as
    cyclical as a business gets and the other is about as defensive. They carry
    the same label, so our mapping puts both in Consumer Discretionary. Same
    story with housebuilders sitting alongside Reckitt.

    No rule based on the *label* can fix this, because the label does not distinguish them. It needs a per-company override, which means somebody
    has to make and maintain 100 judgement calls.

    We have left it as it is, deliberately, so you can see it. But note what it
    does to the model: `ind_Consumer Discretionary` is a blend of luxury,
    retail, housebuilding and two enormous defensives, so its factor return is
    an average of things that do not move together. Any portfolio you build out
    of those names will have its risk estimated through a factor that means very
    little.

    When a vendor tells you their model has 60 industry factors, this is the
    question to ask: not how many, but *who decided which, and on what basis?*

That nuance &mdash; a factor model is only as good as its factor definitions
&mdash; is the real payoff of this module, and it is worth more than the machinery.

## The factor we could not build

**Value.** Book-to-price needs book value, and there is no free point-in-time
source for it. Dividend yield is the usual stand-in and it is a poor one: it
conflates cheapness with payout policy and with quality, and it drops to zero for
any company that suspends its dividend &mdash; which tends to happen precisely
when the stock has become cheap.

Do not skip past this. **Exposure quality is the
binding constraint on a cross-sectional model.** The regression machinery is a
morning's work; getting clean, point-in-time, survivorship-free fundamentals is
what the vendors actually charge for.

!!! warning "Point-in-time, and why it matters"
    Our exposures use *today's* share count, so the size exposure for 2023 is
    approximate &mdash; see the note in Module 1 about NatWest. A real model uses
    the share count as it was reported at the time, along with the restated
    accounts as they were *then* known, not as they were subsequently corrected.
    Getting this wrong builds a backtest that quietly knows the future.
