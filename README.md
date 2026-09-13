# Risk Model Training

A teaching site for new joiners to the Investment Risk team. It serves fresh
FTSE 100 price history and a set of lessons that walk someone from a column of
prices to a working equity risk model — built by hand, in Excel.

The site holds the data and the instructions. All the actual work happens in the
joiner's spreadsheet.

## What a joiner does

| Module | They build |
|---|---|
| 0 | Orientation: ex-ante vs ex-post, why Excel |
| 1 | Data hygiene: ragged panels, bad prints, survivorship bias |
| 2 | Returns at three frequencies, and the √T rule |
| 3 | The covariance matrix, and portfolio volatility from `w'Σw` |
| 4 | Tracking error, and contribution to risk (MCTR / CTR) |
| 5 | Rolling windows and EWMA |
| 6 | Parametric and historical VaR, plus a Kupiec backtest |
| 7 | Single-factor model: `Σ = ββ'σ²ₘ + D` |
| 8 | Cross-sectional factor model: `Σ = XFX' + Δ` |
| 9 | Statistical / PCA model, eigenvectors by power iteration |
| 10 | Bake-off: five models, one portfolio, bias statistics |
| 11 | Higher moments: skew, kurtosis, Cornish–Fisher VaR |
| 12 | Power-law tails: a log-log line through the worst days, and extrapolation |
| 13 | Student-t, rank correlation, copulas and Monte Carlo |

Lessons live in [`content/`](content/) as markdown — edit them without touching
any Python.

## Design notes

**Data refreshes itself.** Constituents come from Wikipedia, prices from Yahoo.
A full refresh takes about 30 seconds. The site never blocks on it: it serves the
last good snapshot immediately and refreshes in the background when stale, so an
upstream outage degrades to a slightly older "data as of" banner rather than a
broken page.

**The answer key is computed live.** `app/reference/` recomputes every answer from
the same dataset the joiner downloaded, so a data refresh can never leave a stale
key behind. Nothing is hardcoded.

**Checks are method-agnostic.** Answers are graded on the number, within 2%
relative tolerance. `MMULT`, `SUMPRODUCT`, pairwise `COVARIANCE.S` — all pass.

**Each joiner gets their own portfolio**, seeded from their user id, so answers
cannot be shared. There are 32 self-checks across Modules 1 to 13.

**Three datasets.** `raw` is all 100 names exactly as they arrive, ragged and
uncleaned, for Module 1. `core` (2005 onwards, 81 names, cleaned and trimmed to
a rectangle) is the default and what every answer is computed from. `long`
(1995 onwards, 57 names) trades breadth for history.

### Illustrations

Every module has at least one hand-drawn, XKCD-style cartoon, in
`app/static/img/`. To add one:

- Draft a precise prompt. Spell out every label word for word, which side
  anything is shaded, and the single accent colour (site pink `#E9B8BC`), and
  forbid any other text.
- Generate it in ChatGPT and save it to `app/static/img/`.
- Check the labels are spelled right and the picture makes its point. Image
  models get counts and proportions only roughly right; that is accepted as part
  of the hand-drawn look.
- Compress: resize to 1400px wide and quantise with Pillow's `FASTOCTREE` at 128
  colours (35–100KB). Median-cut removes the pastel accent entirely, so count
  accent pixels before and after.
- Embed as a `<figure class="figure">` with full alt text and a caption, and add
  the name to the image list in the smoke test.

### The data is dirty, deliberately and otherwise

Several real problems were found building this, and they are used as teaching
material rather than hidden:

- **Bad prints.** Polar Capital Technology shows `373.50 → 37.35 → 377.30`. Left
  in, it accounted for half of the first principal component.
- **Bank-holiday junk.** Wrong-scale prints on Christmas Day and Good Friday.
  Coverage on those days is 98%, so a sparsity filter does not catch them —
  `quality.py` uses an excursion test instead.
- **Weekly sampling is Wednesday-to-Wednesday.** UK holidays cluster on Mondays
  and Fridays. Measured on this panel: Wednesday anchoring lands on a non-trading
  day 10 times, Friday 32, Monday 106.
