---
number: 9
slug: pca
title: The statistical risk model
summary: Extract factors directly from the covariance matrix using principal components. The first one turns out to be the market.
time: 2-3 hours
---

!!! tip "Do you have to choose?"
    Maybe you do not have to make a choice between time-series and
    cross-sectional models at all. Module 7 took returns and calculated the
    loadings. Module 8 took the loadings and calculated factor returns. Instead,
    you could just not assume either the loadings or what your factors are, and
    see what comes out of the analysis of the returns themselves.

    That is the idea behind a statistical risk model. Do certain groups of stocks
    move in particular ways together? Can we create stock factors just from
    looking at returns, without knowing anything about the underlying companies?

In Modules 7 and 8 the factors were chosen in advance: the market in Module 7,
and size, momentum, volatility and industry in Module 8. The table near the start
of Module 8 compares all three approaches by what each one assumes.

## What principal components are

Principal components analysis finds the directions of greatest variance in your
covariance matrix.

- **PC1** is the portfolio of your 81 stocks with the highest variance.
- **PC2** is the highest-variance portfolio *uncorrelated with PC1*.
- And so on, each orthogonal to all the ones before it.

Formally these are the eigenvectors of &Sigma;, ordered by eigenvalue. The
eigenvalue *is* the variance of that portfolio, so the share of variance explained
is simple to calculate:

<div class="formula">share of variance explained by PC<sub>k</sub> = &lambda;<sub>k</sub> / trace(&Sigma;)</div>

The trace (the sum of the diagonal) is the total variance across all your stocks,
because eigenvalues sum to the trace. So you can compute the share explained
without finding all 81 components.

## Doing eigenvectors in Excel

Excel has no `EIGEN()` function. You do not need one: **power iteration** is a few cells and a drag. Multiply any starting vector by &Sigma;, normalise it, and repeat. It
converges to the dominant eigenvector, because each multiplication stretches the
vector further along the direction of greatest variance:

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
    The numbers stop changing after about fifteen iterations on this data.

    The eigenvalue, once converged:
    ```
    =MMULT(TRANSPOSE(v), MMULT(Cov!$B$2:$CC$82, v))
    ```

    If the sheet is slow, compute `MMULT(Cov, v)` once into a helper column and
    normalise from that, rather than calling it twice in one formula.

!!! tip "Accuracy"
    We checked the power-iteration result against a standard numerical
    eigendecomposition (LAPACK, via numpy) on this dataset. The first five
    eigenvalues agree to **eleven decimal places**, so the Excel method gives the
    same result as a standard library.

For the next component, **deflate**, by subtracting the one you just found:

<div class="formula">&Sigma;&prime; = &Sigma; &minus; &lambda;<sub>1</sub> v<sub>1</sub> v<sub>1</sub>&prime;</div>

Then run the same routine on &Sigma;&prime;. Because PC1's contribution has been
removed, power iteration now converges to PC2. Repeat for as many as you want.

!!! excel "Deflation in one formula"
    ```
    =Cov!B2:CC82 - lambda1 * MMULT(v1, TRANSPOSE(v1))
    ```
    `MMULT(v1, TRANSPOSE(v1))` is the outer product: an 81&times;81 matrix from an
    81&times;1 vector. Note the argument order; the other way round gives a
    1&times;1 scalar, which is not what you want here.

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

Look at the PC1 loadings. **All 81 have the same sign**, so PC1 is a long-only
portfolio of the whole index.

Now score it: for each week, compute the loadings dotted with that week's
returns, giving a time series. Correlate that against the simple equal-weighted
average of all 81 stocks.

You should get about **0.991**.

The algorithm was given only the covariance matrix, with no index or benchmark,
and it still produced something very close to the market. The market is the
largest single source of common variation in the data, so methods like this one
find it.

<figure class="figure">
  <img src="/static/img/pca-machine.png" width="1400" height="788" loading="lazy"
       alt="A cartoon of a home-made machine full of gears. A stick figure on a stepladder tips a grid labelled covariance matrix into the funnel on top. A long pink banner reading PC1 = THE MARKET unrolls from a chute on the side, held by a second stick figure who says Nobody told it that.">
  <figcaption>The algorithm sees only the covariance matrix, with no index and no
  company names. Its first component still correlates about 0.99 with the market.</figcaption>
