---
number: 9
slug: pca
title: The statistical risk model
summary: Let the data find its own factors. The first one turns out to be the market, and nobody told it to be.
time: 2-3 hours
---

Modules 7 and 8 both told the model what the factors were. Module 7 said "the
market". Module 8 said "size, momentum, volatility, industry". Both times, a
human decided.

This module asks the data instead.

## What principal components are

Principal components analysis finds the directions of greatest variance in your
covariance matrix.

- **PC1** is the portfolio of your 81 stocks with the highest variance.
- **PC2** is the highest-variance portfolio *uncorrelated with PC1*.
- And so on, each orthogonal to all the ones before it.

Formally these are the eigenvectors of &Sigma;, ordered by eigenvalue. The
eigenvalue *is* the variance of that portfolio, which makes the arithmetic of
"variance explained" pleasantly direct:

<div class="formula">share of variance explained by PC<sub>k</sub> = &lambda;<sub>k</sub> / trace(&Sigma;)</div>

The trace &mdash; the sum of the diagonal &mdash; is the total variance across all
your stocks, because eigenvalues sum to the trace. So you can compute the share
explained without finding all 81 components.

## Doing eigenvectors in Excel

Excel has no `EIGEN()` function. You do not need one.

**Power iteration** is four cells and a drag. Multiply any starting vector by
&Sigma;, normalise it, and repeat. It converges to the dominant eigenvector,
because each multiplication stretches the vector further along the direction of
greatest variance:

1. Start with **v** = a column of 81 ones.
2. Compute **w** = &Sigma;**v**.
3. Normalise: **v** = **w** / &radic;(sum of **w**&sup2;).
4. Go back to step 2.

!!! excel "The layout"
    Put your starting vector in column B, then in `C2`:
    ```
    =MMULT(Cov!$B$2:$CC$82, B2:B82) / SQRT(SUMSQ(MMULT(Cov!$B$2:$CC$82, B2:B82)))
    ```
    Spill that down 81 rows, then drag the whole column right for twenty columns.
    Watch the numbers stop moving &mdash; on this data they settle after about
    fifteen iterations.

    The eigenvalue, once converged:
    ```
    =MMULT(TRANSPOSE(v), MMULT(Cov!$B$2:$CC$82, v))
    ```

    If the sheet is slow, compute `MMULT(Cov, v)` once into a helper column and
    normalise from that, rather than calling it twice in one formula.

!!! tip "This is not an approximation"
    We checked the power-iteration result against a proper numerical
    eigendecomposition (LAPACK, via numpy) on this exact dataset. The first five
    eigenvalues agree to **eleven decimal places**. The Excel route is not a
    rough-and-ready substitute; it is the same answer.

For the next component, **deflate** &mdash; subtract the one you just found:

<div class="formula">&Sigma;&prime; = &Sigma; &minus; &lambda;<sub>1</sub> v<sub>1</sub> v<sub>1</sub>&prime;</div>

Then run the identical routine on &Sigma;&prime;. Because PC1's contribution has
been removed, power iteration now converges to PC2. Repeat for as many as you
want.

!!! excel "Deflation in one formula"
    ```
    =Cov!B2:CC82 - lambda1 * MMULT(v1, TRANSPOSE(v1))
    ```
    `MMULT(v1, TRANSPOSE(v1))` is the outer product: an 81&times;81 matrix from an
    81&times;1 vector. Note the argument order &mdash; the other way round gives
    you a 1&times;1 scalar, which is a different and much less useful thing.

## What you will find

On the 81-name weekly covariance since 2005:

| Component | Variance explained |
|---|---|
| PC1 | **34.3%** |
| PC2 | 4.9% |
| PC3 | 4.4% |
| PC4 | 3.4% |
| PC5 | 3.0% |

### PC1 is the market, and nobody told it to be

Look at the PC1 loadings. **All 81 are the same sign.** It is a long-only
portfolio of the entire index.

Now score it: for each week, compute the loadings dotted with that week's
returns, giving a time series. Correlate that against the simple equal-weighted
average of all 81 stocks.

You should get about **0.991**.

That is the result worth pausing on. We handed the algorithm a covariance matrix
and nothing else &mdash; no index, no benchmark, no instruction about what a
market is &mdash; and it recovered the market almost exactly. The market factor is
not an assumption we impose on equity returns. It is the dominant feature of the
data, and any sensible method will find it.

