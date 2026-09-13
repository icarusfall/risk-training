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

One quick adjustment to the covariance calculation swaps the answer for a
relative number: just use the relative weights in the calculation, and leave the
covariance matrix alone.

<div class="formula">TE = &radic;(w<sub>a</sub>&prime; &Sigma; w<sub>a</sub>) &times; &radic;52</div>

This will give the right total tracking error. But often the most interesting
question is not what the total number is, but which holdings &mdash; or, later
on, which factors &mdash; are driving it: what is the tracking error
**breakdown**? Interestingly, just swapping in relative weights causes problems
for the breakdown of risk. More on that at the end of the module.

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
driving this?* The naive answer &mdash; "the biggest weight" &mdash; is often
wrong, because a large position in a placid utility can matter less than a small
one in a miner. Though in practice, as you are about to see, the boring answer
holds up more often than people expect.

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

!!! tip "A simple way to think about it"
    A simple way to think about this is that we are adding up the rows and
    columns of a matrix that has been scaled by the weights.

    Take the covariance matrix and multiply every cell by the weight of its row
    **and** the weight of its column, so cell (i, j) becomes
    w<sub>i</sub> w<sub>j</sub> &Sigma;<sub>ij</sub>. Add up every cell in that
    grid and you get the portfolio variance &mdash; exactly the
    w&prime;&Sigma;w from Module 3, just done by hand.

    Now, at the last step, add up the grid one column at a time instead of all at
    once. You are left with a single row of numbers, one per holding, that add up
    to the total. That row is the amount each holding &mdash; or, later on, each
    factor &mdash; contributes to it.

    The one wrinkle: that row adds up to the total **variance**. Divide each
    number by the portfolio volatility and the row adds up to the **volatility**
    instead. Those are your CTRs, and it is the same number as the formula above.
    ```
    grid cell      =B$1 * $A2 * Cov!B2        ' weight across row 1, weight down column A
    column total   =SUM(B2:B13)               ' one per holding
    CTR            =B15 / SQRT(SUM(B15:M15))  ' divide by portfolio vol
    ```

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

Sort your holdings by weight, then by contribution to risk, and compare.

Honestly, the two lists will usually look quite similar. We built 300 random
portfolios the same way yours was built and checked:

| | |
|---|---|
| Biggest weight is also the biggest contributor | 37% of the time |
| Biggest contributor is one of the three biggest weights | 77% of the time |
| Rank correlation between weight and contribution | median 0.80 |

So for total risk, the boring answer is usually close, and the covariance matrix
mostly confirms what the weights already told you. Anyone who tells you
otherwise has probably only ever looked at the interesting cases.

Where the covariance matrix earns its keep is the exceptions &mdash; the roughly
one portfolio in four where the biggest risk is not even a top-three weight.
When the orders do diverge, it is typically a mid-sized bank or miner
contributing more than its weight suggests, or a large consumer staples position
contributing less. Two reasons compound:

1. **Its own volatility** is higher.
2. **Its correlation with everything else you own** is higher &mdash; and this is
   the part people miss. A stock that is volatile but uncorrelated adds less risk
   than a stock that is moderately volatile and moves with the rest of the book.

That second point is why contributions are worth computing even when they mostly
agree with the weights: the exceptions are precisely the positions that surprise
people. And the picture shifts a good deal more once you move from total risk to
active risk, which is where this module ends up.

!!! warning "Contributions can be negative"
    If a holding is negatively correlated with the rest of the portfolio, its CTR
    is negative &mdash; it genuinely *reduces* total risk. The contributions still
    sum to &sigma;<sub>p</sub>. This surprises people, so be ready for it.

## Now the important bit: decomposing active risk

Everything above *appears* to work identically with active weights. Substitute
w<sub>a</sub> for **w** and you get contributions to tracking error. That is the
report a portfolio manager actually wants &mdash; which of my active bets is
using up my risk budget?

**The total will be right. The attribution will be wrong.**

This is worth labouring, because it is a genuine defect rather than an
approximation, and expensive third-party risk systems fall for it.

### The 5% cash example

Suppose you hold 95% of the FTSE 100, matched weight for weight, and 5% cash.

Think about what you have actually decided. Every stock is held at its index
weight, scaled down. The *only* active decision in the entire portfolio is the
cash.

Your active weights are:

- each stock: 0.95 w<sub>b,i</sub> &minus; w<sub>b,i</sub> = **&minus;0.05 w<sub>b,i</sub>**
- cash: **+0.05**

Tracking error comes out at exactly 5% of the benchmark volatility &mdash; on our
data, 5% &times; 17.09% = **0.854%**. That is correct, and comfortingly obvious:
you are 5% out of the market.

Now decompose it. Cash has zero variance and zero covariance with everything, so
its **entire row of &Sigma; is zeros**. Therefore:

<div class="formula">
CTR<sub>cash</sub> = w<sub>a,cash</sub> &times; (&Sigma;w<sub>a</sub>)<sub>cash</sub> / &sigma;<sub>a</sub> = 0.05 &times; 0 / &sigma;<sub>a</sub> = 0
</div>

Your risk report now says that **100% of your tracking error comes from your
stock holdings, and none of it from the cash.**

That is nonsense. The stocks are the index, held at index weight. They are not a
bet on anything. The cash is the only thing you did.

