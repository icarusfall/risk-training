"""Fetch the current FTSE 100 constituent list (with ICB sector) from Wikipedia.

Sector matters: it gives us free industry dummies for the cross-sectional
factor model, without paying for a classification feed.
"""
from __future__ import annotations
import io, logging, re
import pandas as pd
import requests
from .. import config

log = logging.getLogger(__name__)
_HEADERS = {"User-Agent": "Mozilla/5.0 (risk-training; educational use)"}


def to_yahoo(epic: str) -> str:
    """LSE EPIC -> Yahoo symbol.

    Yahoo writes LSE lines as '<EPIC>.L', but uses '-' where the EPIC has a dot
    and drops a trailing dot entirely:
        III   -> III.L
        BT.A  -> BT-A.L
        RR.   -> RR.L
    """
    t = str(epic).strip().upper()
    t = re.sub(r"\.$", "", t)          # trailing dot is cosmetic (RR. -> RR)
    t = t.replace(".", "-")            # internal dot becomes a hyphen (BT.A -> BT-A)
    return f"{t}.L"


def fetch_constituents() -> pd.DataFrame:
    """Returns DataFrame[epic, yahoo, name, sector]. Raises on failure."""
    r = requests.get(config.WIKI_URL, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    tables = pd.read_html(io.StringIO(r.text))

    for t in tables:
        cols = [str(c) for c in t.columns]
        has_ticker = any("icker" in c or "EPIC" in c for c in cols)
        if has_ticker and len(t) >= 90:
            df = t.copy()
            df.columns = [str(c) for c in df.columns]
            tick = next(c for c in df.columns if "icker" in c or "EPIC" in c)
            name = next((c for c in df.columns if "ompany" in c), df.columns[0])
            sect = next((c for c in df.columns if "sector" in c.lower()
                         or "classification" in c.lower()), None)
            out = pd.DataFrame({
                "epic": df[tick].astype(str).str.strip().str.upper(),
                "name": df[name].astype(str).str.strip(),
                # Wikipedia is inconsistent about capitalisation ("Financial services"
                # vs "Financial Services") - title-case so dummies don't split.
                "sector": (df[sect].astype(str).str.replace(r"\[.*?\]", "", regex=True)
                           .str.strip().str.title() if sect else "Unclassified"),
            })
            out["yahoo"] = out["epic"].map(to_yahoo)
            out = out.drop_duplicates("yahoo").reset_index(drop=True)
            log.info("Fetched %d constituents, %d sectors", len(out), out["sector"].nunique())
            return out[["epic", "yahoo", "name", "sector"]]

    raise RuntimeError("Could not locate the constituents table on the Wikipedia page")
