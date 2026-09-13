"""Reference implementations for the later modules: VaR, factor models, PCA.

Deliberately free of scipy - Python's stdlib NormalDist covers the normal
quantile, and the chi-square survival function at one degree of freedom has a
closed form. One less wheel to build on Railway.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from .model import ANNUALISATION, portfolio_vol

_N = NormalDist()


def norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF."""
    return _N.inv_cdf(p)


def chi2_sf_1df(x: float) -> float:
    """P(X > x) for chi-square with 1 degree of freedom."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


# --------------------------------------------------------------------------- #
# Value at Risk (module 6)
# --------------------------------------------------------------------------- #
def var_parametric(w, S, conf: float = 0.99, horizon: int = 1,
                   mean: float = 0.0) -> float:
    """Normal VaR, returned as a POSITIVE loss fraction.

    Scaled to the horizon by sqrt(time) - the same rule as annualisation, and
    it inherits the same iid assumption.
    """
    sig = portfolio_vol(w, S) * math.sqrt(horizon)
    return float(-(mean * horizon + norm_ppf(1 - conf) * sig))


def var_historical(port_returns: pd.Series, conf: float = 0.99) -> float:
    """Historical VaR: the empirical quantile of realised P&L.

    No distributional assumption, so it keeps the fat left tail that the
    parametric version smooths away.
    """
    r = np.asarray(pd.Series(port_returns).dropna(), dtype=float)
    return float(-np.percentile(r, (1 - conf) * 100.0))


def expected_shortfall(port_returns: pd.Series, conf: float = 0.99) -> float:
    """Average loss GIVEN the VaR threshold is breached."""
    r = np.asarray(pd.Series(port_returns).dropna(), dtype=float)
    cut = np.percentile(r, (1 - conf) * 100.0)
    tail = r[r <= cut]
    return float(-tail.mean()) if tail.size else float("nan")


def cornish_fisher_z(z: float, skew: float, excess_kurt: float) -> float:
    """The normal quantile adjusted for skew and EXCESS kurtosis (module 11)."""
    s, k = skew, excess_kurt
    return (z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24
            - (2 * z ** 3 - 5 * z) * s ** 2 / 36)


def var_cornish_fisher(port_returns: pd.Series, conf: float = 0.99) -> float:
    """Cornish-Fisher VaR as a POSITIVE loss fraction, mean set to zero.

    Uses Excel's conventions - SKEW, KURT (already excess) and STDEV.S - which
    are exactly pandas' skew(), kurt() and std(). On this data it lands above
    historical VaR, not between parametric and historical: the expansion is
    meant for mild departures from normality and weekly excess kurtosis is 5+.
    """
    r = pd.Series(port_returns).dropna()
    z = cornish_fisher_z(norm_ppf(1 - conf), float(r.skew()), float(r.kurt()))
    return float(-z * r.std(ddof=1))


def kupiec_pof(exceptions: int, n: int, conf: float = 0.99) -> dict:
    """Kupiec proportion-of-failures test.

    Asks only whether the NUMBER of exceptions is plausible, not whether they
    clustered - clustering is what the Christoffersen test adds.
    """
    p = 1.0 - conf
    if n == 0:
        return {"exceptions": 0, "n": 0, "lr": float("nan"), "p_value": float("nan"),
                "expected": 0.0, "rate": float("nan"), "reject_95": False}
    pi = exceptions / n
    ll_null = (n - exceptions) * math.log(1 - p) + exceptions * math.log(p)
    if exceptions == 0:
        ll_alt = n * math.log(1 - pi) if pi < 1 else 0.0
    elif exceptions == n:
        ll_alt = n * math.log(pi)
    else:
        ll_alt = (n - exceptions) * math.log(1 - pi) + exceptions * math.log(pi)
    lr = -2.0 * (ll_null - ll_alt)
    return {"exceptions": int(exceptions), "n": int(n), "expected": p * n,
            "rate": pi, "lr": float(lr), "p_value": chi2_sf_1df(lr),
            "reject_95": bool(lr > 3.841)}


def backtest_var(port_returns: pd.Series, var_level: float, conf: float = 0.99) -> dict:
    """Count breaches of a FIXED VaR level and test the count."""
    r = pd.Series(port_returns).dropna()
    exc = int((r < -abs(var_level)).sum())
    return kupiec_pof(exc, len(r), conf)


# --------------------------------------------------------------------------- #
# Single-factor (market) model  (module 7)
# --------------------------------------------------------------------------- #
def market_model(r: pd.DataFrame, rm: pd.Series) -> pd.DataFrame:
    """OLS of every stock on the market return, solved in one lstsq call.

    Returns alpha, beta, residual (specific) vol and R-squared.
    """
    idx = r.index.intersection(pd.Series(rm).dropna().index)
    Y = r.loc[idx].to_numpy(dtype=float)
    x = pd.Series(rm).loc[idx].to_numpy(dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ coef
    dof = max(len(idx) - 2, 1)
    sse = (resid ** 2).sum(axis=0)
    sst = ((Y - Y.mean(axis=0)) ** 2).sum(axis=0)
    return pd.DataFrame({
        "alpha": coef[0],
        "beta": coef[1],
        "resid_vol": np.sqrt(sse / dof),
        "r_squared": 1.0 - sse / np.where(sst == 0, np.nan, sst),
    }, index=r.columns)


def cov_from_market_model(fit: pd.DataFrame, market_var: float) -> pd.DataFrame:
    """Sigma = beta beta' * var(market) + diag(specific variance).

    The N(N+1)/2 free parameters of a sample covariance collapse to 2N+1. That
    is the entire argument for factor models: far fewer things to estimate, so
    far less estimation noise.
    """
    b = fit["beta"].to_numpy(dtype=float).reshape(-1, 1)
    S = b @ b.T * float(market_var) + np.diag(fit["resid_vol"].to_numpy(dtype=float) ** 2)
    return pd.DataFrame(S, index=fit.index, columns=fit.index)


# --------------------------------------------------------------------------- #
# Cross-sectional factor model  (module 8)
# --------------------------------------------------------------------------- #
def zscore(s: pd.Series, winsor: float = 3.0) -> pd.Series:
    """Standardise, then clip. Winsorising stops one silly print from becoming
    the factor."""
    sd = s.std(ddof=1)
    z = (s - s.mean()) / (sd if sd and np.isfinite(sd) else 1.0)
    return z.clip(-winsor, winsor)


def build_exposures(px: pd.DataFrame, mcap: pd.DataFrame, industries: pd.Series,
                    asof, cols: list[str]) -> pd.DataFrame:
    """Style exposures observable from price alone, as at a date.

        size      log market cap
        momentum  12-month return skipping the last month (classic 12-1)
        lowvol    negative trailing 1-year volatility

    Industry dummies come from the ICB mapping. A proper VALUE factor needs
    book value, which we have no free point-in-time source for - dividend yield
    stands in, and the notes are explicit that it is a proxy.
    """
    cols = [c for c in cols if c in px.columns]
    hist = px.loc[:asof, cols].ffill()
    if len(hist) < 260:
        raise ValueError("need ~1y of history before asof to build exposures")

    size = np.log(mcap.loc[:asof, [c for c in cols if c in mcap.columns]].ffill().iloc[-1])
    mom = hist.iloc[-21] / hist.iloc[-252] - 1.0
    vol = hist.pct_change().iloc[-252:].std(ddof=1) * math.sqrt(252)

    X = pd.DataFrame({
        "size": zscore(size.reindex(cols)),
        "momentum": zscore(mom.reindex(cols)),
        "lowvol": zscore(-vol.reindex(cols)),
    }, index=cols)
    dummies = pd.get_dummies(pd.Series(industries).reindex(cols), prefix="ind", dtype=float)
    return pd.concat([X, dummies], axis=1).dropna()


def cross_sectional_regression(fwd_ret: pd.Series, X: pd.DataFrame,
                               weights: pd.Series | None = None) -> pd.Series:
    """One period's cross-sectional regression -> that period's factor returns.

    Weighting by sqrt(cap) is the standard choice: residuals are
    heteroskedastic in size, and it stops the smallest names setting the factor.
    """
    common = X.index.intersection(pd.Series(fwd_ret).dropna().index)
    Xm = X.loc[common].to_numpy(dtype=float)
    y = pd.Series(fwd_ret).loc[common].to_numpy(dtype=float)
    if weights is not None:
        sw = np.sqrt(np.asarray(pd.Series(weights).loc[common], dtype=float))
        Xm, y = Xm * sw[:, None], y * sw
    coef, *_ = np.linalg.lstsq(Xm, y, rcond=None)
    return pd.Series(coef, index=X.columns)


def factor_model_covariance(F: pd.DataFrame, X: pd.DataFrame,
                            specific_var: pd.Series) -> pd.DataFrame:
    """Sigma = X F X' + Delta, from a history of factor returns F."""
    Fc = F.cov()
    Xm = X.to_numpy(dtype=float)
    S = Xm @ Fc.to_numpy(dtype=float) @ Xm.T + np.diag(
        np.asarray(specific_var.reindex(X.index).fillna(0.0), dtype=float))
    return pd.DataFrame(S, index=X.index, columns=X.index)


