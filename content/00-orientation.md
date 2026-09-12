---
number: 0
slug: orientation
title: What you are about to build
summary: What a risk model is for, why we make you do it in Excel, and how to use this site.
time: 15 min
---

Welcome to the team.

Over the next few days you are going to build a working equity risk model from
nothing more than a column of prices. Not a toy: by the end you will have four
different models of the same portfolio, you will know why they disagree, and you
will have an opinion about which one you would have trusted in March 2020.

## Why Excel, when Python would take ten minutes

Because ten minutes is the problem.

In Python you would type `returns.cov()` and get a matrix. It would be correct.
You would learn nothing, because you would never have to decide what a return
is, what to do about the Tuesday that Barclays did not trade, or whether a name
that listed in 2021 belongs in a covariance matrix estimated since 2005.

In Excel you have to decide all of it, by hand, and you can see every number.
When your tracking error comes out at 0.02% you will go and look, and you will
find that you left a row of zeros at the top of the returns block. That hour is
the point of the exercise.

!!! tip "You will use Python eventually"
    Everyone on this team does. But you will be much better at it having once
    done this the slow way, because you will know what the library is doing and
    when to distrust it.

## What a risk model actually is

Strip away the vendor packaging and an equity risk model is one object:

<div class="formula">a covariance matrix &Sigma;, and a rule for estimating it</div>

Everything else is a consequence. Portfolio volatility is <code>w&prime;&Sigma;w</code>.
Tracking error is the same thing with active weights. Value at Risk is a
quantile off the same distribution. Risk attribution is a derivative of it. Get
&Sigma; right and the rest is arithmetic.

The interesting part is the second half of that sentence &mdash; *and a rule for
estimating it*. You have perhaps 1,100 weekly observations and 81 stocks. A full
covariance matrix has 81 &times; 82 / 2 = **3,321 free parameters**. You are
estimating 3,321 numbers from 1,100 observations. That should worry you, and
Modules 7 to 9 are three different ways of being less worried.

## The ex-ante / ex-post distinction

Get this straight now, because people muddle it constantly and it is the single
most common confusion in risk conversations.

| | What it answers | How you compute it |
|---|---|---|
| **Ex-post** (realised) | What *did* happen? | Standard deviation of the returns your portfolio actually delivered |
| **Ex-ante** (predicted) | What *might* happen? | <code>&radic;(w&prime;&Sigma;w)</code>, using today's weights |

They differ for a reason that matters. Ex-post risk uses the weights you *had*,
which changed every day. Ex-ante uses the weights you have *now*, held still. A
manager who de-risked in February 2020 has a terrible ex-post number for that
year and may have had a perfectly sensible ex-ante one throughout.

Almost everything you build here is **ex-ante**. Module 6 is where the two meet,
when you check whether yesterday's predictions survived contact with reality.

## How this site works

- **The data refreshes itself.** Prices update automatically, so the numbers move
  a little over time. If you come back next week your answers will have shifted
  in the third decimal place. That is realistic and it is deliberate.
- **You get your own portfolio.** Each joiner is assigned a different set of
  holdings and a different single stock, so the self-checks mark *your* working.
  Comparing answers with the other new joiner will not help you.
- **The checks grade the number, not the method.** `MMULT`, `SUMPRODUCT`,
  pairwise `COVARIANCE.S`, forty intermediate tabs held together with hope &mdash;
  all pass identically, to within 2%. We care that you understand the maths.
- **Shortcuts are fine.** Genuinely. Use whatever gets you there. The only thing
  worth protecting is that *you* end up understanding it, because in six months
  someone will ask you why the tracking error moved and there will be no
  spreadsheet to hide behind.

!!! warning "One honest note"
    Usage on this site is logged, and we will notice if the answers arrive faster
    than the arithmetic could. Nobody is in trouble for that &mdash; it just means
    we should have a conversation about how you are getting on.

## What you need

Excel (Microsoft 365 on Windows is what we assume &mdash; the array formulas spill
automatically). An hour or two at a time. A willingness to be wrong for a while.

Start with [the data](/data), then Module 1.
