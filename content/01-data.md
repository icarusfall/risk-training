---
number: 1
slug: data
title: The data, and what is wrong with it
summary: Ragged histories, bad prints, survivorship bias, and the benchmark that is lying to you.
time: 60 min
---

Before any maths: look at the data. Properly. This module has almost no formulas
in it and it is the one that separates people who are good at this job from
people who produce confident nonsense.

Download the **[raw workbook](/download/workbook?dataset=raw)** and open the
`Prices` tab.

!!! warning "Use the raw file for this module, and only this module"
    That link gives you the panel exactly as it arrives from the data provider:
    all 100 names, ragged start dates, real gaps, and the bad prices still in.
    It is the only file you can actually learn this from &mdash; you cannot
    practise spotting a broken price series in a file somebody has already
    cleaned.

    **From Module 2 onward, switch to the
    [core workbook](/download/workbook?dataset=core).** That is the same data
    after we have made the decisions you are about to make, trimmed to a tidy
    rectangle. Everyone works from the same canonical file after this, because
    otherwise no two people's answers would agree.

## 1. The panel is ragged, on purpose

You have 100 FTSE 100 constituents. You do not have 100 usable price histories.

Sort the `Universe` tab by the `first_date` column. Some names go back to 1995.
Nine started after 2015. One of them &mdash; Metlen, which joined the index
recently &mdash; has barely a year.

This is your first judgement call, and there is no correct answer:

- **Keep every name** and your covariance matrix can only span the shortest
  history. That is about thirteen months, which throws away every crisis in the
  sample.
- **Keep the long window** and you must drop the short names, losing real
  companies from the model.
- **Something in between**, which is what everyone actually does.

!!! excel "Doing it in Excel"
    Have a look at the `Prices` tab. As you scroll along the top rows from left
    to right, you will find some price histories that do not begin until later
    and so are blank at the top.

    If you want to see how much history each stock has, try using the `COUNT`
    command to tell you &mdash; put it in a spare row above the prices and drag
    it across. You can then sort or filter on that row.

    When you decide to reject a column, delete it rather than leaving it in with
    gaps at the top. Blank cells get read as zeros later on, and a zero return
    is not the same thing as a missing one.

We offer three files on the [data page](/data): **Raw** (this one),
**Core** from 2005, and **Long** from 1995, which keeps a longer history at the
cost of roughly a quarter of the names. Have a look at all three and notice what
each trade costs you.

## 2. Some of the prices are simply wrong

Free data is not clean. Here is a real example from this dataset &mdash; Polar
Capital Technology Trust, over six consecutive trading days:

| Date | Price (p) |
|---|---|
| 2011-04-27 | 371.90 |
| 2011-04-28 | 373.50 |
| **2011-04-29** | **37.35** |
| 2011-05-03 | 377.30 |

That is a factor of ten, for one day, and then it comes back. As a return series
that is &minus;90% followed by +910%. Drop that into a covariance matrix and the
stock appears to have 285% annualised volatility &mdash; and because it is so
volatile it dominates everything downstream. When we first ran a principal
components analysis on the uncleaned panel, **this single stock accounted for
half of the first principal component**. The "market factor" was one broken
investment trust.

Worse, the same name has breaks that *do not* come back: on 2013-01-02 it drops
from 363.50 to 37.43 and simply stays there.

### Your task

Hunt them.

Build a new returns tab with the daily returns for each stock over time.
Technically quants prefer the log return, `=LN(B3/B2)`, but pretty much everyone
just does `=B3/B2-1`. Either is fine for finding outliers.

!!! tip "One Excel trap worth knowing now"
    Excel's `LOG` function is base 10. The natural log &mdash; the one you want
    for a log return &mdash; is `LN`. `LOG(B3/B2)` will give you a number, it
    will look plausible, and it will be wrong by a factor of about 2.3.

Then use conditional formatting to flag any absolute daily move above, say, 40%.
Look at each one and decide:

- **A real market event.** Barclays genuinely rose 73% on 26 January 2009. RBS
  genuinely fell 67% on 19 January 2009. These are the most interesting days in
  your sample and you must not delete them.
- **A bad print that reverts.** Delete and interpolate.
- **A permanent scale break.** Usually undeclared corporate actions. Without a
  corporate-action feed you cannot safely repair these &mdash; drop the name.

