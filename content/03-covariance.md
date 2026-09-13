---
number: 3
slug: covariance
title: The covariance matrix
summary: Build the whole matrix in one formula, then squeeze it with a weight vector to get portfolio volatility.
time: 90 min
---

This is the core of the exercise. Everything after it is a variation.

## Why covariance, and why it is nearly enough

A covariance between two sets of returns captures both how much each varies by
itself, *and* the correlation between them. In fact you can define a covariance
exactly that way:

<div class="formula">
&sigma;<sub>ij</sub> = &sigma;<sub>i</sub> &times; &sigma;<sub>j</sub> &times; &rho;<sub>ij</sub>
</div>

the product of each stock's standard deviation and the correlation between them
&mdash; a number running from &minus;1 to +1, representing how much they move
with respect to each other.

So it is a handy **portmanteau** measure for each pair, capturing three separate
bits of information in one number. Note what happens on the diagonal, where a
stock meets itself: the correlation is 1, so the covariance collapses to
&sigma;<sub>i</sub>&sup2;, the plain variance. The same number does both jobs.

Once you have this for every possible pair of stocks, you have basically
captured everything &mdash; almost everything, until we move away from Normal
land &mdash; about the risk of any combination of these stocks. Any portfolio at
all, including ones nobody has thought of yet.

In a sense, all a risk model **is** is a covariance matrix, calculated in some
way. Modules 5, 7, 8 and 9 are four different ways of calculating one. They
disagree completely about the method and not at all about the object.

And the way to retrieve a single risk number from the model is to multiply your
chosen portfolio weights by the covariance matrix. Although, as you will see,
you actually multiply by the weights **twice** &mdash; once vertically and once
horizontally.

## What you are building

For N stocks, &Sigma; is an N&times;N matrix where the entry in row *i*, column
*j* is the covariance between stock *i* and stock *j*. The diagonal holds each
stock's variance.

With 81 names that is 6,561 cells, or 3,321 distinct numbers. You are
not going to type 3,321 formulas.

## The quick way: a grid of `COVARIANCE.S`

Lay your tickers down column A and across row 1 of a `Cov` sheet, then fill the
grid with one covariance per pair. Every cell asks the same question &mdash;
*what is the covariance between this row's stock and this column's stock?*

It is 6,561 cells for 81 names, it recalculates more slowly than the matrix
version, and it works perfectly well. It earns exactly the same marks.

The art is in getting each cell to point at the right two columns of returns
without typing 6,561 different ranges. There are a few ways, and the team is
split on which is best:

!!! excel "Pointing each cell at the right columns"
    Assume weekly returns in `ReturnsW!B2:CD1115` (1,114 weeks, 81 stocks),
    tickers in `ReturnsW!B1:CD1`, and your `Cov` grid starting at `B2` with the
    same tickers, in the same order, down column A and across row 1.

    **`OFFSET`**, walking across by the row and column number of the cell you are
    in:
    ```
    =COVARIANCE.S(OFFSET(ReturnsW!$A$2, 0, ROW()-1, 1114, 1),
                  OFFSET(ReturnsW!$A$2, 0, COLUMN()-1, 1114, 1))
    ```

    **`INDIRECT`**, building each range as a text address. The most transparent
    about what it is doing, and the most tedious to type:
    ```
    =COVARIANCE.S(INDIRECT("ReturnsW!" & ADDRESS(2, ROW(), 4) & ":" & ADDRESS(1115, ROW(), 4)),
                  INDIRECT("ReturnsW!" & ADDRESS(2, COLUMN(), 4) & ":" & ADDRESS(1115, COLUMN(), 4)))
    ```

    **`INDEX` with `MATCH`**, looking each column up by ticker. An `INDEX` row
    argument of `0` returns the whole column:
    ```
    =COVARIANCE.S(INDEX(ReturnsW!$B$2:$CD$1115, 0, MATCH($A2, ReturnsW!$B$1:$CD$1, 0)),
                  INDEX(ReturnsW!$B$2:$CD$1115, 0, MATCH(B$1, ReturnsW!$B$1:$CD$1, 0)))
    ```
    This one has the virtue of matching on the ticker *name* rather than on
    position, so it survives someone re-sorting the columns.

    Write one cell, drag across and down, done.

!!! warning "OFFSET and INDIRECT are volatile"
    Both recalculate every time *anything* in the workbook changes, not just when
    their inputs do. Across 6,561 cells that is noticeable. It is not wrong &mdash;
    just switch calculation to manual (**Formulas &rarr; Calculation Options**)
    and press F9 when you want fresh numbers. `INDEX` is not volatile.

!!! tip "COVAR is not COVARIANCE.S"
    If you reach for the old `COVAR` function, know that it is the **population**
    covariance, dividing by *n* rather than *n*&minus;1 &mdash; the same as
    `COVARIANCE.P`.

    Note the contrast with `STDEV` in Module 2, which quietly defaults to the
    *sample* version. Excel's legacy functions are not even consistent with each
    other about which one they mean.

    With 1,114 weekly observations the difference is a factor of 1114/1113 on
    the variance, about 0.045% on the volatility. That is comfortably inside the
    checker's tolerance, so `COVAR` still gets full marks. But it is worth knowing
    which one you are using, and why the diagonal of your grid will be a hair
    below the `VAR.S` of each column.

## The pure way: seeing the guts of the calculation

The quick way gets the numbers. This way shows you what the numbers *are*, and
it is worth doing at least once even if you build your real model the quick way
&mdash; Module 5's exponential weighting and Module 9's principal components are
far easier to understand, and much easier to build, once you see a covariance
matrix as a single piece of matrix algebra.

