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
    atol: float = 0.0               # for answers that can sit near zero, like skew


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


# --- module 11: higher moments ----------------------------------------------
def _skew(c):
    return float(_port_return_series(c).skew())        # = Excel SKEW


def _excess_kurt(c):
    return float(_port_return_series(c).kurt())        # = Excel KURT, already excess


def _var_hist_95(c):
    return float(100 * A.var_historical(_port_return_series(c), conf=0.95))


def _var_cf(c):
    return float(100 * A.var_cornish_fisher(_port_return_series(c), conf=0.99))


# --- module 12: power-law tails ---------------------------------------------
# Daily, not weekly: 50 losses out of 5,405 days is the worst 1%.
def _power_law_fit(c) -> dict:
    r = M.returns(c["px"], "daily")
    pr = pd.Series(r.to_numpy() @ c["w"].to_numpy(), index=r.index)
    return A.power_law_tail(pr, k=50)


def _pl_alpha(c):
    return _power_law_fit(c)["alpha"]


def _pl_years_20(c):
    return A.power_law_years_between(_power_law_fit(c), 0.20)


# --- module 13: Student-t, copulas and Monte Carlo ---------------------------
# The market for module 13 is CAPFIXED_TR, not CUKX.L: CUKX only starts in 2010
# and the one-factor correlations want the whole sample.
def _market_weekly(ds) -> pd.Series:
    return M.returns(ds.benchmarks["CAPFIXED_TR"].dropna().to_frame(), "weekly").iloc[:, 0]


def _rank_corr_stock_market(c):
    ds = c["ds"]
    r = M.returns(ds.prices[[c["stock"]]], "weekly").iloc[:, 0]
    return A.spearman(r, _market_weekly(ds))


def _t4_var(c):
    return float(100 * A.var_student_t4(_port_return_series(c), conf=0.99))


def _mc_t_copula_es(c):
    ds = c["ds"]
    rw = M.returns(c["px"], "weekly")
    mkt = _market_weekly(ds).reindex(rw.index)
    vols = rw.std(ddof=1).to_numpy()
    rhos = np.array([rw[n].corr(mkt) for n in c["names"]])
    out = A.monte_carlo_t_copula(c["w"].to_numpy(), vols, rhos, nu=4)
    return float(100 * out["es"])


# --- module 4: the cash trap ------------------------------------------------
# A portfolio holding 95% of the BENCHMARK weights plus 5% cash. The only
# active decision is the cash, so it must carry all of the tracking error - and
# the naive decomposition says it carries none of it. See
# model.active_space_covariance for why.
CASH_WEIGHT = 0.05


def _with_cash(names, S_stocks, wb_stocks, wp_stocks):
    """Append cash as an asset: zero variance, zero covariance with everything."""
    n = len(names)
    S = np.zeros((n + 1, n + 1))
    S[:n, :n] = np.asarray(S_stocks, dtype=float)
    labels = list(names) + ["CASH"]
    Sdf = pd.DataFrame(S, index=labels, columns=labels)
    wb = np.append(np.asarray(wb_stocks, dtype=float), 0.0)
    wp = np.append(np.asarray(wp_stocks, dtype=float) * (1 - CASH_WEIGHT), CASH_WEIGHT)
    return Sdf, wb, wp


def _cash_te(c):
    """TE of 95% of the benchmark plus 5% cash. Should be 5% of benchmark vol."""
    r = M.returns(c["px"], "weekly")
    S = M.cov_matrix(r)
    Sdf, wb, wp = _with_cash(c["names"], S, c["wb"], c["wb"])
    return float(100 * M.tracking_error(wp, wb, Sdf, "weekly"))


