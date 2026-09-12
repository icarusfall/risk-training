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


def stock_label(ds: datasets.Dataset, ticker: str) -> str:
    """"Kingfisher plc (KGF.L)" rather than a bare ticker.

    Question text that reads as jargon puts people off before they have started,
    and the ticker on its own tells a new joiner nothing.
    """
    u = ds.universe.set_index("yahoo")
    if ticker in u.index:
        return f"{u.loc[ticker, 'name']} ({ticker})"
    return ticker


def _ctx(seed: int, dataset: str = "core") -> dict:
    ds = datasets.build(dataset)
    w = test_portfolio(seed, ds)
    names = list(w.index)
    px = ds.prices[names]
    stock = assigned_stock(seed, ds)
    return {"ds": ds, "w": w, "names": names, "px": px,
            "wb": benchmark_weights(ds, names),
            "stock": stock, "stock_label": stock_label(ds, stock)}


# Universe-wide objects for modules 8 and 9 are identical for every joiner and
# moderately expensive, so they are memoised on the price cache's mtime and
# rebuilt only when the data refreshes.
_universe_cache: dict[str, tuple[float, dict]] = {}


def _universe_models(dataset: str = "core") -> dict:
    """The full-universe covariance, its PCA, and the cross-sectional model."""
    from .data import store
    mtime = store.PRICES_PARQUET.stat().st_mtime if store.PRICES_PARQUET.exists() else 0.0
    hit = _universe_cache.get(dataset)
    if hit and hit[0] == mtime:
        return hit[1]

    ds = datasets.build(dataset)
    px = ds.prices
    rw = M.returns(px, "weekly")
    S = M.cov_matrix(rw)

    vals, V = A.pca_deflation(S, k=5)
    total_var = float(np.trace(S.to_numpy()))
    S_pca = A.cov_from_pca(vals, V, S)
    pc1_score = pd.Series(rw.to_numpy() @ V["PC1"].to_numpy(), index=rw.index)

    mcap = store.market_caps().loc[px.index]
    industries = ds.universe.set_index("yahoo").loc[list(px.columns), "industry"]
    cs = A.cross_sectional_model(px, mcap, industries, rw)

    out = {"ds": ds, "rw": rw, "S": S, "eigenvalues": vals, "V": V,
           "total_var": total_var, "S_pca": S_pca, "pc1_score": pc1_score,
           "equal_weight": rw.mean(axis=1), "cs": cs}
    _universe_cache[dataset] = (mtime, out)
    return out


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


# Module 1 works from the RAW file, not the cleaned one, so its checks are
# computed there. Note the count below is NOT the same set as core's
# exclusions even though both happen to number 19: core removes two names on
# data quality before it ever tests their history length.
# The first TRADING day of 2005, not 1 January - that was a Saturday and New
# Year's Day besides, so there is no row for it and a question naming it sends
# people looking for one. No name in the panel begins in early January 2005, so
# the boundary is unambiguous either way and the answer is the same.
M1_START = "2005-01-03"


def _n_no_history(c):
    """How many of the 100 names have no price back to the first trading day
    of 2005."""
    px = datasets.build("raw").prices
    firsts = px.apply(lambda col: col.first_valid_index())
    return float((firsts > pd.Timestamp(M1_START)).sum())


def _scale_break_ticker(c):
    """The name whose price drops by roughly ten times and stays there."""
    best, best_gap = "", 1e9
    for rep in datasets.build("raw").quality_report:
        for b in rep["breaks"]:
            gap = abs(float(b["ratio"]) - 10.0)
            if gap < best_gap:
                best, best_gap = rep["ticker"], gap
    return best


def _beta(c):
    ds = c["ds"]
    bench = ds.benchmarks[config.TOTAL_RETURN_BENCHMARK].dropna()
    r = M.returns(ds.prices[[c["stock"]]], "weekly")
    rm = M.returns(bench.to_frame(), "weekly").iloc[:, 0]
    idx = r.index.intersection(rm.index)
    return float(A.market_model(r.loc[idx], rm.loc[idx])["beta"].iloc[0])


# --- module 8: cross-sectional factor model ----------------------------------
def _size_exposure(c):
    X = _universe_models()["cs"]["X"]
    return float(X.loc[c["stock"], "size"]) if c["stock"] in X.index else float("nan")


def _factor_vol(name: str):
    def f(c):
        F = _universe_models()["cs"]["F"]
        return float(100 * F[name].std(ddof=1) * np.sqrt(52))
    return f