Look at the size of the loadings, too:

- **Largest:** Barclays, NatWest, Barratt, Lloyds &mdash; banks and a housebuilder.
- **Smallest:** Reckitt, Unilever, National Grid, Severn Trent, United Utilities.

That is a beta ranking. PC1 loadings are essentially beta, rediscovered from the
covariance matrix alone.

### PC2 is a UK story

PC2 has mixed signs, which is where interpretation starts. Average the PC2
loading within each ICB industry:

| Industry | Mean PC2 loading |
|---|---|
| Basic Materials | **&minus;0.204** |
| Energy | &minus;0.166 |
| Health Care | &minus;0.074 |
| Consumer Discretionary | &minus;0.008 |
| Financials | +0.044 |
| Real Estate | **+0.086** |

Global commodities at one end, domestic UK financials and property at the other.
That is a genuinely FTSE-specific axis: this index staples a set of enormous
global miners and oil majors onto a set of domestic British banks and REITs, and
the second-largest source of common variation is the tension between them.

No one specified that factor. It fell out of the data.

Check the orthogonality while you are here: correlate the PC2 score against the
market. You should get roughly &minus;0.08, i.e. nothing. The components are
uncorrelated by construction, and confirming it is a good test that your
deflation worked.

## Building a risk model from it

Keep the first *k* components and rebuild:

<div class="formula">&Sigma;<sub>k</sub> = V L V&prime; + diag(residual variance)</div>

where **V** holds the *k* eigenvectors, **L** the eigenvalues on its diagonal.
The diagonal top-up is what makes each stock keep its own total variance: without
it, a stock poorly captured by the first five components would appear almost
riskless.

!!! excel "The reconstruction"
    ```
    systematic =MMULT(MMULT(V, L), TRANSPOSE(V))
    residual   =MAX(0, original diagonal - systematic diagonal)
    Sigma_k    =systematic + diagonal of residuals
    ```
    Clamp the residual at zero. Numerically it should never be negative, but
    floating-point arithmetic occasionally disagrees and a negative variance
    propagates into a `#NUM!` the moment you take a square root.

## How many components?

Here is the awkward number: on this data it takes **30 components** to reach 80%
of total variance.

So 81 stocks do not live on a five-dimensional manifold. PC1 gets you a third,
the next four add about 16 points between them, and then there is a long, flat
tail of components each explaining 1&ndash;2% &mdash; which is another way of
saying most of what a FTSE 100 stock does is specific to that company.

The usual selection methods and what they suggest:

- **Scree plot.** Chart the eigenvalues and look for the elbow. Here it is sharp
  and obvious: after PC1, everything is small. That argues for very few factors.
- **Variance target.** Retain enough for 80% or 90%. That argues for 30 or more.
- **Marchenko&ndash;Pastur / random matrix theory.** Components whose eigenvalues
  fall inside the range you would expect from pure noise given your ratio of
  stocks to observations are *indistinguishable from noise*, and should be
  dropped. This is the principled answer and it usually keeps single figures.

Reasonable people land in different places. Five is a defensible working choice
and it is what the self-check uses.

## The catch, which is a real one

Principal components are **statistical**, not economic. Three consequences you
should be able to articulate:

1. **They have no names.** PC1 is the market and PC2 is arguably
   commodities-versus-domestic, but PC4 is whatever it is. You cannot walk into a
   meeting and attribute a portfolio's risk to PC4.
2. **They rotate.** Re-estimate on a different window and the components move,
   sometimes swapping order when two eigenvalues are close. A fundamental factor
   called "Financials" means the same thing every month; PC3 does not.
3. **The sign is arbitrary.** An eigenvector multiplied by &minus;1 is still an
   eigenvector. Any convention will do &mdash; we force the largest loading
   positive &mdash; but do not read meaning into it.

What they are superb at is capturing correlation structure **nobody thought to
specify**. When correlations behave strangely, a statistical model picks it up
because it is not committed to a story about why.

Which is exactly why most risk teams run a fundamental model *and* a statistical
one, and treat a disagreement between them as information rather than as an error
to be reconciled. That is Module 10.