def _cash_ctr(c):
    """Cash's contribution to TE for 95% of the joiner's own portfolio plus 5%
    cash, decomposed in active space. Zero under the naive decomposition."""
    r = M.returns(c["px"], "weekly")
    S = M.cov_matrix(r)
    Sdf, wb, wp = _with_cash(c["names"], S, c["wb"], c["w"])
    rc = M.active_risk_contributions(wp, wb, Sdf, "weekly")
    return float(100 * rc["ctr"].loc["CASH"])


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
    Check("m4_cash_te", "4", "Now hold 95% of the BENCHMARK weights and 5% cash. "
          "What is that portfolio's annualised tracking error (%)?", "percent", _cash_te,
          "Cash is an extra asset with zero variance and zero covariance with "
          "everything. Work out the active weights and use the same formula as "
          "before. The answer should be exactly 5% of the benchmark volatility."),
    Check("m4_cash_ctr", "4", "Take 95% of YOUR portfolio weights plus 5% cash. "
          "Using the active-space (rotated) covariance matrix, what does the cash "
          "position contribute to tracking error (%)? It can be negative.",
          "percent", _cash_ctr,
          "Rotate first: Sigma~ = Sigma - Cov(r_i,r_b) - Cov(r_j,r_b) + Var(r_b). "
          "Then decompose with PORTFOLIO weights, not active weights. If you get "
          "exactly zero, you decomposed the unrotated matrix.",
          0.05),
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

    Check("m11_skew", "11", "Skew of your portfolio's weekly (Wednesday-to-Wednesday) "
          "returns", "number", _skew,
          "SKEW() on the same weekly portfolio returns you used for VaR in Module 6. "
          "Give three decimal places; it is usually negative.",
          atol=0.005),
    Check("m11_kurt", "11", "EXCESS kurtosis of your portfolio's weekly returns",
          "number", _excess_kurt,
          "KURT() already subtracts the 3. If you are out by roughly 3, you have "
          "raw kurtosis."),
    Check("m11_var_hist_95", "11", "One-week 95% HISTORICAL VaR of your portfolio, "
          "as a positive loss (%)", "percent", _var_hist_95,
          "PERCENTILE.INC at 0.05 on your weekly portfolio returns, as in Module 6. "
          "Now compare it with 95% parametric VaR: which is bigger?"),
    Check("m11_var_cf", "11", "One-week 99% Cornish-Fisher VaR of your portfolio, as "
          "a positive loss (%)", "percent", _var_cf,
          "Adjust z = NORM.S.INV(0.01) using SKEW and KURT, then multiply by the "
          "weekly STDEV.S. It should come out ABOVE your historical VaR."),

    Check("m12_alpha", "12", "Take the 50 largest DAILY losses of your portfolio. "
          "Rank them 1 to 50, largest first, and give each the probability rank / n, "
          "where n is the total number of daily returns. Regress LN(probability) on "
          "LN(loss). What is the tail exponent alpha (minus the slope)?",
          "number", _pl_alpha,
          "=-SLOPE(LN(prob), LN(loss)), with losses as positive numbers. A Power "
          "trendline on a log-log scatter shows the same slope as its exponent. "
          "It usually lands between 3 and 4. Fifty is only a marking convention; "
          "try other cut-offs and watch the answer move."),
    Check("m12_years_20", "12", "Extend your fitted line. On average, how many years "
          "would pass between daily losses of 20% or more? (Use 252 trading days a "
          "year.)", "number", _pl_years_20,
          "The line says P(loss >= x) = EXP(intercept) * x^slope. One over that is "
          "the number of days between such losses; divide by 252. Use the same "
          "units for x as you used for the losses in the fit."),

    Check("m13_rank_corr", "13", "RANK correlation between the weekly returns of "
          "{stock} and the CAPFIXED_TR benchmark", "number", _rank_corr_stock_market,
          "CORREL of RANK.AVG of each series. Plain CORREL on the returns is Pearson "
          "correlation, which is usually close but not the same."),
    Check("m13_t4_var", "13", "One-week 99% VaR of your portfolio using a Student-t "
          "with 4 degrees of freedom, as a positive loss (%)", "percent", _t4_var,
          "-T.INV(0.01, 4) * SQRT(2/4) * the weekly STDEV.S. The SQRT(2/4) rescales "
          "the t to unit variance. It should be about 14% above the normal VaR."),
    Check("m13_mc_es", "13", "Simulate your portfolio with version C (t tails, t "
          "copula, nu = 4, one-factor correlations with CAPFIXED_TR). What is the "
          "one-week 99% expected shortfall, as a positive loss (%)?", "percent",
          _mc_t_copula_es,
          "Use at least 10,000 scenarios, with ONE chi-square draw per scenario "
          "shared by all 12 holdings. Simulation noise is allowed for: answers "
          "within 12% are marked correct.",
          0.12),
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
    correct = rel <= rtol or abs(got - exp) <= ck.atol
    return {"correct": bool(correct), "expected": exp, "rel_error": rel,
            "submitted": got}


def checks_for_module(module: str) -> list[Check]:
    return [c for c in CHECKS.values() if c.module == module]