# --------------------------------------------------------------------------- #
# Statistical / PCA model  (module 9)
# --------------------------------------------------------------------------- #
def power_iteration(S, iters: int = 500, tol: float = 1e-13,
                    seed: int = 0) -> tuple[float, np.ndarray]:
    """Dominant eigenpair by repeated multiply-and-normalise.

    This is the Excel-friendly route: one MMULT column, divided by its own
    norm, copied across until the numbers stop moving.
    """
    A = np.asarray(S, dtype=float)
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(A.shape[0])
    v /= np.linalg.norm(v)
    lam = 0.0
    for _ in range(iters):
        w = A @ v
        nw = np.linalg.norm(w)
        if nw < 1e-300:
            break
        v_new = w / nw
        lam_new = float(v_new @ A @ v_new)
        converged = abs(lam_new - lam) < tol
        v, lam = v_new, lam_new
        if converged:
            break
    # Sign is arbitrary in an eigenvector; fix it so PC1 reads as "the market".
    if v[int(np.argmax(np.abs(v)))] < 0:
        v = -v
    return lam, v


def pca_deflation(S: pd.DataFrame, k: int = 5) -> tuple[np.ndarray, pd.DataFrame]:
    """First k principal components via power iteration + Hotelling deflation.

    Subtracting lambda*v*v' removes the component just found, so the next pass
    of the same routine returns the next one.
    """
    A = np.asarray(S, dtype=float).copy()
    vals, vecs = [], []
    for _ in range(k):
        lam, v = power_iteration(A)
        vals.append(lam)
        vecs.append(v)
        A = A - lam * np.outer(v, v)
    V = pd.DataFrame(np.column_stack(vecs), index=S.index,
                     columns=[f"PC{i + 1}" for i in range(k)])
    return np.array(vals), V


