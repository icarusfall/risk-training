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
| 8 | Cross-sectional factor model *(outline)* |
| 9 | Statistical / PCA model *(outline)* |
| 10 | Bake-off: four models, one portfolio *(outline)* |

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

Two independent signals:

- **Bait.** Paths that appear only in `robots.txt`, `llms.txt` and an HTML
  comment, never linked from any page. Fetching one means something read the
  machine-facing surface of the site and acted on it.
- **Cadence.** A run of first-time-right answers, with no wrong attempts
  anywhere, arriving faster than the arithmetic plausibly goes.

Both are soft signals. Corporate DLP crawlers, link prefetchers and security
scanners do trip the bait, and a genuinely well-built spreadsheet can trip the
cadence test — the alert email says so. Treat a hit as a reason to ask how
someone is getting on, never as proof.

The welcome page states that usage is logged. Worth keeping: it makes the signal
more meaningful, and at a regulated firm employee monitoring deserves the notice.

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