| Decomposition | Cash | Stocks | Total |
|---|---|---|---|
| Naive &mdash; w<sub>a</sub> against &Sigma; | **0.0000%** | 0.8543% | 0.854% |
| Rotated &mdash; see below | **0.8543%** | 0.0000% | 0.854% |

### Why it happens

Because **in active space, cash is not riskless.**

Holding cash instead of the index is a *short position in the index*. Its
benchmark-relative return is r<sub>cash</sub> &minus; r<sub>b</sub> =
&minus;r<sub>b</sub>, which is exactly as volatile as the index itself. There is
nothing safe about it.

The plain covariance matrix cannot see this, because it describes **absolute**
returns, and in absolute terms cash genuinely is riskless. A zero row in &Sigma;
forces a zero contribution no matter how large the active weight sitting against
it. And the Euler identity still holds &mdash; the contributions still sum to the
tracking error &mdash; so nothing looks broken. The report is simply pointing at
the wrong positions.

### The fix: rotate the matrix into active space

Replace every covariance with the covariance of **benchmark-relative** returns:

<div class="formula">
&Sigma;&#771;<sub>ij</sub> = Cov(r<sub>i</sub> &minus; r<sub>b</sub>, r<sub>j</sub> &minus; r<sub>b</sub>) = &Sigma;<sub>ij</sub> &minus; Cov(r<sub>i</sub>, r<sub>b</sub>) &minus; Cov(r<sub>j</sub>, r<sub>b</sub>) + Var(r<sub>b</sub>)
</div>

You already have every piece of that:

- **Cov(r<sub>i</sub>, r<sub>b</sub>)** is the *i*-th element of
  &Sigma;w<sub>b</sub> &mdash; one `MMULT`.
- **Var(r<sub>b</sub>)** is w<sub>b</sub>&prime;&Sigma;w<sub>b</sub>, a single
  number.

Then decompose using your **portfolio** weights, not your active weights. The
rotation has already taken the benchmark out:

<div class="formula">
&sigma;<sub>a</sub><sup>2</sup> = w<sub>p</sub>&prime; &Sigma;&#771; w<sub>p</sub> &nbsp;&nbsp;&nbsp;&nbsp; CTR<sub>i</sub> = w<sub>p,i</sub> (&Sigma;&#771; w<sub>p</sub>)<sub>i</sub> / &sigma;<sub>a</sub>
</div>

The total is **identical** &mdash; check that first, it is a good test of your
algebra. But the attribution now lands on the positions that caused it. In the
cash example, cash takes 100% and the stocks take 0%.

!!! excel "Doing the rotation"
    Add cash to your universe first: one extra row and column of **zeros** in the
    covariance matrix, a benchmark weight of 0, and a portfolio weight of 5%.
    Cash really does have zero absolute risk &mdash; that is the whole point.

    Then, beside your covariance matrix:
    ```
    covib   =MMULT(Cov, wb)                        ' a column, one row per asset
    varb    =MMULT(TRANSPOSE(wb), MMULT(Cov, wb))  ' one cell
    ```
    Paste `covib` **twice**: once as a column down the side, and once transposed
    as a row across the top. Each cell of the rotated matrix is then
    ```
    =Cov!B2 - $M2 - N$1 + $O$1
    ```
    where `$M2` is that row's Cov(r<sub>i</sub>,r<sub>b</sub>), `N$1` is that
    column's, and `$O$1` is Var(r<sub>b</sub>). Drag across and down.

    On a 365 build, if `covib` is a spilled column you can do the whole thing in
    one formula:
    ```
    =Cov - covib - TRANSPOSE(covib) + varb
    ```

    Two sanity checks before going further. The rotated matrix must still be
    **symmetric**, and `w_p' Sigma~ w_p` must equal the tracking error you
    already computed the ordinary way. If it does not, your row and column
    vectors are the wrong way round.

### It is not only about cash

Cash is the cleanest illustration, but the same defect bites whenever an asset's
**absolute** risk is a poor guide to its **benchmark-relative** risk:

- Any holding that is not in the benchmark at all.
- A portfolio that is not fully invested, or is geared.
- A futures or derivative overlay, where notional and market value diverge.
- Any near-riskless asset: short-dated gilts, money market funds, collateral.

Anywhere &Sigma; has a small row and the active weight against it is not small,
the naive decomposition will quietly under-attribute.

!!! warning "An honest caveat"
    The two decompositions are not simply right and wrong in every case. They
    answer different counterfactuals.

    The naive one asks *"if I scale this active position on its own, what happens
    to tracking error?"* The rotated one asks *"if I scale this holding, funded
    out of the benchmark, what happens?"* The second is what actually happens
    when you trade, which is why it is the better default &mdash; but they do
    genuinely differ.

    You can see the difference without any cash at all. Take a portfolio with two
    stock tilts and everything else at benchmark weight. The naive decomposition
    gives exactly zero to every name held at benchmark weight. The rotated one
    does not, because in its counterfactual those holdings are funded against the
    index too &mdash; on our data they collectively carry about &minus;0.5
    percentage points of the tracking error.

    Know which question you are answering. The failure to avoid is not picking the
    wrong one; it is running the naive decomposition on a portfolio holding cash
    and never noticing that the largest position in the report has vanished.

## Do both, and compare

Build the absolute decomposition and the active one side by side. The two
rankings are often strikingly different, because an overweight in a
low-volatility name can still be a large active bet.

Then add 5% cash to your own portfolio and run it both ways. The totals will
agree; watch where the attribution moves.