def variance_explained(eigenvalues, total_var: float) -> np.ndarray:
    return np.asarray(eigenvalues, dtype=float) / float(total_var)


def cov_from_pca(eigenvalues, V: pd.DataFrame, S: pd.DataFrame) -> pd.DataFrame:
    """Sigma_k = V L V' + diag(residual variance).

    The diagonal top-up keeps each stock's total variance intact even though
    only k components are retained.
    """
    L = np.diag(np.asarray(eigenvalues, dtype=float))
    Vm = V.to_numpy(dtype=float)
    systematic = Vm @ L @ Vm.T
    resid = np.maximum(np.diag(np.asarray(S, dtype=float)) - np.diag(systematic), 0.0)
    return pd.DataFrame(systematic + np.diag(resid), index=S.index, columns=S.index)


# --------------------------------------------------------------------------- #
# Module 8 pipeline: the whole cross-sectional model, as the lesson specifies
# --------------------------------------------------------------------------- #
# Exposures are measured on this date and the regressions run over every week
# after it. A FIXED calendar anchor, not "156 weeks back from today": the lesson
# has to name a date the joiner can look up, and an anchor that slides with the
# data would move the exposures - and so every answer - each time it refreshes.
# 27 September 2023 was a Wednesday, matching our weekly sampling.
CS_ASOF = "2023-09-27"


