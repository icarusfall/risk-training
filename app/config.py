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

def _flag(key: str, default: str) -> bool:
    return _env(key, default).strip().lower() not in ("0", "false", "no", "off", "")


# How the site refers to the person who runs the programme.
ADMIN_NAME = _env("ADMIN_NAME", "Charlie")

# --- accounts ----------------------------------------------------------------
# Anyone can sign up unless this is switched off; they still have to receive
# the emailed link before an account exists.
SIGNUP_ENABLED = _flag("SIGNUP_ENABLED", "1")
# Optional comma-separated list, e.g. "lgim.com,lgimamericas.com". Blank means
# any address may sign up.
SIGNUP_ALLOWED_DOMAINS = [d.strip().lower().lstrip("@")
                          for d in _env("SIGNUP_ALLOWED_DOMAINS", "").split(",") if d.strip()]
# Redirect every other hostname (the *.up.railway.app one) to BASE_URL's host.
# Session cookies belong to one hostname, so without this somebody signed in on
# one name looks signed out on the other.
REDIRECT_TO_BASE_URL = _flag("REDIRECT_TO_BASE_URL", "0")

# --- email (Resend) ----------------------------------------------------------
# Unset => messages, including setup links, are written to the log instead.
RESEND_API_KEY = _env("RESEND_API_KEY", "")
# Must be an address on a domain verified in Resend, or Resend will only
# deliver to the account owner. e.g. "Risk Model Training <hello@charliesrisk101.com>"
MAIL_FROM = _env("MAIL_FROM", "onboarding@resend.dev")
# Where replies to site emails go.
MAIL_REPLY_TO = _env("MAIL_REPLY_TO", ADMIN_EMAIL)

# Tolerance for marking a self-check answer correct (relative).
CHECK_RTOL = float(_env("CHECK_RTOL", "0.02"))
