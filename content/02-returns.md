---
number: 2
slug: returns
title: Returns, and the square root of time
summary: Three frequencies, log versus simple, and why annualising daily vol does not quite match annualising monthly vol.
time: 60 min
---

Now the arithmetic starts. You are going to build three return series from one
price series, annualise all three, and then explain why they disagree.

!!! excel "The file you need from here on"
    Work from the **[core workbook](/download/workbook?dataset=core)** &mdash; 81
    names, 2005 onwards, already screened and trimmed to a complete rectangle
    with no gaps.

    This is the same data you were picking over in Module 1, after the decisions
    you just made have been applied. Everyone uses this file from now on, so that
    everyone's numbers agree. The ragged raw file has done its job.

## Simple or log?

<div class="formula">
simple: &nbsp; r<sub>t</sub> = P<sub>t</sub> / P<sub>t-1</sub> &minus; 1
&nbsp;&nbsp;&nbsp;&nbsp;
log: &nbsp; r<sub>t</sub> = ln(P<sub>t</sub> / P<sub>t-1</sub>)
</div>

Both are defensible. The rule of thumb on this desk:

- **Log returns** add up across *time*. Twelve monthly log returns sum to the
  annual log return. They are what you want for compounding, and they are
  symmetric: &minus;50% then +100% nets to zero.
- **Simple returns** add up across *assets*. A portfolio's simple return is the
  weighted sum of its holdings' simple returns. Log returns do **not** have this
  property &mdash; the log return of a portfolio is not the weighted average of
  log returns.

Since a covariance matrix exists to be squeezed by a weight vector, and weights
aggregate across assets, **we use simple returns throughout**. Build both if you
like; over daily horizons they differ in the fourth decimal place.

!!! excel "Doing it in Excel"
    With your prices in `Prices!B2:CD5407`, put this in the first cell of a new
    `ReturnsD` sheet and drag:
    ```
    =Prices!B3/Prices!B2-1
    ```
    Or, if you want the whole block in one formula on a 365 build:
    ```
    =Prices!B3:CD5407/Prices!B2:CD5406-1
    ```

    **Label your `ReturnsD` tab properly.** Two things, and both will save you
    from a bug later:

    - A **date column** down the left. You will need it constantly &mdash; for
      filtering to Wednesdays, for cutting windows, for finding a crisis.
    - A **top row of tickers**, copied across from the `Prices` tab. When you
      later feed a returns block into a covariance matrix and then multiply by a
      weight vector, everything depends on the columns being in the order you
      think they are. Labels are how you check.

    **On dates:** conventionally a daily return is labelled with its **end**
    date. The return from Monday's close to Tuesday's close is Tuesday's return,
    because Tuesday is when you would have earned it. So your first return sits
    against the **second** date in the price file, not the first, and your
    `ReturnsD` tab has exactly one row fewer than `Prices`.

    That sounds obvious written down. It is also the single most common way to
    end up one row out, which puts every stock's returns against the wrong date
    and quietly wrecks every correlation in the model.

## Weekly: use Wednesdays

Do not just take every fifth row. Sample **Wednesday closing prices**, then take
returns of that series.

The reason is the one from Module 1: UK market holidays cluster on Mondays and
Fridays &mdash; Good Friday, Easter Monday, May Day, the spring and August bank
holidays. A Friday-anchored week is regularly a four-day week pretending to be a
five-day one, which puts a lumpy, seasonal error straight into your variance.
Wednesday is the quietest day of the UK week.

!!! excel "Getting Wednesdays"
    **Route one: filter the rows you have.** Add a helper column next to your
    dates:
    ```
    =WEEKDAY(A2,2)=3
    ```
    (`WEEKDAY` with return-type 2 makes Monday 1, so Wednesday is 3.) Then filter
    to `TRUE`, or use `FILTER`:
    ```
    =FILTER(A2:CD5407, WEEKDAY(A2:A5407,2)=3)
    ```

    **Route two: build the grid you want.** Often easier. Put any Wednesday in a
    cell, then below it:
    ```
    =A2+7
    ```
    and fill down. You now have a clean weekly calendar that owes nothing to
    what happens to be in the price file.

    Route two leaves you needing to pull a price for each of those dates, and
    some of them will be bank holidays with no row in the file. The answer is
    an approximate-match **`VLOOKUP`**, which snaps each grid date onto the last
    real trading day at or before it. See *Snapping a date grid onto real
    trading days*, further down this page &mdash; it works identically for
    weekly and monthly.

## Monthly: use month ends

Same two routes as the weekly case.

**Filter the rows you have.** Flag a row when the month of the *next* date
differs from the month of this one:

```
=MONTH(A3)<>MONTH(A2)
```

That marks the final trading day of each month. Filter on it.

**Or build the grid.** `EOMONTH` gives you calendar month ends directly &mdash;
put a start date in a cell, then below it:

```
=EOMONTH(A2,1)
```

and fill down, for a clean series of month ends.

The catch is that the last *calendar* day of a month is rarely a *trading* day.
31 August is a bank holiday about one year in seven; 25 December never trades.
So you have a grid of dates, some of which have no row in the price file.