def cross_sectional_model(px: pd.DataFrame, mcap: pd.DataFrame,
                          industries: pd.Series, weekly: pd.DataFrame,
                          asof: str = CS_ASOF) -> dict:
    """Build exposures once, then regress every later week on them.

    Exposures are fixed as at `asof`, so they are known before every return they
    explain - no look-ahead. A production model refreshes them monthly, but
    freezing them keeps the exercise reproducible in a spreadsheet and does not
    change what the joiner learns.

    Returns exposures X, factor returns F, specific variances, and Sigma.
    """
    asof = pd.Timestamp(asof)
    if (weekly.index > asof).sum() < 30:
        raise ValueError("not enough weekly observations after asof")

    cols = list(px.columns)
    X = build_exposures(px, mcap, industries, asof, cols)
    names = list(X.index)

    caps = mcap[names].ffill().loc[:asof].iloc[-1]
    rets = weekly.loc[weekly.index > asof, names]

    rows = {}
    for dt, r in rets.iterrows():
        rows[dt] = cross_sectional_regression(r, X, weights=caps)
    F = pd.DataFrame(rows).T

    # Specific risk is what the factors failed to explain, stock by stock.
    fitted = pd.DataFrame(F.to_numpy() @ X.to_numpy().T,
                          index=F.index, columns=names)
    resid = rets[names] - fitted
    specific_var = resid.var(ddof=1)

    Sigma = factor_model_covariance(F, X, specific_var)
    return {"asof": asof, "X": X, "F": F, "specific_var": specific_var,
            "residuals": resid, "Sigma": Sigma, "returns": rets}


# --------------------------------------------------------------------------- #
# Module 10: judging a model rather than building one
# --------------------------------------------------------------------------- #
def bias_statistic(port_returns: pd.Series, window: int = 104) -> dict:
    """Standardise each realised return by the volatility predicted for it.

        b_t = r_t / sigma_predicted,t

    where sigma is the sample standard deviation of the PREVIOUS `window`
    returns - so every prediction uses only data that existed at the time.

    A calibrated model gives std(b) = 1. Below 1 means risk was overstated,
    above 1 means understated. This one number is how a risk team actually
    judges a model, and it is worth more than any amount of narrative.
    """
    r = pd.Series(port_returns).dropna()
    if len(r) <= window:
        raise ValueError("series shorter than the window")
    pred = r.rolling(window).std(ddof=1).shift(1)      # shift => no look-ahead
    b = (r / pred).dropna()
    return {"bias": float(b.std(ddof=1)), "n": int(len(b)),
            "mean_abs_b": float(b.abs().mean()),
            "outliers_gt_3": int((b.abs() > 3).sum())}


def bias_statistic_ewma(port_returns: pd.Series, lam: float = 0.94,
                        burn_in: int = 104) -> dict:
    """The same test, but predicting with an EWMA rather than a flat window."""
    r = pd.Series(port_returns).dropna()
    var = r.iloc[:burn_in].var(ddof=1)
    preds, actuals = [], []
    for i in range(burn_in, len(r)):
        preds.append(np.sqrt(var))
        actuals.append(r.iloc[i])
        var = lam * var + (1 - lam) * r.iloc[i] ** 2   # update AFTER predicting
    b = np.array(actuals) / np.array(preds)
    return {"bias": float(b.std(ddof=1)), "n": int(len(b)),
            "outliers_gt_3": int((np.abs(b) > 3).sum())}
