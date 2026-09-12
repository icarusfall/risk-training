---
number: 2
slug: returns
title: Returns, and the square root of time
summary: Three frequencies, log versus simple, and why annualising daily vol does not quite match annualising monthly vol.
time: 60 min
---

Now the arithmetic starts. You are going to build three return series from one
price series, annualise all three, and then explain why they disagree.

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
    Keep the date column alongside. You will need it constantly.

## Weekly: use Wednesdays

Do not just take every fifth row. Sample **Wednesday closing prices**, then take
returns of that series.

The reason is the one from Module 1: UK market holidays cluster on Mondays and
Fridays &mdash; Good Friday, Easter Monday, May Day, the spring and August bank
holidays. A Friday-anchored week is regularly a four-day week pretending to be a
five-day one, which puts a lumpy, seasonal error straight into your variance.
Wednesday is the quietest day of the UK week.

!!! excel "Getting Wednesdays"
    Add a helper column next to your dates:
    ```
    =WEEKDAY(A2,2)=3
    ```
    (`WEEKDAY` with return-type 2 makes Monday 1, so Wednesday is 3.) Then filter
    to `TRUE`, or use `FILTER`:
    ```
    =FILTER(A2:CD5407, WEEKDAY(A2:A5407,2)=3)
    ```
    If a particular Wednesday was a holiday, take the previous trading day rather
    than dropping the week.

## Monthly: use month ends

```
=EOMONTH(A2,0)=A2
```
will not quite work, because the last *trading* day is rarely the last *calendar*
day. Easier: flag a row when the month of the next date differs from the month of
this one.

```
=MONTH(A3)<>MONTH(A2)
```

That marks the final trading day of each month. Filter on it.

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
