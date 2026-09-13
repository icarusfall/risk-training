---
number: 0
slug: orientation
title: What you are about to build
summary: What a risk model is for, why we use Excel, and how to use this site.
time: 15 min
---

Welcome to the team.

Over the next few days you are going to build a working equity risk model from
nothing more than a column of prices. By the end you will have five different
models of the same portfolio, an understanding of why they disagree, and an
opinion about which one you would have trusted in March 2020.

## Why Excel, when Python would take ten minutes

Because ten minutes is the problem.

In Python you could type `returns.cov()` and have a correct matrix in seconds. You
would also skip every decision that goes into it: what counts as a return, what
to do about the Tuesday that Barclays did not trade, or whether a name that
listed in 2021 belongs in a covariance matrix estimated since 2005.

In Excel you make each of those decisions by hand, and you can see every number.
When your tracking error comes out at 0.02% you will go and look, and you will
find that you left a row of zeros at the top of the returns block. That hour is
a large part of what the exercise is for.

!!! tip "You will use Python eventually"
    Everyone on this team does. You will be better at it for having done this the
    slow way once, because you will know what the library is doing and when to
    distrust it.

## What a risk model is

Strip away the vendor packaging and an equity risk model comes down to one object:

<div class="formula">a covariance matrix &Sigma;, and a rule for estimating it</div>

Most of what a risk system reports follows from it. Portfolio volatility is
<code>w&prime;&Sigma;w</code>. Tracking error is the same calculation with active
weights. Value at Risk is a quantile of the same distribution. Risk attribution
is a derivative of it.

The harder part is the second half: *a rule for estimating it*. You have about
1,100 weekly observations and 81 stocks. A full covariance matrix has
81 &times; 82 / 2 = **3,321 free parameters**, so you are estimating 3,321
numbers from 1,100 observations. That is a problem, and Modules 7 to 9 look at
three different ways of dealing with it.

## Ex-ante and ex-post risk

People mix these up often, so it is worth being clear about them from the start.

| | What it answers | How you compute it |
|---|---|---|
| **Ex-post** (realised) | What *did* happen? | Standard deviation of the returns your portfolio actually delivered |
| **Ex-ante** (predicted) | What *might* happen? | <code>&radic;(w&prime;&Sigma;w)</code>, using today's weights |

They differ because ex-post risk uses the weights you *had*, which changed every
day, while ex-ante risk uses the weights you have *now*, held fixed. A manager who
de-risked in February 2020 has a poor ex-post number for that year and may have
had a perfectly sensible ex-ante number throughout.

Almost everything you build here is **ex-ante**. Module 6 is where the two meet,
when you check whether past predictions held up against what actually happened.

## How this site works

- **The data refreshes itself.** Prices update automatically, so the numbers move
  a little over time. If you come back next week your answers will have shifted
  in the third decimal place. That is deliberate.
- **You get your own portfolio.** Each joiner is assigned a different set of
  holdings and a different single stock, so the self-checks mark *your* working.
  Comparing answers with the other new joiner will not help.
- **The checker just validates that you got the right number.** There are lots of
  different approaches in Excel that will all work fine. Different team members
  already have different preferences on whether they use `MMULT`, `SUMPRODUCT`,
  or just lots of spaghetti tabs building on each other using nothing more than
  `*` and `+`. Answers are marked to within 2%, so a rounding difference will
  never count against you.
- **Ask people.** You are strongly encouraged to ask team colleagues how they
  would calculate things in Excel if it is not clear to you. Different members of
  the team will give you a more or less over-engineered answer, so choose your
  fighter wisely.
- **Shortcuts are fine.** Use whatever gets you there. What matters is that you
  end up understanding the calculation, because in six months someone will ask
  you why the tracking error moved.

!!! warning "Usage is logged"
    Usage on this site is logged, and we will notice if the answers arrive faster
    than the arithmetic could. Nobody is in trouble for that &mdash; it just means
    we should have a conversation about how you are getting on.

## What you need

Excel (we assume Microsoft 365 on Windows, where array formulas spill
automatically), an hour or two at a time, and a willingness to be wrong for a while.

If you are feeling confident, take a look at [the data](/data) first &mdash; but
it is not necessary, as it will be introduced gradually as you work through the
modules.

Start with [Module 1](/module/data).