- **`ISF.L` is not a total-return series** despite being a FTSE 100 ETF. It
  distributes, and Yahoo's adjusted series does not reinvest. Use `CUKX.L`
  (accumulating), verified at +3.75%/yr over the price index. `ISF.L` is kept in
  the file on purpose as a Module 1 exercise.
- **Market caps are approximate.** We only know today's share count, so
  `cap ≈ shares_today × price_t`. Fine for a z-scored size exposure; catastrophic
  for index weights, where it puts NatWest at 26% of the 2005 index. Composite
  benchmarks therefore use fixed weights, never back-projected caps.
- **Three names are not quoted in sterling** (Compass, IHG in USD; Metlen in EUR)
  and are FX-converted to pence.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

First boot fetches ~30s of data into `data_cache/`. Then create yourself an admin:

```bash
python -c "from app import db; db.init(); u=db.create_user('you@lgim.com','You',is_admin=True); print(f'http://localhost:8000/auth/{db.issue_token(u[\"id\"])}')"
```

Open that link. With no `RESEND_API_KEY` set, magic links are written to the
server log instead of emailed.

**Run `python scripts/smoke_test.py` before every push.** It hits every route
in-process with deprecation warnings escalated to errors, grades every check,
and checks the canary, downloads, images and sign-in flow.

## Deploying to Railway

1. Point a Railway project at this repo. `railway.json` handles the rest.
2. **Add a volume mounted at `/data`** and set `DATA_DIR=/data`. Without it the
   price cache and the SQLite database are wiped on every redeploy.
3. Set the variables in [`.env.example`](.env.example) — at minimum `SECRET_KEY`,
   `BASE_URL`, `ADMIN_TOKEN` and `ADMIN_EMAIL`. While Resend is on its sandbox
   sender, leave `LOGIN_LINK_RECIPIENT` at its default of `admin`, so sign-in
   links are emailed to the admin to forward.
4. Visit `/admin?token=<ADMIN_TOKEN>` to add joiners and email them links.

## The canary

The site flags — softly — when answers look like they came from an AI agent.
Deliberately **not** punitive: the AI route works perfectly and returns genuinely
correct, personalised answers, so the joiner scores full marks and notices
nothing. The only effect is an email to `ADMIN_EMAIL`.

Three independent signals:

- **Bait.** Paths that appear only in `robots.txt`, `llms.txt` and an HTML
  comment, never linked from any page. Fetching one means something read the
  machine-facing surface of the site and acted on it.
- **Shortcut.** `answers.csv` sits in a bare directory index at `/download/` but
  is linked from no page, so the only way to find it is to edit URLs. It holds
  genuinely correct, personalised answers, and its preamble says plainly that
  the download is logged. A hit means somebody went looking, which makes it the
  cleanest of the three signals.
- **Cadence.** A run of first-time-right answers, with no wrong attempts
  anywhere, arriving faster than the arithmetic plausibly goes.

All three are soft signals. Corporate DLP crawlers, link prefetchers and security
scanners do trip the bait, a genuinely well-built spreadsheet can trip the
cadence test, and the shortcut can simply be curiosity. The alert emails say so.
Treat a hit as a reason to ask how someone is getting on, never as proof.

The welcome page states that usage is logged. Worth keeping: it makes the signal
more meaningful, and at a regulated firm employee monitoring deserves the notice.

## To do

The copy review of all eleven modules finished on 13 September 2026, and every
module had its cartoons by the end of the same day. Work through these roughly in
order.

Charlie's view, 13 September 2026: with Module 12 the syllabus is essentially
complete. What follows is optional.

1. **Email joiners directly once a sending domain is verified in Resend.** Set
   `MAIL_FROM` to an address on the domain and `LOGIN_LINK_RECIPIENT=user` in
   Railway. Until then the sign-in form emails links to `ADMIN_EMAIL` to forward.

When writing new lesson copy, follow the house style: plain and warm, jokes and
concrete images welcome, no "it is not X, it is Y" punch finishes, and every
figure computed on the live data before it goes in.

### Parked

- **A Python track.** Excel is deliberate for now. Module 13 (Monte Carlo and
  copulas) is the natural place to point towards Python.
- **Time-series models: ARMA, ARCH, GARCH.** Charlie's ideas for optional further
  modules. GARCH would follow naturally from Module 5's EWMA, which is a GARCH(1,1)
  with no mean reversion.
