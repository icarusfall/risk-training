"""Data-quality screening.

Free price data is not clean, and the dirt here comes in three distinct kinds.
Treating them as one thing gets you either a poisoned covariance matrix or a
screen that throws away real history:

  1. Bank-holiday junk. Yahoo stamps wrong-scale prints on UK market holidays
     (Christmas Day, Good Friday, May Day) for a few names - BAE at 16x and
     Unilever at 52x, mostly in the 1990s. Note these days are NOT sparse:
     coverage is 98%+, because Yahoo carries the rest of the panel forward. So
     a coverage-based calendar filter does not catch them, and the excursion
     test below is what actually does the work.

  2. Bad prints that revert. Polar Capital Technology shows 373.50 -> 37.35 ->
     377.30. Repairable, so we repair it. These arrive in runs as often as
     singly (the 25th AND the 27th of December), which is why the test looks
     for a return to base within a few days rather than on the very next one.

  3. Persistent scale breaks. PCT again: 363.50 -> 37.43, and it STAYS at the
     new scale. Not safely repairable without a corporate-action feed, so the
     name is excluded.

What we deliberately do NOT exclude: real market history. Barclays +73% on
2009-01-26 and RBS -67% on 2009-01-19 are genuine, and a screen that removes
them has removed the most interesting fortnight in the sample. The break rule
is therefore keyed on implausible SCALE (>=5x), not on large returns.

Every decision is recorded and published, because hunting these down is
Module 1's exercise - the joiner should find them before reading our list.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# A one-day move beyond this is worth inspecting in a FTSE 100 name.
SPIKE_THRESHOLD = 0.60
# An excursion that returns to its starting level within this many trading
# days was a bad print (or a short run of them), not a market move.
EXCURSION_WINDOW = 5
# "Returned to its starting level" means within this tolerance.
EXCURSION_TOL = 0.25
# A persistent jump of this scale is a denomination error, not a market move.
BREAK_RATIO = 5.0
# A date needs this share of the active panel to count as a trading day.
MIN_DAY_COVERAGE = 0.60


# --------------------------------------------------------------------------- #
# 1. calendar
# --------------------------------------------------------------------------- #
def trading_days(px: pd.DataFrame, min_coverage: float = MIN_DAY_COVERAGE) -> pd.DatetimeIndex:
    """Dates where enough of the *currently listed* panel actually printed.

    Measured against names already alive on each date, so the early years are
    not penalised for names that had not listed yet. In practice this drops
    nothing on the current panel (Yahoo fills holidays forward); it is kept as
    cheap insurance against a future feed that leaves genuine gaps instead.
    """
    alive = px.notna().cummax(axis=0).sum(axis=1).clip(lower=1)
    present = px.notna().sum(axis=1)
    return px.index[(present / alive) >= min_coverage]


def apply_calendar(px: pd.DataFrame, min_coverage: float = MIN_DAY_COVERAGE) -> tuple[pd.DataFrame, list[str]]:
    keep = trading_days(px, min_coverage)
    dropped = [str(d.date()) for d in px.index.difference(keep)]
    if dropped:
        log.info("Dropped %d non-trading day(s) from the calendar", len(dropped))
    return px.loc[keep], dropped


# --------------------------------------------------------------------------- #
# 2 & 3. per-series anomalies
# --------------------------------------------------------------------------- #
def scan_series(s: pd.Series, name: str = "") -> dict:
    """Classify anomalies in one price series into spikes and scale breaks.

    A "spike" is an EXCURSION: the price leaps, then comes back to roughly where
    it started within a few days. That covers single bad prints and also short
    runs of them - Yahoo stamps bad values on both Christmas Day and the 27th,
    so a next-day-reversion test alone misses them.
    """
    s = s.dropna()
    out = {"ticker": name, "spikes": [], "breaks": [], "n": int(len(s))}
    if len(s) < 30:
        return out

    vals = s.to_numpy(dtype=float)
    lr = np.log(s / s.shift(1))
    big = lr[lr.abs() > np.log(1 + SPIKE_THRESHOLD)]

    consumed: set[int] = set()
    for dt, val in big.items():
        pos = int(lr.index.get_loc(dt))
        if pos in consumed:
            continue
        base = vals[pos - 1] if pos > 0 else vals[0]

        # Does it come back to `base` within the window?
        back_at = None
        for j in range(pos + 1, min(pos + 1 + EXCURSION_WINDOW, len(vals))):
            if abs(vals[j] / base - 1.0) <= EXCURSION_TOL:
                back_at = j
                break

        ratio = float(np.exp(abs(val)))
        rec = {"date": str(pd.Timestamp(dt).date()),
               "return_pct": round(100 * (float(np.exp(val)) - 1), 1),
               "price_before": round(float(base), 2),
               "price_after": round(float(vals[pos]), 2),
               "ratio": round(ratio, 1)}

        if back_at is not None:
            rec["bad_dates"] = [str(pd.Timestamp(d).date()) for d in s.index[pos:back_at]]
            out["spikes"].append(rec)
            consumed.update(range(pos, back_at))
        elif ratio >= BREAK_RATIO:
            out["breaks"].append(rec)
        # else: a large, persistent, plausibly-scaled move => real market history.
    return out


def repair_spikes(s: pd.Series, spikes: list[dict]) -> pd.Series:
    """Blank isolated bad prints and interpolate across them."""
    if not spikes:
        return s
    out = s.copy()
    bad: list[str] = []
    for sp in spikes:
        bad.extend(sp.get("bad_dates") or [sp["date"]])
    idx = pd.to_datetime(sorted(set(bad)))
    hit = out.index.intersection(idx)
    out.loc[hit] = np.nan
    return out.interpolate(method="time", limit_area="inside")


def screen_panel(px: pd.DataFrame, start: str | None = None) -> dict:
    """Full pipeline: calendar -> spike repair -> break exclusion.

    `start` matters: most of the denomination noise in this panel is in the
    1990s, so screening the window you will actually model keeps far more names.
    """
    window = px.loc[start:] if start else px
    cleaned, dropped_days = apply_calendar(window)

    reports, excluded = [], []
    for c in cleaned.columns:
        rep = scan_series(cleaned[c], c)
        if rep["spikes"]:
            cleaned[c] = repair_spikes(cleaned[c], rep["spikes"])
            rep = {**scan_series(cleaned[c], c), "spikes": rep["spikes"]}
        if rep["spikes"] or rep["breaks"]:
            reports.append(rep)
        if rep["breaks"]:
            excluded.append(c)

    if excluded:
        log.warning("Excluding %d name(s) with unrepairable scale breaks: %s",
                    len(excluded), excluded)
    return {"prices": cleaned, "reports": reports, "excluded": excluded,
            "dropped_days": dropped_days,
            "n_spikes_repaired": sum(len(r["spikes"]) for r in reports)}
