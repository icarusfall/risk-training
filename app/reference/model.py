"""Reference risk-model implementation: the answer key.

Everything here recomputes from the live cache, so answers never go stale when
the data refreshes. Self-checks compare a joiner's number to these within a
relative tolerance - the METHOD is theirs to choose (MMULT, SUMPRODUCT,
pairwise COVARIANCE.S, a pivot table and a prayer). Only the maths must agree.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

# Annualisation: periods per year for the sqrt-time rule.
ANNUALISATION = {"daily": 252, "weekly": 52, "monthly": 12}
# Weekly sampling is Wednesday-to-Wednesday, not Friday-to-Friday. UK market
# holidays cluster on Mondays and Fridays - Good Friday, Easter Monday, May Day,
# the spring and August bank holidays - so a Friday-stamped week is regularly a
# four-day week masquerading as a five-day one. Wednesday is the least
# holiday-prone day of the UK week.
FREQ_RULE = {"daily": None, "weekly": "W-WED", "monthly": "ME"}


# --------------------------------------------------------------------------- #
# returns
# --------------------------------------------------------------------------- #
def resample_prices(px: pd.DataFrame, freq: str) -> pd.DataFrame:
    if freq == "daily":
        return px
    if freq not in FREQ_RULE:
        raise ValueError(f"unknown frequency {freq!r}")
    return px.resample(FREQ_RULE[freq]).last()


def returns(px: pd.DataFrame, freq: str = "daily", log: bool = False) -> pd.DataFrame:
    """Period returns. Simple by default; log optional.

    Note we resample PRICES then difference, rather than compounding daily
    returns - identical result, but it matches what the joiner does in Excel.
    """
    p = resample_prices(px, freq)
    r = np.log(p / p.shift(1)) if log else p.pct_change()
    return r.iloc[1:]


def trim_universe(px: pd.DataFrame, start: str | None = None,
                  min_coverage: float = 0.98) -> pd.DataFrame:
    """Keep the window from `start`, then drop columns that are too gappy.

    This is the 'remove columns where the history isn't long enough' step,
    done explicitly rather than by silently dropping NaNs.
    """
    w = px.loc[start:] if start else px
    keep = w.columns[w.notna().mean() >= min_coverage]
    return w[keep].ffill().dropna(how="any")


# --------------------------------------------------------------------------- #
# covariance
# --------------------------------------------------------------------------- #
def cov_matrix(r: pd.DataFrame, ddof: int = 1) -> pd.DataFrame:
    """Sample covariance, the matrix-algebra way: S = R'R / (T-1) on demeaned R.

    Exactly the MMULT(TRANSPOSE(R), R)/(n-1) the joiner builds in Excel.
    """
    R = r.to_numpy(dtype=float)
    R = R - R.mean(axis=0, keepdims=True)
    S = R.T @ R / (R.shape[0] - ddof)
    return pd.DataFrame(S, index=r.columns, columns=r.columns)


def ewma_weights(n: int, lam: float = 0.94) -> np.ndarray:
    """Normalised RiskMetrics weights, oldest first (so they line up with a
    chronological returns block)."""
    age = np.arange(n - 1, -1, -1)          # oldest observation has the largest age
    w = (1 - lam) * lam ** age
    return w / w.sum()


def half_life(lam: float) -> float:
    return np.log(0.5) / np.log(lam)


def cov_ewma(r: pd.DataFrame, lam: float = 0.94, demean: bool = False) -> pd.DataFrame:
    """EWMA covariance.

    demean=False matches RiskMetrics (means assumed zero), which is the industry
    convention at daily frequency and what we teach.
    """
    R = r.to_numpy(dtype=float)
    if demean:
        R = R - R.mean(axis=0, keepdims=True)
    w = ewma_weights(len(R), lam)
    Rw = R * np.sqrt(w)[:, None]            # scale rows, then the same R'R
    return pd.DataFrame(Rw.T @ Rw, index=r.columns, columns=r.columns)


# --------------------------------------------------------------------------- #
# portfolio risk
# --------------------------------------------------------------------------- #
def portfolio_variance(w: np.ndarray, S: pd.DataFrame | np.ndarray) -> float:
    S = np.asarray(S, dtype=float)
    w = np.asarray(w, dtype=float).reshape(-1)
    return float(w @ S @ w)


def annualise_vol(period_vol: float, freq: str) -> float:
    return float(period_vol * np.sqrt(ANNUALISATION[freq]))


def portfolio_vol(w, S, freq: str | None = None) -> float:
    v = np.sqrt(max(portfolio_variance(w, S), 0.0))
    return annualise_vol(v, freq) if freq else v


def risk_contributions(w, S, freq: str | None = None) -> pd.DataFrame:
    """Marginal and total contribution to risk.

    MCTR_i = (S w)_i / sigma          CTR_i = w_i * MCTR_i      sum(CTR) = sigma
    """
    idx = S.index if isinstance(S, pd.DataFrame) else range(len(w))
    Sm = np.asarray(S, dtype=float)
    wv = np.asarray(w, dtype=float).reshape(-1)
    sig = np.sqrt(max(wv @ Sm @ wv, 1e-300))
    mctr = (Sm @ wv) / sig
    ctr = wv * mctr
    scale = np.sqrt(ANNUALISATION[freq]) if freq else 1.0
    return pd.DataFrame({"weight": wv, "mctr": mctr * scale, "ctr": ctr * scale,
                         "pct_of_risk": ctr / sig}, index=idx)


def tracking_error(wp, wb, S, freq: str | None = None) -> float:
    return portfolio_vol(np.asarray(wp, float) - np.asarray(wb, float), S, freq)


# --------------------------------------------------------------------------- #
# benchmark composite
# --------------------------------------------------------------------------- #
def cap_weights(mcap: pd.DataFrame, cols: list[str], asof=None) -> pd.Series:
    """Cap weights as at a date (default: the latest)."""
    m = mcap[[c for c in cols if c in mcap.columns]].ffill()
    row = m.iloc[-1] if asof is None else m.loc[:asof].iloc[-1]
    return row / row.sum()


def composite_index(px: pd.DataFrame, cols: list[str],
                    weights: pd.Series | None = None) -> pd.Series:
    """Total-return index for a FIXED weight vector, rebalanced each period.

    Deliberately NOT cap-weighted through time. We only know today's shares
    outstanding, and back-projecting them is catastrophically wrong for any
    name that has been heavily diluted: it puts NatWest at 26% of the 2005
    index and Lloyds at 11%, then rides those phantom weights down through the
    GFC, producing a "total return" index that underperforms its own price
    index. Constant shares is a fine approximation for a size EXPOSURE that
    gets z-scored and winsorised; it is useless for index weights, where the
    error compounds.

    Default is equal weight. Pass `weights` for a fixed cap-weighted variant.

    Health warning for the joiner either way: this is built from TODAY'S index
    members, so it inherits survivorship bias. Names that fell out of the
    FTSE 100 - often after doing badly - are simply absent. Use ISF.L when you
    want a benchmark with no survivorship bias in it.
    """
    cols = [c for c in cols if c in px.columns]
    r = px[cols].ffill().pct_change()
    if weights is None:
        idx_ret = r.mean(axis=1)
    else:
        w = weights.reindex(cols).fillna(0.0)
        w = w / w.sum()
        idx_ret = (r * w).sum(axis=1, min_count=1)
    return (1 + idx_ret.fillna(0.0)).cumprod() * 100.0
