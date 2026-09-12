---
number: 10
slug: bake-off
title: The bake-off
summary: Four models, one portfolio. Which would you have trusted in March 2020?
time: half a day
status: soon
---

!!! warning "Being written"
    The capstone. Everything up to here has been construction; this is judgement.

By now you have four estimates of the same covariance matrix:

1. **Sample** - fits the past exactly, noise included (Module 3)
2. **EWMA** - same, weighted toward recent history (Module 5)
3. **Single-factor** - 163 parameters instead of 3,321 (Module 7)
4. **Statistical / PCA** - factors the data chose for itself (Module 9)

They disagree. The exercise is to work out which disagreements matter.

### Test 1: the bias statistic

For each week, predict volatility using only data available *before* it, then
compare to what actually happened:

<div class="formula">b<sub>t</sub> = r<sub>t</sub> / &sigma;<sub>predicted,t</sub></div>

If the model is calibrated, the standard deviation of **b** across time is 1.
Below 1 and you are overstating risk; above 1 and you are understating it.

This single number is how risk teams actually judge a model, and it is the most
useful thing in this module.

### Test 2: the crises, one at a time

Run all four through September 2008, March 2020 and September 2022. Ask:

- Which reacted fastest?
- Which one was *already* elevated going in?
- Did the factor models hold up better than the sample matrix when correlations
  went to one?

### Test 3: minimum variance

Build the minimum-variance portfolio under each &Sigma;. Then compute what each
one *actually* realised out of sample.

The sample covariance usually produces the most extreme weights and the worst
out-of-sample result. The matrix that fits history best is the worst at
forecasting - estimation error, concentrated into exactly the positions the
optimiser loves most. This result surprises everyone the first time.

### The question to answer

You have to give one number to a portfolio manager on 24 February 2020. Which
model, which window, and what do you say about the uncertainty around it?

There is no answer key for this one. Write half a page and we will discuss it.
