"""Central configuration. Everything overridable by environment variable so
Railway can drive it without code changes."""
from __future__ import annotations
import os
from pathlib import Path

def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)

# --- storage -----------------------------------------------------------------
# On Railway, mount a volume at /data and set DATA_DIR=/data
DATA_DIR = Path(_env("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data_cache")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "risk_training.sqlite3"

# --- universe ----------------------------------------------------------------
HISTORY_START = _env("HISTORY_START", "1995-01-01")
WIKI_URL = "https://en.wikipedia.org/wiki/FTSE_100_Index"

# Benchmark series. Deliberately several, because "the index" is not one
# unambiguous thing - and two of these disagree in a way worth discovering.
#
#   ^FTSE   FTSE 100 PRICE index. No dividends. Longest history (1995).
#   CUKX.L  iShares Core FTSE 100 ACC. Dividends reinvested inside the fund, so
#           the price IS total return. Verified: +3.75%/yr over ^FTSE, which is
#           the FTSE 100 yield. This is the one to regress against. From 2010.
#   FTAL.L  SPDR FTSE UK All-Share ACC. Total return, All-Share. From 2012.
#   ISF.L   iShares Core FTSE 100 DIST. Kept ON PURPOSE: Yahoo's "adjusted"
#           series for it does NOT reinvest the dividends, so it tracks the
#           price index to within 0.12%/yr despite looking like a total-return
#           ETF. Module 1 asks the joiner to spot why it and CUKX.L disagree.
#
# Worth keeping in proportion: dividends matter a great deal for RETURNS and
# almost nothing for RISK. Volatility is a second moment, and a smooth ~3.5%/yr
# yield barely touches it - see the comparison in the Module 2 notes. Do not
# let a joiner conclude that a price series makes their vol estimate invalid.
BENCHMARK_TICKERS = {
    "^FTSE": "FTSE 100 Price Index (no dividends)",
    "CUKX.L": "iShares Core FTSE 100 Acc (TOTAL RETURN)",
    "FTAL.L": "SPDR FTSE UK All-Share Acc (TOTAL RETURN)",
    "ISF.L": "iShares Core FTSE 100 Dist (price only - see notes)",
}
TOTAL_RETURN_BENCHMARK = "CUKX.L"
COMPOSITE_CODE = "FTSE100_TR_COMPOSITE"

# --- refresh policy ----------------------------------------------------------
# Serve last-good instantly; refresh in the background when older than this.
STALE_AFTER_HOURS = float(_env("STALE_AFTER_HOURS", "12"))
REFRESH_TIMEOUT_S = float(_env("REFRESH_TIMEOUT_S", "180"))

# --- app ---------------------------------------------------------------------
SECRET_KEY = _env("SECRET_KEY", "dev-only-insecure-key-change-in-production")
BASE_URL = _env("BASE_URL", "http://localhost:8000")
ADMIN_EMAIL = _env("ADMIN_EMAIL", "")
ADMIN_TOKEN = _env("ADMIN_TOKEN", "letmein")

# Outbound email for magic links + canary alerts (Resend). Unset => log to stdout.
RESEND_API_KEY = _env("RESEND_API_KEY", "")
# Resend's sandbox sender works with no domain setup, but ONLY delivers to the
# Resend account owner's own address. Good enough for admin alerts; joiner
# magic links to other domains are rejected, which is why /admin shows the
# link on screen for forwarding. Verify a domain to email joiners directly.
MAIL_FROM = _env("MAIL_FROM", "onboarding@resend.dev")

# Tolerance for marking a self-check answer correct (relative).
CHECK_RTOL = float(_env("CHECK_RTOL", "0.02"))
