---
number: 5
slug: ewma
title: Time windows and exponential weighting
summary: Your volatility estimate depends as much on the window you chose as on the market. Watch it move through 2008 and 2022.
time: 75 min
---

Everything so far treated 2008 and last Tuesday as equally informative. This probably
is not the case.

## Choose your window

Take your portfolio and compute its annualised volatility over the full sample.
Now recompute it using only the last 52 weeks. Then only the last 260.

The numbers will differ substantially &mdash; often by a factor of two. Nothing
about your portfolio changed. Only the window did.

!!! excel "Rolling windows"
    Put the window length in one cell, say `Ctrl!B1 = 260`, and the number of
    weekly observations in another:
    ```
    Ctrl!B3   =COUNT(ReturnsW!B2:B1115)
    ```
    which is 1,114. Then pick out the last N rows of your demeaned block with
    `OFFSET`:
    ```
    =OFFSET(Dev!$B$2, Ctrl!$B$3 - Ctrl!$B$1, 0, Ctrl!$B$1, 81)
    ```
    Feed that into the same `MMULT(TRANSPOSE(...), ...)` as Module 3, dividing by
    `Ctrl!B1 - 1` rather than the full count. Now typing a new window length
    recalculates everything, and you can watch the answer move.

    Count the data rows only. If your `Dev` sheet keeps the column means in row 1,
    as Module 3 suggests, then `COUNT(Dev!B:B)` picks those up too and every
    window quietly ends one row past the end of your data.

    `OFFSET` is volatile. The non-volatile equivalent glues two `INDEX` calls
    together into a range:
    ```
    =INDEX(Dev!$B$2:$CD$1115, Ctrl!$B$3 - Ctrl!$B$1 + 1, 0):INDEX(Dev!$B$2:$CD$1115, Ctrl!$B$3, 0)
    ```
    Strictly, a window should be demeaned using the mean of that window rather
    than of the whole sample. Over 260 weeks the difference is small enough to
    ignore while you are exploring.

### The trade-off

- **Short window.** Responsive &mdash; picks up a regime change quickly. Also
  noisy, and it forgets crises entirely. A 52-week window in early 2007 had never
  heard of a financial crisis.
- **Long window.** Stable, and remembers tail events. Also sluggish: in March 2020
  a ten-year window was still mostly telling you about 2012.

There is no correct answer. There is only being explicit about which error you
prefer.

## Exponential weighting

Rather than a hard cut-off &mdash; everything inside the window counts fully,
everything outside counts zero &mdash; let influence decay smoothly.

<div class="formula">
&Sigma; = (1 &minus; &lambda;) &Sigma;<sub>k</sub> &lambda;<sup>k</sup> r<sub>t&minus;k</sub> r&prime;<sub>t&minus;k</sub>
</div>

The most recent observation gets weight (1&minus;&lambda;), the one before
&lambda;(1&minus;&lambda;), and so on. The weights sum to one.

**Half-life** &mdash; how long until an observation counts half as much &mdash; is
the intuitive handle:

<div class="formula">half-life = ln(0.5) / ln(&lambda;)</div>

| &lambda; | Half-life (daily) | Half-life (weekly) |
|---|---|---|
| 0.94 | 11 days | 11 weeks |
| 0.97 | 23 days | 23 weeks |
| 0.99 | 69 days | 69 weeks |

&lambda; = 0.94 is RiskMetrics' original daily parameter and has become a
convention. It is not sacred &mdash; it was fitted to 1990s data. Use it as a
starting point, not an answer.

## Building it in Excel: one trick

This looks harder than the sample covariance. It is not, because of one
rearrangement.

You want a weighted sum of outer products. But note that scaling **row t** of your
demeaned return matrix by &radic;w<sub>t</sub> and then forming R&prime;R gives
exactly the weighted sum &mdash; because each term of the product picks up
&radic;w<sub>t</sub> twice.

So the recipe is:

1. Build a column of weights, oldest row first:
   `=(1-lambda) * lambda^(n - ROW() + 1)`
