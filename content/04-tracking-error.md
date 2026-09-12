---
number: 4
slug: tracking-error
title: Tracking error and where the risk comes from
summary: Active weights, and decomposing total risk into per-holding contributions that actually add up.
time: 60 min
---

Total portfolio volatility is rarely what anyone on this desk is asked about.
The question is almost always **relative**: how far can this portfolio drift from
its benchmark?

## Active weights

<div class="formula">w<sub>active</sub> = w<sub>portfolio</sub> &minus; w<sub>benchmark</sub></div>

That is the whole trick. Tracking error is portfolio volatility computed on
active weights instead of absolute ones:

<div class="formula">TE = &radic;(w<sub>a</sub>&prime; &Sigma; w<sub>a</sub>) &times; &radic;52</div>

Same matrix. Same formula. Different vector.

Two properties worth internalising:

- Active weights **sum to zero**. A long-only portfolio has a long/short active
  position, which is why tracking error can be small even when both portfolio and
  benchmark are volatile.
- If you hold the benchmark exactly, w<sub>a</sub> is all zeros and TE is zero.
  Use this as your test. Set your weights equal to the benchmark weights on your
  front tab and confirm you get zero out.

Your benchmark weights are on [the home page](/) &mdash; cap weights across your
own holdings, renormalised to 100%.

!!! tip "What the number means"
    Tracking error is a one-standard-deviation annual figure. A TE of 4% means
    that in roughly two years out of three, your relative return should land
    within &plusmn;4% of the benchmark. It is symmetric: it does not distinguish
    beating the benchmark from missing it. Everyone forgets this and describes
    tracking error as though it were a downside measure.

## Where does the risk come from?

Here is the question you will be asked most often in this job: *which position is
driving this?* The naive answer &mdash; "the biggest weight" &mdash; is usually
wrong, because a large position in a placid utility may matter less than a small
one in a miner.

We want a decomposition that **adds up**: a per-holding number summing exactly to
total portfolio risk. Volatility is not additive, so this is not obvious &mdash;
but it works out beautifully because of one property.

### Marginal contribution to risk

MCTR is the sensitivity of portfolio volatility to a small increase in one weight:

<div class="formula">MCTR<sub>i</sub> = &part;&sigma;<sub>p</sub> / &part;w<sub>i</sub> = (&Sigma;w)<sub>i</sub> / &sigma;<sub>p</sub></div>

The whole vector is one `MMULT` of &Sigma; and **w**, divided by a scalar.

### Contribution to risk

<div class="formula">CTR<sub>i</sub> = w<sub>i</sub> &times; MCTR<sub>i</sub></div>

And now the useful part:

<div class="formula">&Sigma;<sub>i</sub> CTR<sub>i</sub> = &sigma;<sub>p</sub></div>

The contributions sum **exactly** to total volatility. This is Euler's theorem
for homogeneous functions: &sigma;<sub>p</sub>(w) is homogeneous of degree one in
**w**, so the weighted sum of its partial derivatives returns the function itself.

That single property is why the entire risk industry reports risk this way.

!!! excel "Doing it in Excel"
    With weights in `B2:B13` and covariance in `Cov!B2:M13`:

    **Sigma-w** (spills down 12 rows):
    ```
    =MMULT(Cov!B2:M13, B2:B13)
    ```
    **Portfolio variance** (one cell, call it `PVar`):
    ```
    =MMULT(TRANSPOSE(B2:B13), MMULT(Cov!B2:M13, B2:B13))
    ```
    **MCTR** (annualised):
    ```
    =MMULT(Cov!B2:M13, B2:B13) / SQRT(PVar) * SQRT(52)
    ```
    **CTR**:
    ```
    =B2:B13 * D2:D13
    ```
    **Percent of risk**:
    ```
    =E2:E13 / SUM(E2:E13)
    ```
    Check that `SUM` of your CTR column equals your annualised portfolio
    volatility. If it does not, something upstream is misaligned.

## The thing to notice

Sort your holdings by weight, then by contribution to risk. The orders will not
match.

You will typically find that a mid-sized holding in a bank or a miner contributes
far more risk than its weight suggests, while a large consumer staples position
contributes less. Two reasons compound:

1. **Its own volatility** is higher.
2. **Its correlation with everything else you own** is higher &mdash; and this is
   the part people miss. A stock that is volatile but uncorrelated adds less risk
   than a stock that is moderately volatile and moves with the rest of the book.

That second point is the entire argument for looking at contributions rather than
weights, and it is worth being able to explain in one sentence at a meeting.

!!! warning "Contributions can be negative"
    If a holding is negatively correlated with the rest of the portfolio, its CTR
    is negative &mdash; it genuinely *reduces* total risk. The contributions still
    sum to &sigma;<sub>p</sub>. This surprises people, so be ready for it.

## Do the same for active risk

Everything above works identically with active weights: substitute
w<sub>a</sub> for **w** and you get contributions to *tracking error*. That is the
report a portfolio manager actually wants &mdash; which of my active bets is using
up my risk budget?

Build both. The two rankings are often strikingly different, because an
overweight in a low-volatility name can still be a large active bet.
