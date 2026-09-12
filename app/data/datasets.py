"""Canonical datasets.

One place decides which names, which dates and which cleaning rules apply. The
download the joiner gets and the answer key the self-check computes both come
from here, so the two agree by construction rather than by luck.

Three datasets, because Module 1 and Modules 2+ need genuinely different things:

  raw   1995-> : all 100 names exactly as they arrive. Ragged starts, real gaps,
                 bad prints left in. This is what Module 1 is for - you cannot
                 learn to spot a broken price series from a file we already
                 cleaned, and you cannot practise deciding which columns are too
                 short if every column is the same length.
  core  2005-> : ~81 names, screened and trimmed to a complete rectangle. The
                 default, and what every self-check answer is computed from.
  long  1995-> : the same treatment over a longer window, so roughly a quarter
                 fewer names survive. Adds the dot-com bubble and its unwind.

Both core and long are deliberately rectangular: answers have to be
well-defined, and they cannot be if every joiner trims the panel differently.
The judgement happens in Module 1 on `raw`; from Module 2 onward everyone works
from the same canonical file.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import quality, store

log = logging.getLogger(__name__)

DATASETS = {
    "raw": {
        "label": "Raw (all 100 names, 1995 onwards)",
        "start": "1995-01-01",
        "blurb": "Exactly as it arrives: ragged start dates, real gaps, and the bad "
                 "prints still in. Use this for Module 1.",
        "clean": False,
    },
    "core": {
        "label": "Core (2005 onwards)",
        "start": "2005-01-01",
        "blurb": "Four crises: the GFC, the 2011 euro crisis, Covid, and the 2022 gilt/LDI crisis. "
                 "Screened and trimmed. Use this from Module 2 onward.",
        "clean": True,
    },
    "long": {
        "label": "Long (1995 onwards)",
        "start": "1995-01-01",
        "blurb": "Adds the dot-com bubble and unwind, at the cost of roughly a quarter of the names.",
        "clean": True,
    },
}
DEFAULT_DATASET = "core"

# A name must print on this share of the window's trading days to be included.
MIN_COVERAGE = 0.98


@dataclass
class Dataset:
    name: str
    start: str
    prices: pd.DataFrame                 # stocks only, cleaned, GBp
    benchmarks: pd.DataFrame             # index levels
    universe: pd.DataFrame               # per-name metadata for included names
    quality_report: list = field(default_factory=list)
    excluded: dict = field(default_factory=dict)

    @property
    def tickers(self) -> list[str]:
        return list(self.prices.columns)

    def summary(self) -> dict:
        return {
            "name": self.name,
            "label": DATASETS[self.name]["label"],
            "blurb": DATASETS[self.name]["blurb"],
            "n_stocks": self.prices.shape[1],
            "n_days": self.prices.shape[0],
            "first_date": str(self.prices.index.min().date()),
            "last_date": str(self.prices.index.max().date()),
            "n_excluded": sum(len(v) for v in self.excluded.values()),
            "n_gaps": int(self.prices.isna().sum().sum()),
            "n_start_dates": int(self.prices.apply(lambda c: c.first_valid_index()).nunique()),
            "excluded": self.excluded,
            "benchmarks": list(self.benchmarks.columns),
        }


_cache: dict[str, tuple[float, Dataset]] = {}


def build(name: str = DEFAULT_DATASET) -> Dataset:
    """Assemble a dataset from the raw cache. Cached on the cache's mtime."""
    if name not in DATASETS:
        raise KeyError(f"unknown dataset {name!r}")
    mtime = store.PRICES_PARQUET.stat().st_mtime if store.PRICES_PARQUET.exists() else 0.0
    hit = _cache.get(name)
    if hit and hit[0] == mtime:
        return hit[1]

    start = DATASETS[name]["start"]
    raw = store.prices()
    uni = store.universe()
    mcap = store.market_caps()

    stock_cols = [t for t in uni["yahoo"] if t in raw.columns]
    bench_cols = [c for c in raw.columns if c not in stock_cols]

    if DATASETS[name].get("clean", True):
        screened = quality.screen_panel(raw[stock_cols], start=start)
        px = screened["prices"]
        excluded = {"data_quality": list(screened["excluded"])}
        px = px.drop(columns=screened["excluded"], errors="ignore")

        # Drop names without enough history in this window - the "is this column
        # long enough?" judgement, made explicit rather than by silent dropna.
        coverage = px.notna().mean()
        short = list(coverage[coverage < MIN_COVERAGE].index)
        excluded["short_history"] = short
        px = px.drop(columns=short, errors="ignore").ffill().dropna(how="any")
        reports = screened["reports"]
    else:
        # Untouched prices. No screening, no coverage filter, no forward fill -
        # the gaps and the bad prints ARE the exercise.
        px = raw.loc[start:, stock_cols].copy()
        px = px.dropna(axis=0, how="all")
        excluded = {"data_quality": [], "short_history": []}
        # We still run the scan, so the cleaning log can serve as the answer key
        # for the Module 1 hunt. We report; we just do not act.
        reports = quality.screen_panel(raw[stock_cols], start=start)["reports"]

    # Benchmarks, on the same calendar.
    bench = raw.loc[px.index, bench_cols].ffill() if bench_cols else pd.DataFrame(index=px.index)
    from ..reference.model import cap_weights, composite_index
    bench = bench.copy()
    cols_now = list(px.columns)
    px_for_index = px.ffill()
    bench["EQUAL_WEIGHT_TR"] = composite_index(px_for_index, cols_now)
    bench["CAPFIXED_TR"] = composite_index(
        px_for_index, cols_now, weights=cap_weights(mcap.loc[px.index], cols_now))

    u = uni[uni["yahoo"].isin(px.columns)].copy().reset_index(drop=True)
    last_cap = mcap.loc[px.index[-1], [c for c in px.columns if c in mcap.columns]]
    u["mcap_gbp_m"] = u["yahoo"].map(lambda t: round(float(last_cap.get(t, np.nan)) / 1e6, 1)
                                     if t in last_cap.index else None)
    u["weight_pct"] = u["mcap_gbp_m"] / u["mcap_gbp_m"].sum() * 100.0

    ds = Dataset(name=name, start=start, prices=px, benchmarks=bench, universe=u,
                 quality_report=reports, excluded=excluded)
    log.info("Dataset %s: %d names x %d days (%s..%s), excluded %s",
             name, px.shape[1], px.shape[0], ds.summary()["first_date"],
             ds.summary()["last_date"], {k: len(v) for k, v in excluded.items()})
    _cache[name] = (mtime, ds)
    return ds