2. Normalise so they sum to 1: divide by their total.
3. Multiply each row of your returns by the **square root** of its weight. Use
   the raw weekly returns, not the demeaned ones from Module 3 &mdash; see the
   convention note below.
4. Run the **same** `MMULT(TRANSPOSE(Rw), Rw)` as Module 3 &mdash; with no
   division by T&minus;1, because the weights already sum to one.

!!! excel "In practice"
    Weight column, with `lambda` in `Ctrl!B2` and T rows of data:
    ```
    =(1-Ctrl!$B$2) * Ctrl!$B$2^(Ctrl!$B$3 - (ROW()-1))
    ```
    where `Ctrl!B3` is the count of weekly observations, so the most recent
    row gets an exponent of zero. Then normalise. Scaled returns on a `ScaledW`
    sheet, with the weights in its column A:
    ```
    =ReturnsW!B2 * SQRT($A2)
    ```
    And the matrix:
    ```
    =MMULT(TRANSPOSE(ScaledW!B2:CD1115), ScaledW!B2:CD1115)
    ```
    One cell changes &lambda; and the entire risk model updates. That is worth
    the setup.

!!! tip "A convention you should know"
    RiskMetrics does **not** demean returns before computing EWMA covariance: it
    assumes the mean is zero. At daily and weekly frequency the mean is tiny
    relative to the volatility, and not estimating it removes a source of noise.
    Our answer key follows that convention, which is why the recipe above uses
    raw returns. On this data demeaning first moves the answer by up to about
    1.3% &mdash; inside the checker tolerance, but closer to the edge than you
    want, so if an EWMA check is refusing you, that is the first thing to look at.

## The exercise that makes the point

Compute your portfolio's EWMA volatility at each week-end through the sample and
chart it. Overlay a rolling 104-week sample volatility.

You should see:

- **September 2008.** EWMA vaults upward within weeks. The rolling window climbs
  slowly, still diluted by four years of calm.
- **2009&ndash;2010.** EWMA falls back quickly as markets settle. The rolling
  window stays elevated far longer &mdash; 2008 is still inside it.
- **March 2020.** The sharpest move in the sample. EWMA(0.94) roughly doubles in
  a month.
- **September 2022.** The gilt and LDI crisis, which is worth dwelling on given
  where you work &mdash; and which is *not* what most people expect. Aggregate
  equity volatility barely moved: EWMA(0.94) averaged 15.1% over September and
  October against 14.8% for a rolling 104-week window. It was a gilt crisis, not
  an equity crisis.

    The sector detail is the interesting part. Daily volatility in those two
    months, as a multiple of the same names' calm-2022 volatility:

    | Industry | Multiple |
    |---|---|
    | Real Estate | **1.60** |
    | Utilities | 1.25 |
    | Financials | 0.99 |
    | Basic Materials | 0.90 |
    | Energy | 0.74 |

    So it hit **rate-sensitive** equity, not financial equity. Real estate and
    utilities are long-duration assets &mdash; bond proxies &mdash; and a violent
    move in gilt yields repriced them hard. Banks, which earn more as rates rise,
    did not budge. If your instinct was "financial crisis, so banks", this is a
    useful correction: ask what the shock actually transmits *through*.

- **The one-year anniversary problem.** Watch a rolling 52-week estimate through
  early 2021. On 24 February it reads **34.5%**; five weeks later, on 31 March,
  **21.1%**. Nothing happened in the market. The Covid crash simply left the
  window.

    EWMA(0.94) over the identical weeks goes 21.8% to 18.8%. A 3 point drift
    against a 13 point cliff.

    This is a genuine operational headache, not a curiosity: the number moves,
    a portfolio manager asks why, and the honest answer is "because of a date".
    Being able to say that clearly, and to have the EWMA comparison ready, is
    most of the job.

EWMA does not have that problem. Old observations fade rather than falling off a
ledge. That is the real argument for it.

## What to take away

1. Quote a volatility without stating its window and you have said nothing.
2. Short windows react; long windows remember. Choose deliberately.
3. EWMA gets responsiveness without the anniversary cliff.
4. &lambda; = 0.94 is a convention, not a law.