</figure>

Look at the size of the loadings, too:

- **Largest:** Barclays, NatWest, Barratt, Lloyds &mdash; banks and a housebuilder.
- **Smallest:** Reckitt, Unilever, National Grid, Severn Trent, United Utilities.

This ordering is close to a ranking by beta.

### PC2: commodities versus domestic UK

PC2 has loadings of both signs. Average the PC2 loading within each ICB industry:

| Industry | Mean PC2 loading |
|---|---|
| Basic Materials | **&minus;0.204** |
| Energy | &minus;0.166 |
| Health Care | &minus;0.074 |
| Consumer Discretionary | &minus;0.008 |
| Financials | +0.044 |
| Real Estate | **+0.086** |

Global commodities are at one end, and domestic UK financials and property at the
other. This reflects the make-up of the FTSE 100, which staples a set of enormous global miners and oil majors onto a set of domestic British banks and REITs. The
difference between those groups is the second-largest source of common variation. Nobody specified that factor; it fell out of the data.

Check the orthogonality while you are here: correlate the PC2 score against the
market. You should get roughly &minus;0.08, which is close to zero. The
components are uncorrelated by construction, so this is a good test that your
deflation worked.

## Building a risk model from it

Keep the first *k* components and rebuild:

<div class="formula">&Sigma;<sub>k</sub> = V L V&prime; + diag(residual variance)</div>

where **V** holds the *k* eigenvectors and **L** the eigenvalues on its diagonal.
The diagonal term keeps each stock's total variance. Without it, a stock that is
poorly captured by the first five components would appear almost riskless.

!!! excel "The reconstruction"
    ```
    systematic =MMULT(MMULT(V, L), TRANSPOSE(V))
    residual   =MAX(0, original diagonal - systematic diagonal)
    Sigma_k    =systematic + diagonal of residuals
    ```
    Clamp the residual at zero. It should not be negative, but floating-point
    arithmetic occasionally produces a tiny negative value, which turns into a
    `#NUM!` when you take a square root.

## How many components?

On this data it takes **30 components** to reach 80% of total variance.

PC1 accounts for about a third, the next four add about 16 points between them,
and then there is a long, flat tail of components each explaining 1&ndash;2%.
That reflects how much of each FTSE 100 stock's movement is specific to that
company.

The usual selection methods and what they suggest:

- **Scree plot.** Chart the eigenvalues and look for the elbow. Here it is clear:
  after PC1, everything is small. That argues for very few factors.
- **Variance target.** Retain enough for 80% or 90%. That argues for 30 or more.
- **Marchenko&ndash;Pastur / random matrix theory.** Components whose eigenvalues
  fall inside the range you would expect from pure noise, given your ratio of
  stocks to observations, are *indistinguishable from noise* and can be dropped.
  This has a stronger theoretical basis and usually keeps fewer than ten
  components.

People reasonably choose different numbers. Five is a defensible working choice,
and it is what the self-check uses.

## The catch

Principal components are statistical constructs without a direct economic
meaning. This has three consequences:

1. **They have no names.** PC1 is the market and PC2 is arguably
   commodities-versus-domestic, but PC4 is whatever it is, and you cannot walk into a meeting and attribute a portfolio's risk to PC4.
2. **They change.** Re-estimate on a different window and the components move,
   sometimes swapping order when two eigenvalues are close. A fundamental factor
   called "Financials" means the same thing every month; PC3 does not.
3. **The sign is arbitrary.** An eigenvector multiplied by &minus;1 is still an
   eigenvector. Any convention will do (we force the largest loading to be
   positive), but the sign itself has no meaning.

Their strength is capturing correlation structure that nobody specified in
advance, including unusual changes in correlation.

For this reason many risk teams run both a fundamental and a statistical model,
and investigate cases where the two disagree. Module 10 compares the models.
