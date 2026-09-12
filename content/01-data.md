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

Download the [starter workbook](/download/workbook) and open the `Prices` tab.

## 1. The panel is ragged, on purpose

You have 100 FTSE 100 constituents. You do not have 100 usable price histories.

Sort the `Universe` tab by the `From` column. Some names go back to 1995. Several
started after 2015. At least one has barely three years.

This is your first judgement call, and there is no correct answer:

- **Keep every name** and your covariance matrix can only span the shortest
  history &mdash; perhaps three years, which throws away every crisis.
- **Keep the long window** and you must drop the short names, losing real
  companies from the model.
- **Something in between**, which is what everyone actually does.

!!! excel "Doing it in Excel"
    Put `=COUNT(B2:B5407)` under each price column to count observations, or
    `=MIN(IF(B2:B5407<>"",$A$2:$A$5407))` for the first date. Then use those as
    a filter row you can sort by. Delete the columns you reject &mdash; do not
    leave them in with gaps, because gaps silently poison a covariance matrix.

We offer two windows on the [data page](/data): **Core** from 2005 (more names)
and **Long** from 1995 (longer history, roughly a quarter fewer names). Look at
both and notice what the trade costs you.

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

Hunt them. Build a returns column (Module 2 will formalise this, but
`=B3/B2-1` will do) and use conditional formatting to flag any absolute daily
move above, say, 40%. Then look at each one and decide:

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

When you are done, compare your list against our [cleaning log](/data). We repair
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

Open the `Benchmarks` tab. There are several series and they do not mean the same
thing. Two in particular:

- `ISF.L` &mdash; iShares Core FTSE 100, **distributing**
- `CUKX.L` &mdash; iShares Core FTSE 100, **accumulating**

Same index, same manager, same holdings. Compute the annualised return of each
over the period where both exist.

You should find `CUKX.L` beating `ISF.L` by around 3.7% a year, which is the FTSE
100 dividend yield. The accumulating share class reinvests dividends inside the
fund, so its price genuinely is a total return. The distributing one pays them
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
that is genuinely part of the risk. For understanding the *business*, it is noise.
Real risk systems split the two.

---

## What to take away

1. Look at the data before you model it. Always.
2. Distinguish a real crash from a bad print. The test is whether it reverts.
3. Know which biases you have chosen to live with, and say so unprompted.
4. "The index" is not one thing. Check what your benchmark actually measures.
