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
cannot be shared.

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

## Deploying to Railway

1. Point a Railway project at this repo. `railway.json` handles the rest.
2. **Add a volume mounted at `/data`** and set `DATA_DIR=/data`. Without it the
   price cache and the SQLite database are wiped on every redeploy.
3. Set the variables in [`.env.example`](.env.example) — at minimum `SECRET_KEY`,
   `BASE_URL` and `ADMIN_TOKEN`.
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

## Planned

All eleven modules are written. Planned work below.

**Illustrations throughout.** Do loads of pictures, once the copy review is
finished. The Module 6 volatility-versus-VaR cartoon set the style: hand-drawn,
XKCD-like, generated in ChatGPT from a prompt that pins down labels and which
tail is shaded, saved to `app/static/img/`, compressed with octree quantisation
(median-cut destroys the pastel accent colour), and embedded as a captioned
figure. Candidate spots so far:

- Module 1: a price that drops tenfold for one day and bounces straight back.
- Module 4: cash as a short position in the index.
- Module 5: the anniversary cliff, as the Covid crash leaves a 52-week window.
- Module 8: the observed-essence question - is this car maker really a bank?
- Module 9: PC1 turning out to be the market.
- Module 11: fat tails against the normal, drawn as a pair with the VaR image.

**Module 11 — higher moments.** Skew, kurtosis, and a lesson in how badly the
fourth moment behaves. Measured on the `CAPFIXED_TR` benchmark, weekly returns,
2005 onwards — the only thing that changes between rows is which weekday the
week is sampled on:

| Anchor | Skew | Excess kurtosis | Ann. vol |
|---|---|---|---|
| Mon | −0.25 | 5.68 | 17.86% |
| Tue | +0.02 | 7.51 | 16.91% |
| Wed | −0.47 | 5.65 | 17.11% |
| Thu | −0.88 | 9.08 | 17.31% |
| Fri | −0.85 | 10.49 | 17.77% |

Kurtosis nearly doubles and skew changes sign, while volatility moves 5.4%. The
second moment is a stable statistic; the fourth is not.

**The mechanism, which is the actual lesson:** it is whether the bucketing
*captures* an outlier or *smooths over* it. A crash runs across several days. If
the week boundary falls outside it, the whole collapse lands in one bucket and
shows up as a single enormous return. If the boundary falls inside it, the crash
is split across two buckets and averaged away.

October 2008, daily: −7.6%, −0.2%, −5.7%, −1.2%, −9.1%, then a rebound.

| Anchor | Same fortnight, weekly |
|---|---|
| Friday | **−21.8%**, then +2.5% — collapse captured whole |
| Wednesday | −12.4%, then −6.8% — split down the middle |
| Monday | −3.5%, then −9.0% — split, and partly offset by the rebound |

Across the five anchors, the correlation between excess kurtosis and the number
of weeks holding two or more of the twenty worst days is **+0.90**. Fat tails
appear when the sampling grid happens to bundle bad days together.

The corollary: dropping the three most extreme weeks out of 1,115 shrinks the
kurtosis spread from 4.84 to 1.29. Three quarters of the disagreement rests on
three observations, which is what "the fourth moment barely converges" means in
practice.

Note this is a *different* criterion from Module 2. Wednesday sampling is right
for volatility because it avoids stale prints; it is not right for kurtosis for
that reason. There is no monotone relationship between stale weeks and kurtosis
(Monday has the most stale weeks at 106 and near-lowest kurtosis), so do not
claim one.

Then the payoff: **Cornish–Fisher VaR**, which adjusts the normal quantile for
skew and kurtosis:

```
z_cf = z + (z²−1)·S/6 + (z³−3z)·K/24 − (2z³−5z)·S²/36
```

It sits neatly between parametric and historical VaR in Module 6 — and having
just watched kurtosis swing by a factor of two, a joiner is well placed to ask
how much they trust a VaR number that depends on it.

**Module 12 — fat-tailed distributions and Monte Carlo.** Stop patching the
normal and replace it. Three routes, in increasing severity:

| Approach | What it fits | Why bother |
|---|---|---|
| Student-t | a single degrees-of-freedom parameter | fits the *whole* distribution, and ν falls straight out of the kurtosis from Module 11 |
| Power law / Hill estimator | the tail index α | asks only how heavy the tail is, ignoring the bulk |
| Generalised Pareto (EVT) | exceedances over a threshold | the peaks-over-threshold theorem says the tail converges to GPD whatever the parent distribution |

Then Monte Carlo: draw from the fitted distribution rather than evaluating a
quantile formula. That gets you a full loss distribution instead of a single
number, handles a portfolio with options or non-linear payoffs, and makes
expected shortfall fall out for free.

Two things worth making explicit when this gets written. Multivariate is where
it gets hard — a t-copula with correlated marginals is the honest version, and
drawing each stock independently from its own fat-tailed marginal badly
understates joint tail risk, which is precisely the thing that kills you.
And threshold choice in EVT is the whole game: too high and you have five
observations, too low and the asymptotics do not hold. A mean-excess plot is
the standard diagnostic, and reasonable people disagree.

Doing this in Excel is feasible but strained — `T.INV`, `RAND()` and a data
table will get a single-asset Monte Carlo going. This is probably the point where
the exercise earns its move to Python, which is a fine note to end the programme
on.

## Layout

```
app/
  main.py            FastAPI routes
  checks.py          self-check engine, per-joiner portfolios
  canary.py          bait paths and cadence detection
  content.py         markdown lesson loader
  db.py              SQLite: users, attempts, events
  data/
    universe.py      constituents from Wikipedia
    industry.py      40 sectors → 11 ICB industries
    instruments.py   shares outstanding, FX normalisation
    quality.py       bad-print detection and repair
    store.py         price cache, non-blocking refresh
    datasets.py      canonical windows (core / long)
    exports.py       CSVs and the starter workbook
  reference/
    model.py         returns, covariance, portfolio risk
    advanced.py      VaR, factor models, PCA
content/             the lessons
```
