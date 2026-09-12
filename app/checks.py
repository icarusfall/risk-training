"""Self-check engine.

Two principles:

1. METHOD-AGNOSTIC. We compare the joiner's NUMBER to ours within a relative
   tolerance. MMULT, SUMPRODUCT, pairwise COVARIANCE.S, a pivot table and sheer
   determination - all pass identically. The point is that they understand the
   maths, not that they memorised a worksheet function.

2. PER-JOINER. Each person gets their own test portfolio, derived from their
   user seed, so two joiners cannot compare answers and get the same number.
   It also means a leaked answer key has to be generated per person, which is
   what makes the canary in canary.py a reliable signal.

Answers are recomputed live from the current dataset, so a data refresh can
never leave a stale key behind.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from . import config
from .data import datasets
from .reference import advanced as A
from .reference import model as M


# --------------------------------------------------------------------------- #
# per-joiner test portfolio
# --------------------------------------------------------------------------- #
def test_portfolio(seed: int, ds: datasets.Dataset, n: int = 12) -> pd.Series:
    """A reproducible long-only portfolio of `n` names for this joiner.

    Round numbers on purpose: weights are whole percents that sum to 100, so
    nobody loses an afternoon to a rounding mismatch.
    """
    rng = np.random.default_rng(seed)

    # Draw from the middle of the cap distribution, not the whole of it. A
    # 12-name basket that happens to catch Unilever and HSBC gives them 30%
    # benchmark weights each, so the active positions come out at -25% and the
    # tracking error is nonsense. Excluding the mega-caps and the tail keeps the
    # benchmark realistic enough that the TE number means something.
    u = ds.universe.set_index("yahoo")
    caps = u["mcap_gbp_m"].astype(float).dropna().sort_values(ascending=False)
    eligible = [t for t in caps.index[10:75] if t in ds.prices.columns]
    cols = sorted(eligible) if len(eligible) >= n else sorted(ds.prices.columns)
    picks = sorted(rng.choice(cols, size=min(n, len(cols)), replace=False).tolist())
    raw = rng.integers(3, 16, size=len(picks)).astype(float)

    # Largest-remainder rounding to whole percents. Dumping the residual on one
    # name (the last, say) can round it to zero, which looks like a bug to the
    # joiner and makes a holding silently vanish from their spreadsheet.
    exact = 100 * raw / raw.sum()
    floor = np.floor(exact).astype(int)
    for i in np.argsort(-(exact - floor))[:100 - int(floor.sum())]:
        floor[i] += 1
    floor = np.maximum(floor, 1)                    # nobody gets a zero weight
    while floor.sum() > 100:                        # trim from the largest
        floor[int(np.argmax(floor))] -= 1
    return pd.Series(floor / 100.0, index=picks, name="weight")


def benchmark_weights(ds: datasets.Dataset, names: list[str]) -> pd.Series:
    """Cap weights over just the joiner's names, renormalised to 1.

    Keeps the tracking-error exercise to a 12x12 problem they can eyeball,
    rather than an 81-name one they cannot.
    """
    u = ds.universe.set_index("yahoo")
    caps = u.loc[[n for n in names if n in u.index], "mcap_gbp_m"].astype(float)
    return (caps / caps.sum()).reindex(names).fillna(0.0)


def assigned_stock(seed: int, ds: datasets.Dataset) -> str:
    """One stock per joiner for the single-name exercises."""
    rng = np.random.default_rng(seed + 7919)
    return str(rng.choice(sorted(ds.prices.columns)))


# --------------------------------------------------------------------------- #
# the checks
# --------------------------------------------------------------------------- #
@dataclass
class Check:
    id: str
    module: str
    prompt: str
    unit: str                       # "percent" | "number" | "text"
    compute: Callable
    hint: str = ""
    rtol: float | None = None


def _ctx(seed: int, dataset: str = "core") -> dict:
    ds = datasets.build(dataset)
    w = test_portfolio(seed, ds)
    names = list(w.index)
    px = ds.prices[names]
    return {"ds": ds, "w": w, "names": names, "px": px,
            "wb": benchmark_weights(ds, names),
            "stock": assigned_stock(seed, ds)}


def _vol_at(freq: str):
    def f(c):
        s = c["ds"].prices[c["stock"]]
        r = M.returns(s.to_frame(), freq)
        return float(100 * M.annualise_vol(r.iloc[:, 0].std(ddof=1), freq))
    return f


def _port_vol(c):
    r = M.returns(c["px"], "weekly")
    S = M.cov_matrix(r)
    return float(100 * M.portfolio_vol(c["w"].to_numpy(), S, "weekly"))


def _te(c):
    r = M.returns(c["px"], "weekly")
    S = M.cov_matrix(r)
    return float(100 * M.tracking_error(c["w"].to_numpy(), c["wb"].to_numpy(), S, "weekly"))


def _top_contributor(c):
    r = M.returns(c["px"], "weekly")
    S = M.cov_matrix(r)
    rc = M.risk_contributions(c["w"].to_numpy(), S, "weekly")
    return str(rc["ctr"].idxmax())


def _ewma_vol(lam: float):
    def f(c):
        r = M.returns(c["px"], "weekly")
        S = M.cov_ewma(r, lam)
        return float(100 * M.portfolio_vol(c["w"].to_numpy(), S, "weekly"))
    return f


def _var_parametric(c):
    r = M.returns(c["px"], "weekly")
    S = M.cov_matrix(r)
    return float(100 * A.var_parametric(c["w"].to_numpy(), S, conf=0.99))


def _var_historical(c):
    r = M.returns(c["px"], "weekly")
    pr = pd.Series(r.to_numpy() @ c["w"].to_numpy(), index=r.index)
    return float(100 * A.var_historical(pr, conf=0.99))


def _n_excluded(c):
    return float(len(c["ds"].excluded.get("data_quality", []))
                 + len(c["ds"].excluded.get("short_history", [])))


def _beta(c):
    ds = c["ds"]
    bench = ds.benchmarks[config.TOTAL_RETURN_BENCHMARK].dropna()
    r = M.returns(ds.prices[[c["stock"]]], "weekly")
    rm = M.returns(bench.to_frame(), "weekly").iloc[:, 0]
    idx = r.index.intersection(rm.index)
    return float(A.market_model(r.loc[idx], rm.loc[idx])["beta"].iloc[0])


CHECKS: dict[str, Check] = {ck.id: ck for ck in [
    Check("m1_excluded", "1", "How many of the 100 names did you have to drop - "
          "for bad data or for too short a history?", "number", _n_excluded,
          "Count both reasons together. Our cleaning log has the answer, but try first."),
    Check("m2_vol_daily", "2", "Annualised volatility of {stock} from DAILY returns, "
          "over the whole sample (%)", "percent", _vol_at("daily"),
          "Standard deviation of daily returns, times sqrt(252)."),
    Check("m2_vol_weekly", "2", "Annualised volatility of {stock} from WEEKLY "
          "(Wednesday-to-Wednesday) returns (%)", "percent", _vol_at("weekly"),
          "Sample Wednesday closes, then sqrt(52). It will not exactly match the daily figure - that is the lesson."),
    Check("m2_vol_monthly", "2", "Annualised volatility of {stock} from MONTHLY "
          "(month-end) returns (%)", "percent", _vol_at("monthly"),
          "sqrt(12). Fewer observations means a noisier estimate."),
    Check("m3_port_vol", "3", "Annualised volatility of YOUR portfolio, from weekly "
          "returns and a sample covariance matrix (%)", "percent", _port_vol,
          "sqrt(w' S w), then annualise. Diversification should put this below the average stock."),
    Check("m4_te", "4", "Annualised tracking error of your portfolio against the "
          "cap-weighted benchmark (%)", "percent", _te,
          "Same covariance matrix, but with active weights: w_p - w_b."),
    Check("m4_top_ctr", "4", "Which holding contributes the MOST to your total risk? "
          "(ticker)", "text", _top_contributor,
          "Contribution to risk, not weight. CTR_i = w_i * (S w)_i / sigma."),
    Check("m5_ewma_94", "5", "Annualised portfolio volatility using an EWMA covariance "
          "with lambda = 0.94 (%)", "percent", _ewma_vol(0.94),
          "Scale each return row by sqrt of its weight before forming R'R. Half-life is about 11 weeks."),
    Check("m5_ewma_97", "5", "The same, with lambda = 0.97 (%)", "percent", _ewma_vol(0.97),
          "Longer memory, so a smoother and usually higher number in calm markets."),
    Check("m6_var_param", "6", "One-week 99% parametric VaR of your portfolio, as a "
          "positive loss (%)", "percent", _var_parametric,
          "2.326 standard deviations, on the weekly (not annualised) volatility."),
    Check("m6_var_hist", "6", "One-week 99% HISTORICAL VaR of your portfolio (%)",
          "percent", _var_historical,
          "The 1st percentile of your portfolio's own realised weekly returns."),
    Check("m7_beta", "7", "Beta of {stock} against the total-return benchmark, "
          "weekly returns", "number", _beta,
          "Slope of the regression of the stock on the market. SLOPE() will do it."),
]}


def context_for(seed: int, dataset: str = "core") -> dict:
    return _ctx(seed, dataset)


def prompt_for(check: Check, ctx: dict) -> str:
    return check.prompt.format(stock=ctx["stock"])


def expected(check_id: str, seed: int, dataset: str = "core"):
    return CHECKS[check_id].compute(_ctx(seed, dataset))


def grade(check_id: str, submitted, seed: int, dataset: str = "core") -> dict:
    """Compare a submission to the reference answer."""
    ck = CHECKS[check_id]
    exp = expected(check_id, seed, dataset)
    if ck.unit == "text":
        ok = str(submitted).strip().upper().replace(".L", "") == str(exp).upper().replace(".L", "")
        return {"correct": ok, "expected": exp, "rel_error": None}
    try:
        got = float(str(submitted).strip().rstrip("%"))
    except ValueError:
        return {"correct": False, "expected": exp, "rel_error": None,
                "message": "That does not look like a number."}
    rtol = ck.rtol or config.CHECK_RTOL
    denom = abs(exp) if abs(exp) > 1e-12 else 1.0
    rel = abs(got - exp) / denom
    return {"correct": bool(rel <= rtol), "expected": exp, "rel_error": rel,
            "submitted": got}


def checks_for_module(module: str) -> list[Check]:
    return [c for c in CHECKS.values() if c.module == module]