!!! tip "The bank holiday trap"
    Many of the bad prints in this panel fall on Christmas Day, Good Friday and
    the May Day bank holiday &mdash; days the London Stock Exchange was shut. The
    data provider stamps a value anyway. This is also why, from the next module
    onward, we sample **weekly returns Wednesday-to-Wednesday**: UK holidays
    cluster on Mondays and Fridays. In this dataset, Wednesday sampling lands on
    a non-trading day 10 times; Friday 32 times; Monday 106.

When you are done, compare your list against our cleaning log &mdash; either
[on the data page](/data?dataset=raw) or as a
[CSV](/download/quality?dataset=raw). We repair
and exclude on published rules &mdash; and reasonable people would draw the line
somewhere slightly different.

## 3. Survivorship bias, which we cannot fix

These are **today's** FTSE 100 members, with their history backfilled.

Think about what is missing. Northern Rock. RBS at its pre-crisis size. Carillion.
Every company that fell out of the index after doing badly, which is generally
*why* they fell out. Your sample is the survivors.

The effect is not subtle. Over the 2005-onward window:

| Series | Annualised return |
|---|---|
| `^FTSE` (real FTSE 100, price only) | +3.8% |
| `CAPFIXED_TR` (our composite, total return) | +9.0% |

Some of that gap is dividends &mdash; roughly 3.5%/yr. The rest is survivorship,
and it is worth about **2 percentage points a year of entirely fictional return**.

!!! warning "What this does to your risk numbers"
    It flatters them. Companies that blew up are absent, so your volatility and
    especially your tail risk are understated. A proper risk system uses
    point-in-time constituents. You cannot here, and knowing that you cannot is
    the lesson. Say it out loud in any meeting where someone quotes a backtest.

## 4. The benchmark that is lying to you

Open the `Benchmarks` tab.

These are the top-level prices of other benchmarks, besides the FTSE 100 that we
are digging into. In each case we are just looking at the combined value of the
index &mdash; a single number per day &mdash; rather than breaking it out into
all the component stocks as we have done on the `Prices` tab. You will see later
how these become useful, in the time-series section of the tutorial.

A key distinction is whether these total levels account for dividends or not.

An index can be quoted two ways. A **price index** tracks only the share prices
of its members. A **total return index** assumes every dividend is reinvested
back into the index. Over twenty years that difference compounds into something
enormous, and if you compare the wrong pair of series you will draw the wrong
conclusion.

Two of the series look as though they should be identical:

- `ISF.L` &mdash; iShares Core FTSE 100, **distributing**
- `CUKX.L` &mdash; iShares Core FTSE 100, **accumulating**

Same index, same manager, same underlying holdings. The only difference is what
the fund does with the dividends it receives: the *distributing* share class
pays them out to you as cash, and the *accumulating* one reinvests them inside
the fund.

Compute the annualised return of each, over the period where both exist.

You should find `CUKX.L` beating `ISF.L` by around 3.7% a year, which is the FTSE
100 dividend yield. The accumulating share class reinvests dividends inside the
fund, so its price is a total return. The distributing one pays them
out &mdash; and our data provider's "adjusted" series does not add them back,
despite appearances. `ISF.L` tracks the **price** index to within 0.1% a year.

**When you regress a stock against "the market" in Module 7, use `CUKX.L`.**
Regressing total returns on a price index quietly biases your alphas down by the
dividend yield.

!!! tip "Keep this in proportion"
    Dividends matter enormously for *returns* and almost not at all for *risk*.
    Volatility is a second moment, and a smooth 3.5%/yr yield barely touches it.
    Measured on this data: `CUKX.L` annualised vol is 15.322%, `ISF.L` is 15.336%
    &mdash; a difference of **0.014 percentage points**. So if you only have price
    returns, your vol estimate is fine. Do not let anyone tell you otherwise.

## 5. Currency, hiding in plain sight

Three names in the FTSE 100 are not quoted in sterling: Compass and IHG in US
dollars, Metlen in euros. We have converted them to pence so the file is
consistent &mdash; but be clear about what that means. Their return series now
contains an **unhedged FX move** as well as a stock move. For a sterling investor
that is part of the risk. For understanding the *business*, it is noise.
Real risk systems split the two.

---

## What to take away

1. Look at the data before you model it. Always.
2. Distinguish a real crash from a bad print. The test is whether it reverts.
3. Know which biases you have chosen to live with, and say so unprompted.
4. "The index" is not one thing. Check what your benchmark actually measures.
