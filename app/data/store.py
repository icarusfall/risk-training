"""Price cache with non-blocking refresh.

Design rule: a joiner NEVER waits for Yahoo. We always serve the last good
snapshot immediately and refresh in a background thread if it's stale. If the
upstream fetch fails, the previous snapshot stays in place and the site keeps
working - the worst case is a slightly older "Data as of" banner.
"""
from __future__ import annotations
import json, logging, threading, time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .. import config
from .industry import to_industry
from .instruments import fetch_instrument_meta, normalise_to_gbp
from .universe import fetch_constituents

log = logging.getLogger(__name__)

PRICES_PARQUET = config.DATA_DIR / "prices.parquet"
UNIVERSE_PARQUET = config.DATA_DIR / "universe.parquet"
MCAP_PARQUET = config.DATA_DIR / "mcap.parquet"
META_JSON = config.DATA_DIR / "meta.json"

_refresh_lock = threading.Lock()
_refreshing = False


# --------------------------------------------------------------------------- #
# metadata
# --------------------------------------------------------------------------- #
def read_meta() -> dict:
    if META_JSON.exists():
        try:
            return json.loads(META_JSON.read_text())
        except Exception:
            log.warning("meta.json unreadable; treating cache as empty")
    return {}


def _write_meta(**kw) -> None:
    meta = read_meta()
    meta.update(kw)
    META_JSON.write_text(json.dumps(meta, indent=2, default=str))


def age_hours() -> float | None:
    ts = read_meta().get("refreshed_at")
    if not ts:
        return None
    try:
        then = datetime.fromisoformat(ts)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - then).total_seconds() / 3600.0
    except Exception:
        return None


def is_stale() -> bool:
    a = age_hours()
    return a is None or a > config.STALE_AFTER_HOURS


def has_data() -> bool:
    return PRICES_PARQUET.exists() and UNIVERSE_PARQUET.exists()


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #
def _download_once(tickers: list[str], start: str) -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(tickers, start=start, auto_adjust=True,
                      progress=False, threads=True)
    if raw is None or raw.empty:
        raise RuntimeError("yfinance returned no data")
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close.dropna(how="all")


def _download(tickers: list[str], start: str, attempts: int = 3) -> pd.DataFrame:
    """Bulk download, then retry stragglers individually.

    Yahoo intermittently drops a name from a bulk request (seen on VOD.L). A
    single transient blip silently removing a stock from the exercise is worse
    than taking a few extra seconds, so we chase the gaps.
    """
    px = _download_once(tickers, start)
    for attempt in range(2, attempts + 1):
        missing = [t for t in tickers if t not in px.columns or px[t].dropna().empty]
        if not missing:
            break
        log.warning("Attempt %d: retrying %d missing ticker(s): %s",
                    attempt, len(missing), missing)
        time.sleep(1.5 * (attempt - 1))          # brief backoff
        try:
            extra = _download_once(missing, start)
        except Exception:
            log.exception("Retry batch failed")
            continue
        for c in extra.columns:
            if not extra[c].dropna().empty:
                px[c] = extra[c]
    return px.dropna(how="all")


def _merge_previous(px: pd.DataFrame) -> pd.DataFrame:
    """Carry forward any column the new fetch lost but the old snapshot had.

    Protects against a degraded refresh quietly shrinking the universe.
    """
    if not PRICES_PARQUET.exists():
        return px
    try:
        old = pd.read_parquet(PRICES_PARQUET)
    except Exception:
        return px
    lost = [c for c in old.columns if c not in px.columns]
    if not lost:
        return px
    log.warning("Carrying forward %d column(s) absent from this fetch: %s", len(lost), lost)
    return px.join(old[lost], how="left")


