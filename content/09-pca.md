---
number: 9
slug: pca
title: The statistical risk model
summary: Let the data find its own factors. The first one turns out to be the market, and nobody told it to be.
time: 2-3 hours
status: soon
---

!!! warning "Being written"
    The outline is below - and the Excel method genuinely works, so you can try
    it now if you are impatient.

Modules 7 and 8 both told the model what the factors were. This one asks the data.

Principal components analysis finds the directions of greatest variance in the
covariance matrix. The first eigenvector is the portfolio of your universe with
the highest variance; the second is the highest-variance portfolio uncorrelated
with the first, and so on.

### Doing eigenvectors in Excel

Excel has no `EIGEN()`. You do not need one. **Power iteration** is four cells:

1. Start with any vector **v** (a column of 1s works).
2. Compute `=MMULT(Cov, v)`.
3. Divide by its own norm: `=SQRT(SUMSQ(...))`.
4. Feed it back in, and repeat.

Copy that block across twenty columns and watch it converge. The vector stops
moving after about fifteen iterations, and what it converges to is the dominant
eigenvector. The eigenvalue is `=MMULT(TRANSPOSE(v), MMULT(Cov, v))`.

We checked this against a proper numerical eigendecomposition on this dataset:
**the power-iteration answer agrees to eleven decimal places**. The Excel route
is not an approximation.

For the next component, **deflate** - subtract what you just found:

<div class="formula">A&prime; = A &minus; &lambda;<sub>1</sub> v<sub>1</sub> v<sub>1</sub>&prime;</div>

and run the identical routine again.

### What you will find

On this universe, PC1 explains roughly half of all variance, and every loading
has the same sign. Nobody told it about the market - it found it. Correlate the
PC1 score against an equal-weighted index return and see how close it is.

PC2 is more interesting: it typically has miners and banks at one end and staples
and utilities at the other. That is a cyclical-versus-defensive axis, discovered
without anyone defining it.

### The catch

Principal components are **statistical**, not economic. They have no names, they
rotate as you change the window, and PC4 is nearly impossible to explain to a
portfolio manager. Statistical models are excellent at capturing correlation
structure you did not anticipate, and useless at attribution.

That is exactly why most risk teams run a fundamental model *and* a statistical
one, and pay attention when they disagree.