- **A real value factor**, if a point-in-time fundamentals source becomes
  available. It would plug into `build_exposures` in `app/reference/advanced.py`.
- **Sharing with other teams.** Needs the sending domain above.

### Decided against

- **Per-company industry overrides**, such as moving Unilever and Reckitt to
  Consumer Staples. The mixed-up source labels are left in on purpose as a
  Module 8 teaching point.

## Specs

### Module 11: higher moments

Written as `content/11-higher-moments.md`; this spec is kept as the record of
what was verified. Skew, kurtosis, and how badly the fourth moment behaves.
Measured on the `CAPFIXED_TR` benchmark, weekly returns on complete weeks from
2005 onwards, changing only which weekday each week is sampled on (verified on
the live data 13 September 2026):

| Anchor | Skew | Excess kurtosis | Ann. vol |
|---|---|---|---|
| Mon | −0.25 | 5.68 | 17.86% |
| Tue | +0.02 | 7.51 | 16.91% |
| Wed | −0.47 | 5.64 | 17.11% |
| Thu | −0.88 | 9.06 | 17.32% |
| Fri | −0.85 | 10.49 | 17.77% |

Kurtosis nearly doubles from one anchor to another (a spread of 4.85, about 63%
of its mean) and skew changes sign, while volatility moves by about 5%.

**The mechanism** is Charlie's: whether the weekly bucketing captures an outlier
or smooths over it. A crash runs across several days. If the week boundary falls
outside it, the whole collapse lands in one bucket as a single large return. If
the boundary falls inside it, the crash is split across two buckets.

October 2008, daily: −7.6%, −0.2%, −5.7%, −1.2%, −9.1%, then a rebound.

| Anchor | Same fortnight, weekly |
|---|---|
| Friday | **−21.8%**, then +2.5%: the collapse captured in one week |
| Wednesday | −12.4%, then −6.8%: split down the middle |
| Monday | −3.5%, then −9.0%: split, and partly offset by the rebound |

Dropping the three most extreme weeks out of about 1,114 shrinks the kurtosis
spread from 4.85 to 1.29, so most of the disagreement rests on three
observations. The top three weeks supply 32% of the sum of fourth powers on
Wednesdays and 60% on Fridays.

An earlier draft quoted a +0.90 correlation between kurtosis and the number of
weeks holding two or more of the twenty worst days. With the twenty worst days
by signed return it is +0.70; +0.90 only appears for the twenty largest
absolute moves, and those counts are 2, 2, 2, 3 and 3 across the five anchors,
too thin to quote. The lesson leaves it out.

Wednesday sampling is right for volatility because it avoids stale prints. That
is a different criterion, and there is no monotone relationship between stale
weeks and kurtosis (Monday has the most stale weeks at 106 and near-lowest
kurtosis), so do not claim one.

Then **Cornish–Fisher VaR**, which adjusts the normal quantile for skew and
kurtosis:

```
z_cf = z + (z²−1)·S/6 + (z³−3z)·K/24 − (2z³−5z)·S²/36
```

An earlier draft assumed it would sit between parametric and historical VaR. It
does not. On the benchmark at 99% one week (Wednesday): parametric 5.52%,
historical 6.82%, Cornish–Fisher 9.28%, historical expected shortfall 9.53%.
Across 300 joiner portfolios Cornish–Fisher is above historical VaR every time
(median 1.37×, minimum 1.05×) and close to expected shortfall (median 0.99×,
middle half 0.93–1.06×). The kurtosis term does most of the work: −0.234 sd per
point of excess kurtosis at 99%, so −1.32 of the −3.91 quantile on Wednesdays.

It also inherits kurtosis's instability. Wednesday to Friday sampling moves
Cornish–Fisher VaR from 9.28% to 12.64% (+36%), against −4% for historical and
+4% for parametric; across the 300 portfolios the median move is +16% against
+3% for historical. At Friday's excess kurtosis of 10.5 the expansion is not
even monotone, running backwards for z between −0.31 and +0.55.

