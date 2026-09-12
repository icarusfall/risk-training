"""Per-instrument metadata (shares outstanding, quote currency) and the FX
normalisation needed to put every price series on a common GBp footing.

Three FTSE 100 lines are quoted away from sterling (Compass and IHG in USD,
Metlen in EUR). Left alone they would (a) corrupt cap weights and (b) bake an
unhedged FX return into those stocks' risk. We convert them, and we tell the
joiner we did - it is one of the better data-hygiene lessons in the exercise.
"""
from __future__ import annotations
import logging
import pandas as pd

log = logging.getLogger(__name__)

FX_TICKERS = {"USD": "GBPUSD=X", "EUR": "GBPEUR=X"}


def fetch_instrument_meta(tickers: list[str]) -> pd.DataFrame:
    """DataFrame[yahoo, shares, currency]. ~20s for 100 names."""
    import yfinance as yf
    rows = []
    tk = yf.Tickers(" ".join(tickers))
    for sym, obj in tk.tickers.items():
        shares = currency = None
        try:
            fi = obj.fast_info
            shares, currency = fi.get("shares"), fi.get("currency")
        except Exception:
            log.debug("fast_info failed for %s", sym)
        rows.append({"yahoo": sym, "shares": shares, "currency": currency or "GBp"})
    return pd.DataFrame(rows)


def fetch_fx(currencies: set[str], start: str) -> pd.DataFrame:
    """GBP crosses as 'units of FOREIGN per 1 GBP'."""
    import yfinance as yf
    want = {c: FX_TICKERS[c] for c in currencies if c in FX_TICKERS}
    if not want:
        return pd.DataFrame()
    raw = yf.download(list(want.values()), start=start, auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(list(want.values())[0])
    return raw.rename(columns={v: k for k, v in want.items()})


def normalise_to_gbp(px: pd.DataFrame, meta: pd.DataFrame, start: str) -> tuple[pd.DataFrame, list[dict]]:
    """Convert non-GBp columns into GBp (pence). Returns (prices, conversion notes)."""
    cur = meta.set_index("yahoo")["currency"].to_dict()
    foreign = {t: c for t, c in cur.items()
               if c and c not in ("GBp", "GBX") and t in px.columns}
    if not foreign:
        return px, []

    fx = fetch_fx(set(foreign.values()), start)
    if fx.empty:
        log.warning("FX unavailable; leaving %d foreign-quoted names unconverted", len(foreign))
        return px, []

    # Align to the price calendar. ffill covers holidays; bfill covers dates
    # before the FX series begins (a constant pre-sample rate, which leaves
    # returns as local-currency returns for that early stretch only).
    fx = fx.reindex(px.index).ffill().bfill()

    out, notes = px.copy(), []
    for t, ccy in foreign.items():
        if ccy not in fx.columns:
            continue
        rate = fx[ccy]                      # foreign per GBP
        gbp = out[t] / rate                 # -> GBP units
        if ccy == "GBP":
            continue
        out[t] = gbp * 100.0                # -> pence, matching the GBp names
        notes.append({
            "ticker": t, "currency": ccy, "fx": FX_TICKERS[ccy],
            "fx_from": str(fx[ccy].dropna().index.min().date()),
        })
    log.info("FX-normalised %d name(s) to GBp: %s", len(notes), [n["ticker"] for n in notes])
    return out, notes
