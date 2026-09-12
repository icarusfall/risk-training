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

With 81 names that is 6,561 cells, or 3,321 genuinely distinct numbers. You are
not going to type 3,321 formulas.

## The wrong way, and why we mention it

You *could* write `=COVARIANCE.S(ReturnsW!B:B, ReturnsW!C:C)` and fill it across
a grid. It works. People do it. It is 4,950 formulas for 100 names, it recalculates
slowly, and &mdash; more importantly &mdash; it teaches you nothing about what a
covariance matrix *is*.

If you want to do it this way, go ahead. The self-check does not care. But do read
the next section, because everything from Module 5 onward assumes you have the
matrix form in your head.

## The right way: it is one matrix multiplication

Take your weekly returns as a matrix **R** with T rows (dates) and N columns
(stocks). Subtract each column's mean, so every column is centred on zero. Then:

<div class="formula">&Sigma; = R&prime;R / (T &minus; 1)</div>

That is the entire thing. One transpose, one matrix multiply, one division.

Why it works: the (i,j) entry of R&prime;R is the sum over all dates of
r<sub>i,t</sub> &times; r<sub>j,t</sub>. Since the columns are demeaned, that sum
divided by T&minus;1 is exactly the sample covariance. The matrix product computes
all 3,321 of them simultaneously, because that is what matrix multiplication is.

!!! excel "Doing it in Excel"
    Say your weekly returns are in `ReturnsW!B2:CC1116` (T=1115 rows, N=80 cols).

    **Step 1 &mdash; demean.** On a new sheet `Dev`, cell `B2`:
    ```
    =ReturnsW!B2:CC1116 - AVERAGE(ReturnsW!B2:B1116)
    ```
    That will not broadcast correctly. Do it column-wise instead &mdash; in `B2`:
    ```
    =ReturnsW!B2 - B$1
    ```
    with row 1 holding `=AVERAGE(ReturnsW!B2:B1116)` for each column. Drag across
    and down. Unglamorous, reliable.

    **Step 2 &mdash; the matrix.** On a `Cov` sheet, in one cell:
    ```
    =MMULT(TRANSPOSE(Dev!B2:CC1116), Dev!B2:CC1116) / (COUNT(Dev!B2:B1116)-1)
    ```
    On Microsoft 365 this spills into an 80&times;80 block automatically. Label the
    rows and columns with your tickers &mdash; you will regret it if you do not.

!!! warning "Performance"
    That multiply is 1115 &times; 80 &times; 80 &asymp; 7 million operations, and
    Excel redoes it on every recalculation. It is fine, but if the sheet becomes
    sluggish, switch to **Formulas &rarr; Calculation Options &rarr; Manual** and
    press F9 when you want it. This is also why we suggest weekly rather than
    daily returns for the full-universe matrix: daily would be five times the work
    for a noisier answer.

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
    answer, which is the worst kind.

    If you would rather avoid `MMULT` entirely:
    ```
    =SQRT(SUMPRODUCT(Cov!B2:M13, MMULT(B2:B13, TRANSPOSE(B2:B13)))) * SQRT(52)
    ```
    or build the full grid of w<sub>i</sub>w<sub>j</sub>&Sigma;<sub>ij</sub> on a
    tab and sum it. All the same number.

## What you should notice

Your portfolio's volatility should come out **below** the weighted average of the
individual stock volatilities. That gap is diversification, and it is the only
free lunch in the business. Compute both and look at the difference.

Now try it: set one weight to 100% and the rest to zero. You should get that
stock's own volatility back. If you do not, your alignment is wrong.

## A number to consider

You estimated 3,321 parameters from 1,115 observations. Three times as many
unknowns as data points.

The matrix still *works* &mdash; it is positive semi-definite by construction,
because R&prime;R always is. But a good chunk of what it contains is estimation
noise dressed as correlation. Modules 7, 8 and 9 are three different escapes from
that problem. Keep the number 3,321 in mind until then.