Take your weekly returns as a matrix **R** with T rows (dates) and N columns
(stocks). Subtract each column's mean, so every column is centred on zero. Then:

<div class="formula">&Sigma; = R&prime;R / (T &minus; 1)</div>

That is all there is to it.

Why it works: the (i,j) entry of R&prime;R is the sum over all dates of
r<sub>i,t</sub> &times; r<sub>j,t</sub>. Since the columns are demeaned, that sum
divided by T&minus;1 is exactly the sample covariance &mdash; the same number
`COVARIANCE.S` gives you for that pair. The matrix product computes all 3,321 of
them simultaneously, because that is what matrix multiplication is.

!!! excel "Doing it in Excel"
    With weekly returns in `ReturnsW!B2:CD1115` (T = 1,114 rows, N = 81 columns):

    **Step 1 &mdash; demean.** Put each column's mean in row 1 of a new `Dev`
    sheet, above where its demeaned returns will go:
    ```
    =AVERAGE(ReturnsW!B2:B1115)
    ```
    then in `Dev!B2`, and dragged across and down:
    ```
    =ReturnsW!B2 - B$1
    ```
    Unglamorous and reliable. On a 365 build you can do the whole block in one
    spilled formula instead:
    ```
    =ReturnsW!B2:CD1115 - BYCOL(ReturnsW!B2:CD1115, LAMBDA(c, AVERAGE(c)))
    ```

    **Step 2 &mdash; the matrix.** On a `Cov` sheet, in one cell:
    ```
    =MMULT(TRANSPOSE(Dev!B2:CD1115), Dev!B2:CD1115) / (COUNT(Dev!B2:B1115) - 1)
    ```
    On Microsoft 365 this spills into an 81&times;81 block automatically. Label the
    rows and columns with your tickers &mdash; you will regret it if you do not.

    If you built the quick way as well, subtract one grid from the other. Every
    cell should be zero, or within floating-point noise of it.

!!! warning "Performance"
    That multiply is 1,114 &times; 81 &times; 81 &asymp; 7.3 million operations,
    and Excel redoes it on every recalculation. It is fine, but if the sheet
    becomes sluggish, switch to manual calculation and press F9 when you want it.
    This is also why we suggest weekly rather than daily returns for the
    full-universe matrix: daily would be five times the work for a noisier answer.

## Sanity checks before you go further

Do these. Every one of them has caught a real bug for someone.

1. **Symmetry.** &Sigma;<sub>ij</sub> must equal &Sigma;<sub>ji</sub>. Check a
   few pairs, or `=SUMPRODUCT(ABS(Cov-TRANSPOSE(Cov)))` should be ~0.
2. **The diagonal is variance.** `SQRT` of a diagonal entry, times &radic;52,
   must match the annualised vol you computed in Module 2 for that stock.
3. **Correlations are in range.** &Sigma;<sub>ij</sub> / (&sigma;<sub>i</sub>&sigma;<sub>j</sub>)
   must lie in [&minus;1, 1]. A value outside that means misaligned rows &mdash;
   almost always a stray blank or an off-by-one.
4. **Everything is positive.** Every diagonal entry. A negative variance means
   you have blanks being read as zeros.

!!! tip "The most common bug by far"
    A blank cell in a return block is treated as **zero**, not as missing. A stock
    that did not trade looks like a stock that did not move, which drags its
    variance and every one of its covariances toward zero. If one name looks
    implausibly calm, look for gaps.

## Portfolio volatility

Now the payoff. With a weight vector **w**:

<div class="formula">&sigma;<sub>p</sub><sup>2</sup> = w&prime;&Sigma;w &nbsp;&nbsp;&nbsp; &sigma;<sub>p</sub> = &radic;(w&prime;&Sigma;w) &times; &radic;52</div>

!!! excel "The front tab"
    Build a sheet with your tickers down column A and your weights in column B.
    Then, in a single cell:
    ```
    =SQRT(MMULT(MMULT(TRANSPOSE(B2:B13), Cov!B2:M13), B2:B13)) * SQRT(52)
    ```
    Two nested `MMULT`s: the inner one gives &Sigma;w, the outer one gives
    w&prime;(&Sigma;w). Both spill to 1&times;1, so `SQRT` just works.

    Make sure your weight order matches your covariance row order **exactly**.
    This is the second most common bug, and it produces a plausible-looking wrong
    answer, which is much harder to spot than an error.

    If you would rather avoid `MMULT` entirely:
    ```
    =SQRT(SUMPRODUCT(Cov!B2:M13, MMULT(B2:B13, TRANSPOSE(B2:B13)))) * SQRT(52)
    ```
    or build the full grid of w<sub>i</sub>w<sub>j</sub>&Sigma;<sub>ij</sub> on a
    tab and sum it. All the same number.

## What you should notice

Your portfolio's volatility should come out **below** the weighted average of the
individual stock volatilities. That gap is diversification, often called the only free lunch in finance. Compute both and look at the difference.

Now try it: set one weight to 100% and the rest to zero. You should get that
stock's own volatility back. If you do not, your alignment is wrong.

## A number to consider

You estimated 3,321 parameters from 1,114 observations. Three times as many
unknowns as data points.

The matrix still *works* &mdash; it is positive semi-definite by construction,
because R&prime;R always is. But a good chunk of what it contains is estimation
noise dressed as correlation. Modules 7, 8 and 9 are three different escapes from
that problem. Keep the number 3,321 in mind until then.