def refresh(force: bool = False) -> dict:
    """Synchronous refresh. Returns the new metadata dict."""
    global _refreshing
    with _refresh_lock:
        if _refreshing and not force:
            return read_meta()
        _refreshing = True
    t0 = time.time()
    try:
        uni = fetch_constituents()
        uni["industry"] = uni["sector"].map(to_industry)

        tickers = list(uni["yahoo"]) + list(config.BENCHMARK_TICKERS)
        px = _download(tickers, config.HISTORY_START)

        # Drop anything still empty after retries, then restore from last snapshot.
        empty = [c for c in px.columns if px[c].dropna().empty]
        if empty:
            log.warning("No data after retries for: %s", empty)
            px = px.drop(columns=empty)
        px = _merge_previous(px)
        px = px.sort_index(axis=1)

        # Quote currency + shares outstanding, then put everything in GBp so
        # cap weights are comparable and FX is not silently inside a return.
        inst = fetch_instrument_meta([t for t in uni["yahoo"] if t in px.columns])
        px, fx_notes = normalise_to_gbp(px, inst, config.HISTORY_START)
        uni = uni.merge(inst, on="yahoo", how="left")

        # Market cap through time from a constant share count:
        #     cap_t = shares_today * price_t
        # Shares actually drift (buybacks, issuance), so this is an
        # approximation - but it gives a genuinely time-varying size exposure
        # instead of stamping today's cap on 2008, and it is the honest
        # free-data compromise. Documented in the Module 1 notes.
        sh = uni.set_index("yahoo")["shares"]
        stock_cols = [t for t in uni["yahoo"] if t in px.columns and pd.notna(sh.get(t))]
        mcap = px[stock_cols].mul([float(sh[t]) for t in stock_cols], axis=1) / 100.0  # GBp -> GBP
        mcap.to_parquet(MCAP_PARQUET)

        resolved = [t for t in uni["yahoo"] if t in px.columns]
        uni["has_data"] = uni["yahoo"].isin(resolved)

        # Coverage stats drive the "which columns are long enough?" exercise.
        first_obs = {c: px[c].dropna().index.min() for c in px.columns}
        uni["first_date"] = uni["yahoo"].map(
            lambda t: first_obs.get(t).date().isoformat() if first_obs.get(t) is not None else None)
        uni["n_obs"] = uni["yahoo"].map(lambda t: int(px[t].notna().sum()) if t in px.columns else 0)

        px.index.name = "date"
        px.sort_index(inplace=True)
        px.to_parquet(PRICES_PARQUET)
        uni.to_parquet(UNIVERSE_PARQUET, index=False)

        meta = dict(
            refreshed_at=datetime.now(timezone.utc).isoformat(),
            n_stocks=int(uni["has_data"].sum()),
            n_missing=int((~uni["has_data"]).sum()),
            missing=[t for t in uni.loc[~uni["has_data"], "epic"]],
            first_date=str(px.index.min().date()),
            last_date=str(px.index.max().date()),
            n_days=int(len(px)),
            benchmarks=[b for b in config.BENCHMARK_TICKERS if b in px.columns],
            fx_normalised=fx_notes,
            n_with_shares=len(stock_cols),
            fetch_seconds=round(time.time() - t0, 1),
        )
        _write_meta(**meta)
        log.info("Refreshed: %d stocks, %s..%s in %.1fs",
                 meta["n_stocks"], meta["first_date"], meta["last_date"], meta["fetch_seconds"])
        return meta
    finally:
        with _refresh_lock:
            _refreshing = False


def refresh_in_background() -> bool:
    """Kick off a refresh unless one is already running. Returns True if started."""
    global _refreshing
    with _refresh_lock:
        if _refreshing:
            return False
    threading.Thread(target=_safe_refresh, name="price-refresh", daemon=True).start()
    return True


def _safe_refresh() -> None:
    try:
        refresh()
    except Exception:
        # Deliberately swallowed: a failed refresh must never take the site down.
        log.exception("Background refresh failed; keeping previous snapshot")


def ensure_fresh() -> dict:
    """Call on page load. Never blocks if we already have a usable snapshot."""
    if not has_data():
        return refresh()            # cold start: we have no choice but to wait
    if is_stale():
        refresh_in_background()
    return read_meta()


# --------------------------------------------------------------------------- #
# read
# --------------------------------------------------------------------------- #
_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, path: Path, loader):
    mtime = path.stat().st_mtime
    hit = _cache.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    obj = loader(path)
    _cache[key] = (mtime, obj)
    return obj


def prices() -> pd.DataFrame:
    if not has_data():
        refresh()
    return _cached("prices", PRICES_PARQUET, pd.read_parquet)


def universe() -> pd.DataFrame:
    if not has_data():
        refresh()
    return _cached("universe", UNIVERSE_PARQUET, pd.read_parquet)


def market_caps() -> pd.DataFrame:
    """Approximate GBP market cap through time (constant shares outstanding)."""
    if not MCAP_PARQUET.exists():
        refresh()
    return _cached("mcap", MCAP_PARQUET, pd.read_parquet)