**The 95% gotcha** (Charlie's): at 95% a fat-tailed distribution has a *smaller*
VaR than the normal with the same volatility. The Cornish–Fisher kurtosis
coefficient (z³−3z)/24 changes sign at z = −√3, 95.84% confidence: +0.020 per
point at 95%, −0.234 at 99%. On the Wednesday benchmark, parametric against
historical VaR: 90% 3.04 vs 2.37, 95% 3.90 vs 3.44, 97.5% 4.65 vs 4.98, 99% 5.52
vs 6.82. Parametric 95% is breached 45 times against 56 expected. Part of the
95% gap is the +0.19% weekly mean (historical on demeaned returns is 3.63%,
still below), and on demeaned returns the crossover is 96.4% (Tuesday 94.5% to
Friday 97.4%). Across 300 portfolios at 95%, historical is below parametric in
100% (94% demeaned), median ratio 0.89 (0.94 demeaned); at 99% above in 100%;
crossover median 96.4%, 10th–90th percentile 95.4–97.3%.

Self-checks, on the joiner's own Wednesday weekly portfolio returns: `SKEW`,
`KURT` (excess), 95% historical VaR and 99% Cornish–Fisher VaR.

### Module 12: power-law tails

Written as `content/12-power-law.md`. Charlie's design: take the extreme losses,
plot them on a log-log chart, fit a straight line, extrapolate. Daily returns,
because 50 of 5,405 days is the worst 1% (50 of 1,114 weeks would be 4.5%).
Losses ranked largest first get probability i/n with n = all days; regress
ln(i/n) on ln(loss), slope = −α. This is exactly Excel's Power trendline on a
log-log scatter. The slope is independent of n and of decimal-vs-percent units.

Verified on the live data, 13 September 2026, `CAPFIXED_TR` daily:

- k = 50: α = 3.31, R² = 0.985, Hill 3.01 (SE ≈ α/√k ≈ 0.43). Losses 3.29% to
  11.08% (12 March 2020). 23 of the 50 are in 2008–09, 12 in 2020.
- α by k: 20 → 3.56, 50 → 3.31, 100 → 3.14, 200 → 3.02, 500 → 2.35, 1,000 → 1.92.
- Simulated normal returns with the same vol, same recipe: α ≈ 8.2, R² still ≈
  0.97. R² is not evidence of a power law; α is.
- Extrapolation (k = 50), actual days / power law / once every: 5% 17 / 14.6 /
  1.5 yrs (normal: 616 yrs); 7% 4 / 4.8 / 4.5 yrs (normal: 7.8m yrs); 10% 1 /
  1.5 / 15 yrs; 15% 0 / 0.4 / 56 yrs; 20% 0 / 0.1 / 145 yrs.
- α ± one SE with the line pinned at the 50th loss: a 20% day once every 78 to
  368 years.
- Out of sample, fit 2005–2019 → 2020 on: ≥3% 26 actual vs 20.7; ≥5% 4 vs 4.3;
  ≥7% 2 vs 1.5; ≥10% 1 vs 0.5.
- Fit 2005–2007 only (681 days, k = 25): α 2.98, but ≥5% predicted 6.1 against
  17 actual, because vol went from 13.5% to 18.8%. Slope stable; position moves
  with volatility.
- 300 joiner portfolios: α 3.2–3.9 (10th–90th percentile), 95% below 4, none
  below 2.9 or above 4.6; Hill vs regression median gap 0.17; worst day 9.3% to
  12.0%, never above 14.2%; years between 20% days median 180 (92–393).

**The fit is a judgement, and the lesson says so** (Charlie's steer): the chart
wiggles, and the answer depends critically on the cut-off.

- Local α on ten-point stretches of the benchmark, ranks 1–10 to 51–60: 3.17,
  5.91, 3.29, 2.16, 2.10, 2.37, 5.53. The line and the data disagree by up to a
  factor of 1.28 in probability.
- α by cut-off, with the 20% return period: 10 → 3.17 / 139 yrs, 20 → 3.56 / 198,
  25 → 3.63 / 211, 50 → 3.31 / 145, 100 → 3.14 / 115, 200 → 3.02 / 95, 300 →
  2.71 / 55. Not monotone: it peaks at k = 24. Over k = 10–200, α runs 3.02–3.63
  and the 20% day 95–213 years.
- 300 portfolios: |α(20) − α(200)| > 0.5 in 56%; max/min of the 20%-day answer
  across k = 20, 50, 100, 200 has median 2.3× and 90th percentile 5.0×; the
  α range over k = 20–200 has median 0.62.

The lesson has joiners draw a stability plot (α against k, from 10 to 200) and
report a range. It says plainly that the check's 50 points is a marking
convention.

Self-checks, on the joiner's own daily portfolio returns: α from the 50 largest
losses, and years between 20% daily losses read off the fitted line.

### Module 8 addition: what "stock-specific" really means

Charlie's steer: a report saying a manager takes mostly specific risk may just
mean the model is mis-specified for the universe (for example a UK manager with a
style bias on a global model). Verified 13 September 2026 over the Module 8 window
(154 weeks after 27 September 2023), active risk against the 81-name cap-weighted
benchmark:

- **300 joiner portfolios**, specific share of active variance, median (10th–90th
  percentile): single-factor 98.7% (92.6–100); CS 11 industries 42.2% (35.4–49.9);
  banks split 41.1%; no size 51.9% (43.1–62.6); no styles 58.8% (48.0–68.6); PCA-5
  65.4% (51.6–78.8). Median spread across models 56.6 points.
- **Five banks**: CS 11 industries specific 28.5%, model TE 13.66%; banks split
  12.2%, TE 19.31%; realised TE 18.02% (in-sample).
- **Residual correlation**: five banks +0.104 under 11 industries (random
  5-name baskets: mean −0.007, 95th percentile 0.066, 99th 0.103); −0.174 with
  banks split.
- **12 smallest names**: specific share 30.7% with size, 45.8% without; residual
  correlation +0.040 vs +0.027, so the correlation diagnostic misses this one.

### Module 6 addition: options and full revaluation

Charlie's steer: non-linear payoffs are a simple reason to prefer historical or
Monte Carlo VaR. Benchmark at 100, 1-month options at the benchmark's 17.11%
volatility, zero rates, 1-week horizon, implied vol held fixed. 99% VaR in
points, delta-normal / delta-gamma normal / full-reval normal MC / full-reval
historical:

- Index 5.52 / 5.52 / 5.52 / 6.82.
- Short ATM put 2.71 / 3.99 / 3.78 / 5.00 (premium 1.893, worst week −12.00).
- Short 5% OTM put 0.74 / 1.44 / 1.50 / 2.29 (premium 0.330, worst −8.57).
- Index + long ATM put 2.81 / 1.52 / 1.74 / 1.82 (worst −1.89).

### Module 13: Student-t, copulas and Monte Carlo

Written as `content/13-monte-carlo.md`, at Charlie's request: Monte Carlo, other
fat-tailed distributions, and copulas with rank correlation. Verified on the live
data, 13 September 2026, weekly returns:

- **ν.** From weekly portfolio kurtosis, ν = 4 + 6/K: median 5.14 (4.73–5.72).
  From Module 12's daily tail exponent: about 3.5. The lesson uses ν = 4, where
  the t4 quantile has a closed form (`student_t4_ppf`, no scipy).
- **t4 VaR** multiplier 2.649 (normal 2.326); at 95%, 1.507 (normal 1.645).
  Across 300 portfolios, relative to historical: 99% t4 0.973× (normal 0.854×),
  95% t4 1.032× (normal 1.126×). ES99 multiplier 3.70 (normal 2.67); t4 ES is
  0.977× historical ES.
- **Rank correlation**, with the 3 weeks of largest |x|+|y| dropped:
  Barclays/Lloyds Pearson 0.753 → 0.711, rank 0.689 → 0.686; Rio/Anglo 0.717 →
  0.774, rank 0.798 → 0.802; BP/Shell 0.843 → 0.804, rank 0.789 → 0.787. All
  3,240 pairs: median Pearson 0.288, rank 0.287; Pearson minus rank, 10th–90th
  percentile −0.049 to +0.058.
- **Weeks both in worst 5%** (independence 2.8), actual / Gaussian / t4 copula,
  calibrated via Kendall's τ, ρ = sin(πτ/2): Barclays/Lloyds 32 / 23.3 / 27.7;
  Rio/Anglo 30 / 29.0 / 32.8; BP/Shell 30 / 28.5 / 32.5; Barclays/National Grid
  10 / 4.3 / 9.1; HSBC/Tesco 10 / 8.2 / 13.3; Rio/Unilever 5 / 5.3 / 10.4. All
  pairs summed (Gaussian calibrated from Spearman, ρ = 2 sin(πρ_s/6)): actual
  44,864, Gaussian 27,446 (actual 1.63×), t4 44,396, independence 9,023; actual
  above Gaussian in 95% of pairs. Both in best 5%: 34,569 (asymmetric).
- **Monte Carlo** with one-factor correlations against `CAPFIXED_TR` (`CUKX.L`
  starts in 2010). The one-factor vol is 0.956× the full-covariance vol (0.934–0.988).
  60 portfolios at 200k draws, relative to historical 99% VaR / ES: A normal 0.83 /
  0.68; B t4 marginals + Gaussian copula 0.88 / 0.78; C t4 copula 0.94 / 0.94.
  B/A ES +16%, C/B ES +20% (VaR +6%, +8%).
- **Noise at 10k draws** (portfolio seed 0, 300 replications), relative error
  median / 95th / 99th: C VaR 2.2% / 5.9% / 7.2%; C ES 3.3% / 9.6% / 11.9%. Hence
  a 12% tolerance on the Monte Carlo ES check; B's ES is typically 16% below C's,
  so it usually fails.

Self-checks: rank correlation of the assigned stock with `CAPFIXED_TR`; t4 99%
VaR of the portfolio; version C 99% ES (rtol 12%, reference 400k draws, fixed
seed).

### Original Module 12 plan

Parked when Module 12 became the power-law exercise; Module 13 now covers the
Student-t, copulas and Monte Carlo, but not the GPD. Replace the normal
distribution rather than adjusting it. Three routes:

| Approach | What it fits | Why |
|---|---|---|
| Student-t | a single degrees-of-freedom parameter | fits the whole distribution, and ν can be backed out of the Module 11 kurtosis |
| Power law / Hill estimator | the tail index α | looks only at how heavy the tail is |
| Generalised Pareto (EVT) | exceedances over a threshold | the peaks-over-threshold theorem says the tail converges to GPD whatever the parent distribution |

Then Monte Carlo: draw from the fitted distribution to get a full loss
distribution rather than a single quantile. It handles non-linear payoffs, and
expected shortfall comes out of it directly.

Two things to cover properly when this is written:
- **Multivariate draws.** A t-copula with correlated marginals is the honest
  version. Drawing each stock independently from its own fat-tailed marginal
  badly understates joint tail risk, which is the case that matters most.
- **EVT threshold choice.** Too high and there are only a handful of
  observations; too low and the asymptotics do not hold. A mean-excess plot is
  the standard diagnostic, and people reasonably disagree.

Excel can manage a single-asset Monte Carlo with `T.INV`, `RAND()` and a data
table, but a copula across 81 names is where the exercise is better done in
Python, which makes this a sensible place to end the programme.

## Layout

```
app/
  main.py            FastAPI routes: pages, checks, downloads, sign-in, admin
  config.py          all settings, overridable by environment variable
  checks.py          self-check engine (32 checks), per-joiner portfolios
  canary.py          bait paths, the answers.csv shortcut, cadence detection
  content.py         markdown lesson loader
  db.py              SQLite: users, login tokens, attempts, events
  mail.py            Resend email: login links, access requests, alerts
  data/
    universe.py      constituents from Wikipedia
    industry.py      40 sectors -> 11 ICB industries
    instruments.py   shares outstanding, FX normalisation
    descriptions.py  plain-English company descriptions for the front page
    quality.py       bad-print detection and repair
    store.py         price cache, non-blocking refresh
    datasets.py      raw / core / long datasets
    exports.py       CSVs and the starter workbook
  reference/
    model.py         returns, covariance, portfolio and active-space risk
    advanced.py      VaR, factor models, PCA, bias statistics
  static/            style.css, img/ for lesson illustrations
  templates/         page templates
content/             the lessons, as markdown
scripts/
  smoke_test.py      run before every push
```