def _cs_port_vol(c):
    Sig = _universe_models()["cs"]["Sigma"]
    names = [n for n in c["names"] if n in Sig.index]
    sub = Sig.loc[names, names]
    w = c["w"].reindex(names).to_numpy()
    return float(100 * M.portfolio_vol(w, sub, "weekly"))


# --- module 9: statistical / PCA model ---------------------------------------
def _pc1_variance(c):
    um = _universe_models()
    return float(100 * um["eigenvalues"][0] / um["total_var"])


def _pc1_corr(c):
    um = _universe_models()
    return float(np.corrcoef(um["pc1_score"], um["equal_weight"])[0, 1])


def _pca_port_vol(c):
    S_pca = _universe_models()["S_pca"]
    names = [n for n in c["names"] if n in S_pca.index]
    sub = S_pca.loc[names, names]
    w = c["w"].reindex(names).to_numpy()
    return float(100 * M.portfolio_vol(w, sub, "weekly"))


# --- module 10: judging a model rather than building one ---------------------
def _port_return_series(c) -> pd.Series:
    r = M.returns(c["px"], "weekly")
    return pd.Series(r.to_numpy() @ c["w"].to_numpy(), index=r.index)


def _bias_flat(c):
    return float(A.bias_statistic(_port_return_series(c), window=104)["bias"])


def _bias_ewma(c):
    return float(A.bias_statistic_ewma(_port_return_series(c), lam=0.94)["bias"])


CHECKS: dict[str, Check] = {ck.id: ck for ck in [
    Check("m1_no_history", "1", "Working from the raw file: how many of the 100 "
          "names have no price history going back as far as 3 January 2005, the "
          "first trading day of that year?",
          "number", _n_no_history,
          "One rule, applied to every column: does it have a price on or before "
          "3 January 2005 or not? The first_date column on the Universe tab is the "
          "quick way, "
          "or COUNT each price column."),
    Check("m1_scale_break", "1", "One name's price falls by a factor of about ten "
          "and never recovers. Which ticker is it?", "text", _scale_break_ticker,
          "Look for a daily return near minus 90% that does not bounce back the "
          "next day. There are two candidates with broken data - this is the one "
          "whose jump is a clean factor of ten."),
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

    Check("m8_size_exposure", "8", "Size exposure (z-scored log market cap) of "
          "{stock} as at 27 September 2023", "number", _size_exposure,
          "Take logs of market cap across all 81 names, subtract the mean, divide "
          "by the sample standard deviation, then clip at plus or minus 3."),
    Check("m8_mom_factor_vol", "8", "Annualised volatility of the MOMENTUM factor "
          "return series (%)", "percent", _factor_vol("momentum"),
          "Standard deviation of your weekly momentum coefficients, times sqrt(52). "
          "It should come out far below any single stock."),
    Check("m8_port_vol", "8", "Annualised volatility of your portfolio under the "
          "cross-sectional model (%)", "percent", _cs_port_vol,
          "Build the full 81-name Sigma = XFX-transpose + Delta first, then take "
          "the rows and columns for your twelve holdings."),

    Check("m9_pc1_variance", "9", "Share of total variance explained by the FIRST "
          "principal component (%)", "percent", _pc1_variance,
          "First eigenvalue divided by the trace of the covariance matrix, the "
          "trace being the sum of its diagonal."),
    Check("m9_pc1_corr", "9", "Correlation between the PC1 score series and the "
          "equal-weighted market return", "number", _pc1_corr,
          "Score each week as the PC1 loadings dotted with that week of returns, "
          "then correlate against the simple average of all 81 stocks. Prepare to "
          "be slightly startled."),
    Check("m9_port_vol_5pc", "9", "Annualised volatility of your portfolio using a "
          "covariance rebuilt from 5 principal components (%)", "percent", _pca_port_vol,
          "Systematic part is V L V-transpose; then add a diagonal top-up so every "
          "stock keeps its own total variance."),

    Check("m10_bias_flat", "10", "Bias statistic for your portfolio, forecasting "
          "with a rolling 104-week volatility", "number", _bias_flat,
          "Divide each week's return by the standard deviation of the previous 104 "
          "weeks, then take the standard deviation of those ratios. 1.00 is "
          "perfectly calibrated."),
    Check("m10_bias_ewma", "10", "The same bias statistic, forecasting with EWMA at "
          "lambda = 0.94", "number", _bias_ewma,
          "Update the variance AFTER making each forecast, never before, or you are "
          "peeking at the return you are trying to predict."),
]}


def context_for(seed: int, dataset: str = "core") -> dict:
    return _ctx(seed, dataset)


def prompt_for(check: Check, ctx: dict) -> str:
    return check.prompt.format(stock=ctx.get("stock_label") or ctx["stock"])


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