!!! excel "Snapping a date grid onto real trading days"
    This is the trick worth learning, and it solves the weekly and monthly cases
    identically.

    `VLOOKUP` with its fourth argument set to `TRUE` does an **approximate**
    match: on a column sorted ascending, it returns the row with the largest
    value **less than or equal to** your lookup date. Which is exactly the
    behaviour you want &mdash; "give me the last trading day at or before this
    date."

    With your grid dates down column A and your tickers along row 1 (that top
    row of tickers from earlier now earns its keep):
    ```
    =VLOOKUP($A2, Prices!$A:$CD, MATCH(B$1, Prices!$A$1:$CD$1, 0), TRUE)
    ```
    Drag it across and down. Every bank holiday silently resolves to the
    previous trading day, which is the convention you want, and you never have
    to special-case Good Friday.

    Three things that will bite you:

    - The lookup column **must be sorted ascending**. Dates in the price file
      are, but if you have re-sorted anything, `TRUE` will return confident
      nonsense rather than an error.
    - A grid date **before** the first row of prices gives `#N/A`. Start your
      grid inside the sample.
    - It snaps **backwards**, always. A grid date after your last price returns
      the last price you have, rather than an error, which will quietly flatten
      the most recent return to zero. Stop the grid at your final date.

    **Bonus marks** if you work out `XLOOKUP` as well. Its fifth argument is a
    match mode, and `-1` means "exact match, or the next smaller item" &mdash;
    the same snapping behaviour, without the fragile column counting:
    ```
    =XLOOKUP($A2, Prices!$A:$A, Prices!B:B, , -1)
    ```

    Further bonus marks for constructing some Frankenstein formula out of
    `INDEX` and `MATCH` instead. `MATCH` with a third argument of `1` is the
    same approximate match on its own, handing back a row number for `INDEX` to
    fetch from:
    ```
    =INDEX(Prices!B:B, MATCH($A2, Prices!$A:$A, 1))
    ```
    This is the route the purists prefer, on the grounds that it does not care
    where the lookup column sits relative to the answer. They are right, and
    they will tell you so.

## Annualising: the square root of time

<div class="formula">
&sigma;<sub>annual</sub> = &sigma;<sub>period</sub> &times; &radic;(periods per year)
</div>

With 252 trading days, 52 weeks and 12 months:

| Frequency | Multiplier |
|---|---|
| Daily | &radic;252 &asymp; 15.87 |
| Weekly | &radic;52 &asymp; 7.21 |
| Monthly | &radic;12 &asymp; 3.46 |

Note it is the **volatility** that scales with &radic;T, because **variance**
scales with T. Variance is additive over independent periods; standard deviation
is not. If you ever find yourself multiplying a volatility by 252, stop.

!!! excel "The calculation"
    ```
    =STDEV.S(ReturnsD!B2:B5406) * SQRT(252)
    ```
    Use `STDEV.S` (sample, divides by n&minus;1), not `STDEV.P`. With thousands of
    observations it makes no practical difference, but the sample estimator is
    what everyone else means, and matching convention matters more than you think.

    Some particularly ancient members of the team still insist on plain
    `STDEV`, which is ambiguous about which one it means. Excel quietly covers
    for them by defaulting it to `STDEV.S`, so they have got away with it for
    twenty-five years and see no reason whatsoever to stop now. You may form
    your own view on whether a function deprecated in 2010 constitutes a house
    style or a personality trait.

    Be warned that at least one of them had a hand in writing this exercise, so
    expressing a strong opinion on the matter is a career decision rather than a
    technical one.

## Now the interesting bit: they will not agree

Compute the annualised volatility of your assigned stock three ways. You will get
three different numbers &mdash; typically the daily figure highest and the monthly
lowest, often by two or three percentage points.

This is not an error in your spreadsheet. The &radic;T rule assumes returns are
**independent and identically distributed**. Real returns are not:

- **Negative autocorrelation at short horizons.** Bid-ask bounce and
  over-reaction mean a down day is slightly more likely to be followed by an up
  day. Sum the variance over a week and the cross terms are negative, so the week
  is less volatile than 5 &times; a day. Scaling daily vol up therefore
  *overstates* weekly risk.
- **Volatility clustering.** Calm begets calm, crisis begets crisis. Returns are
  not identically distributed through time at all.
- **Fewer observations.** Your monthly series has around 250 points against
  5,400 daily. The standard error of a volatility estimate is roughly
  &sigma;/&radic;(2T), so the monthly estimate is simply noisier.

!!! tip "The practitioner's answer"
    Match the estimation frequency to your decision horizon. If you rebalance
    monthly, monthly returns describe your risk best, whatever the daily number
    says. Most equity risk models use weekly as the compromise: enough
    observations to estimate a large covariance matrix, long enough to shed most
    of the microstructure noise.

Run the same comparison on a high-beta bank and on a utility. The gap between
daily and monthly is usually wider for the bank. Ask yourself why.

## What to hand in

Three annualised volatilities for your assigned stock, below. And a one-line
answer, to yourself, to: *which of these three would you quote to a portfolio
manager, and why?*
