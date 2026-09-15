"""FastAPI application.

Route map:
    /                     dashboard: data freshness, downloads, module list
    /module/{n}           a lesson, plus its self-checks
    /check/{check_id}     POST an answer, get graded
    /data                 what we downloaded, what we cleaned, what we dropped
    /download/{key}       CSVs and the starter workbook
    /login, /signup       email-and-password accounts, set up by emailed link
    /password/forgot      ask for a link to set or reset a password
    /account/...          choose or change a password
    /auth/{tok}           legacy magic links, honoured until they expire
    /admin                joiners, progress, canary events
    plus the bait paths in canary.py
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse,
                               RedirectResponse, Response)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer

import pandas as pd

from . import canary, checks, config, content, db, mail, passwords
from .data import datasets, descriptions, exports, store

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup: create tables and warm the price cache without blocking boot.

    Uses the lifespan protocol rather than @app.on_event, which is deprecated
    and due for removal.
    """
    db.init()
    _configure_yfinance_cache()
    if not store.has_data():
        log.info("Cold start: fetching prices (this takes about 30s)...")
        store.refresh_in_background()
    yield


def _configure_yfinance_cache() -> None:
    """Point yfinance's timezone cache at the data volume.

    By default it writes to ~/.cache/py-yfinance, which on Railway is
    ephemeral and which several download threads race to create - producing a
    stream of "File exists" warnings on every cold start. Putting it on the
    volume silences those and lets the cache survive a redeploy.
    """
    try:
        import yfinance as yf
        cache = config.DATA_DIR / "yf-cache"
        cache.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache))
    except Exception:
        log.warning("Could not relocate the yfinance cache; continuing", exc_info=True)


app = FastAPI(title="FTSE 100 Risk Model Training", docs_url=None, redoc_url=None,
              lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

_signer = URLSafeSerializer(config.SECRET_KEY, salt="session")
COOKIE = "rt_session"
_BASE = urlparse(config.BASE_URL)


@app.middleware("http")
async def canonical_host_and_headers(request: Request, call_next):
    """Send visitors on any other hostname to BASE_URL, and add two cheap
    security headers.

    A single hostname matters for more than tidiness: session cookies belong
    to one host, and setup emails link to BASE_URL, so somebody signed in on
    the Railway name would look signed out on the real one. /healthz is exempt
    because Railway's health check does not come in on the public domain.
    """
    host = (request.headers.get("host") or "").lower()
    if (config.REDIRECT_TO_BASE_URL and _BASE.netloc and host
            and host != _BASE.netloc.lower() and request.url.path != "/healthz"):
        target = config.BASE_URL.rstrip("/") + request.url.path
        if request.url.query:
            target += "?" + request.url.query
        return RedirectResponse(target, status_code=301 if request.method in ("GET", "HEAD") else 308)
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


# --------------------------------------------------------------------------- #
# auth helpers
# --------------------------------------------------------------------------- #
def _session_version(user: dict) -> str:
    """Changes whenever the password does, so setting or changing a password
    signs out every other browser. Empty for an account with no password yet,
    which is what keeps cookies issued before passwords existed working."""
    h = user.get("password_hash") or ""
    return hashlib.sha256(h.encode()).hexdigest()[:16] if h else ""


def _public(user: dict) -> dict:
    """The user as handlers and templates see it: no password hash."""
    out = {k: v for k, v in user.items() if k != "password_hash"}
    out["has_password"] = bool(user.get("password_hash"))
    return out


def current_user(request: Request) -> dict | None:
    raw = request.cookies.get(COOKIE)
    if not raw:
        return None
    try:
        data = _signer.loads(raw)
        uid, sv = int(data["uid"]), str(data.get("sv", ""))
    except (BadSignature, KeyError, TypeError, ValueError, AttributeError):
        return None
    user = db.get_user(uid)
    if not user or not hmac.compare_digest(sv, _session_version(user)):
        return None
    return _public(user)


def require_user(request: Request) -> dict:
    u = current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="sign in first")
    return u


def _set_session(resp: Response, user: dict) -> None:
    """`user` must be the database row, hash included, so the version matches."""
    resp.set_cookie(COOKIE, _signer.dumps({"uid": user["id"], "sv": _session_version(user)}),
                    httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30,
                    secure=config.BASE_URL.startswith("https"))


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")


def _ctx(request: Request, **kw) -> dict:
    """Template context every page gets."""
    user = kw.pop("user", None) or current_user(request)
    meta = store.read_meta()
    return {"request": request, "user": user, "meta": meta,
            "age_hours": store.age_hours(), "stale": store.is_stale(),
            "modules": content.list_modules(), "bait_notice": canary.BAIT_NOTICE,
            "datasets": datasets.DATASETS, "admin_name": config.ADMIN_NAME,
            "signup_enabled": config.SIGNUP_ENABLED,
            "allowed_domains": config.SIGNUP_ALLOWED_DOMAINS, **kw}


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
def _portfolio_view(user: dict, ds: datasets.Dataset) -> dict:
    """Everything the front page needs to show a holding as a company rather
    than as a ticker: name, industry, and a plain-English description."""
    ctx = checks.context_for(int(user["seed"]))
    u = ds.universe.set_index("yahoo")
    rows = []
    for ticker, weight in ctx["w"].items():
        meta = u.loc[ticker] if ticker in u.index else None
        name = str(meta["name"]) if meta is not None else ticker
        industry = str(meta["industry"]) if meta is not None else ""
        bench = float(ctx["wb"].get(ticker, 0.0))
        rows.append({
            "ticker": ticker, "name": name, "industry": industry,
            "gloss": descriptions.gloss(industry),
            "description": descriptions.describe(ticker, name, industry),
            "weight": float(weight), "bench": bench, "active": float(weight) - bench,
            "mcap": float(meta["mcap_gbp_m"]) if meta is not None
            and pd.notna(meta.get("mcap_gbp_m")) else None,
        })
    stock = ctx["stock"]
    smeta = u.loc[stock] if stock in u.index else None
    return {
        "rows": rows,
        "stock": {
            "ticker": stock,
            "name": str(smeta["name"]) if smeta is not None else stock,
            "industry": str(smeta["industry"]) if smeta is not None else "",
            "description": descriptions.describe(
                stock,
                str(smeta["name"]) if smeta is not None else "",
                str(smeta["industry"]) if smeta is not None else ""),
        },
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    store.ensure_fresh()
    user = current_user(request)
    prog = db.progress(user["id"]) if user else {}
    ds = datasets.build(datasets.DEFAULT_DATASET) if store.has_data() else None
    portfolio = _portfolio_view(user, ds) if (user and ds) else None
    return templates.TemplateResponse(request, "index.html", _ctx(
        request, user=user, progress=prog, summary=ds.summary() if ds else None,
        portfolio=portfolio, n_checks=len(checks.CHECKS),
        files=exports.FILES))


@app.get("/module/{slug}", response_class=HTMLResponse)
def module(request: Request, slug: str):
    store.ensure_fresh()
    mod = content.get_module(slug)
    if not mod:
        raise HTTPException(404, "no such module")
    user = current_user(request)
    ctx = checks.context_for(int(user["seed"])) if user else None
    mod_checks = [
        {"check": c, "prompt": checks.prompt_for(c, ctx) if ctx else c.prompt,
         "state": (db.progress(user["id"]).get(c.id) if user else None)}
        for c in checks.checks_for_module(mod["number"])
    ]
    return templates.TemplateResponse(request, "module.html", _ctx(
        request, user=user, mod=mod, mod_checks=mod_checks, portfolio=ctx))


@app.post("/check/{check_id}")
def submit_check(request: Request, check_id: str, answer: str = Form(...),
                 user: dict = Depends(require_user)):
    if check_id not in checks.CHECKS:
        raise HTTPException(404, "no such check")
    result = checks.grade(check_id, answer, int(user["seed"]))
    db.record_attempt(user["id"], check_id, answer, result["expected"],
                      result["correct"], result.get("rel_error"))
    if result["correct"]:
        canary.maybe_flag_cadence(user)
    ck = checks.CHECKS[check_id]
    payload = {"correct": result["correct"], "hint": ck.hint}
    if result["correct"]:
        payload["expected"] = result["expected"]
    elif result.get("rel_error") is not None:
        # Directional nudge only - never the number.
        payload["direction"] = ("too high" if float(result["submitted"]) > result["expected"]
                                else "too low")
        payload["close"] = bool(result["rel_error"] < 0.10)
    return JSONResponse(payload)


@app.get("/data", response_class=HTMLResponse)
def data_page(request: Request, dataset: str = datasets.DEFAULT_DATASET):
    store.ensure_fresh()
    if dataset not in datasets.DATASETS:
        dataset = datasets.DEFAULT_DATASET
    ds = datasets.build(dataset)
    return templates.TemplateResponse(request, "data.html", _ctx(
        request, summary=ds.summary(), ds=ds, selected=dataset,
        universe=ds.universe.to_dict("records"),
        quality=ds.quality_report, files=exports.FILES))


def _resolve_download(key: str) -> str | None:
    """Accept either an export key ("quality") or its filename ("cleaning-log.csv").

    The directory index at /download/ lists real filenames, so those have to
    resolve - a listing full of dead links would look like a stage set.
    """
    if key in exports.FILES:
        return key
    for k, (base, ext, *_rest) in exports.FILES.items():
        if key == f"{base}.{ext}":
            return k
    return None


@app.get("/download/")
@app.get("/downloads/")
def download_index():
    """A bare directory index. Linked from nowhere.

    This is how answers.csv is meant to be found: by someone editing the URL to
    see what is in the folder. See canary.py for why that is a signal worth
    having, and why it is a friendlier one than the hidden bait paths.
    """
    return HTMLResponse(canary.directory_listing())


@app.get("/download/{key}")
def download(key: str, request: Request, dataset: str = datasets.DEFAULT_DATASET):
    if key in canary.SHORTCUT_KEYS:
        user = current_user(request)
        canary.trip_shortcut(user, client_ip(request),
                             request.headers.get("user-agent"))
        if not user:
            return PlainTextResponse(
                "Sign in first - the answers are personalised to your portfolio.\n",
                status_code=401)
        return PlainTextResponse(
            canary.answers_csv(user), media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="answers.csv"'})

    resolved = _resolve_download(key)
    if resolved is None:
        raise HTTPException(404, "no such file")
    key = resolved
    store.ensure_fresh()
    ds = datasets.build(dataset if dataset in datasets.DATASETS else datasets.DEFAULT_DATASET)
    _, _, fn, _ = exports.FILES[key]
    t0 = time.time()
    blob = fn(ds)
    user = current_user(request)
    db.log_event("download", user_id=(user or {}).get("id"),
                 detail={"file": key, "dataset": ds.name, "bytes": len(blob)},
                 ip=client_ip(request), user_agent=request.headers.get("user-agent"),
                 path=str(request.url.path))
    log.info("Served %s (%.0f KB) in %.1fs", key, len(blob) / 1024, time.time() - t0)
    media = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
             if key == "workbook" else "text/csv")
    return Response(blob, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{exports.filename(key, ds)}"'})


# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #
# How long each kind of emailed link works for, in hours.
SIGNUP_HOURS = 48           # someone signing themselves up
INVITE_HOURS = 24 * 7       # the admin setting someone up, or moving a joiner onto passwords
RESET_HOURS = 3             # a forgotten password

# Throttles, all counted from the events table, so they survive a restart and
# need nothing extra running.
EMAIL_COOLDOWN_MIN = 5      # at most one emailed link per address in this window
EMAILS_PER_IP_PER_HOUR = 10
LOGIN_LOCK_MIN = 15
LOGIN_FAILS_PER_EMAIL = 5
LOGIN_FAILS_PER_IP = 30


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()[:254]


def _looks_like_email(email: str) -> bool:
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain and " " not in email


def _setup_url(token: str) -> str:
    return f"{config.BASE_URL}/account/setup/{token}"


def _may_email(email: str, ip: str) -> bool:
    """One link per address every few minutes, and a ceiling per IP, so the
    forms cannot be used to fill somebody's inbox."""
    if db.count_events(["auth_request"], EMAIL_COOLDOWN_MIN, email=email):
        return False
    if ip and db.count_events(["auth_request"], 60, ip=ip) >= EMAILS_PER_IP_PER_HOUR:
        return False
    return True


def _login_locked(email: str, ip: str) -> bool:
    if db.count_events(["login_failed"], LOGIN_LOCK_MIN, email=email) >= LOGIN_FAILS_PER_EMAIL:
        return True
    return bool(ip) and db.count_events(["login_failed"], LOGIN_LOCK_MIN, ip=ip) >= LOGIN_FAILS_PER_IP


def _sign_in(request: Request, user: dict, to: str = "/") -> RedirectResponse:
    resp = RedirectResponse(to, status_code=303)
    _set_session(resp, user)
    db.log_event("login", user_id=user["id"], ip=client_ip(request),
                 user_agent=request.headers.get("user-agent"))
    return resp


def _private(resp: Response) -> Response:
    """For pages whose URL carries a token: keep it out of Referer headers and caches."""
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", _ctx(request))


@app.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    email, ip = _norm_email(email), client_ip(request)

    def fail(message: str, status: int):
        return templates.TemplateResponse(request, "login.html",
                                          _ctx(request, error=message, email=email),
                                          status_code=status)

    if _login_locked(email, ip):
        return fail(f"Too many attempts. Wait {LOGIN_LOCK_MIN} minutes, or set a new "
                    "password with the link below.", 429)
    user = db.get_user_by_email(email)
    if user and user.get("password_hash") and len(password) <= passwords.MAX_LENGTH:
        ok = passwords.verify_password(password, user["password_hash"])
    else:
        passwords.burn_time(password)       # same delay whether or not the account exists
        ok = False
    if not ok:
        db.log_event("login_failed", user_id=(user or {}).get("id"), detail={"email": email},
                     ip=ip, user_agent=request.headers.get("user-agent"))
        return fail("That email and password do not match. If you used the site before "
                    "it had passwords, use the link below to set one.", 400)
    return _sign_in(request, user)


@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return templates.TemplateResponse(request, "signup.html", _ctx(request))


@app.post("/signup")
def signup_submit(request: Request, email: str = Form(...), name: str = Form("")):
    """Start an account. Nothing is created until the emailed link is used, so
    an address typed by mistake, or by somebody else, leaves no account behind."""
    email, ip, name = _norm_email(email), client_ip(request), name.strip()[:100]

    def form_error(message: str, status: int = 400):
        return templates.TemplateResponse(request, "signup.html",
                                          _ctx(request, error=message, email=email, name=name),
                                          status_code=status)

    if not config.SIGNUP_ENABLED:
        return form_error(f"Sign-up is closed at the moment. Ask {config.ADMIN_NAME} to add you.", 403)
    if not _looks_like_email(email):
        return form_error("That does not look like an email address.")
    if config.SIGNUP_ALLOWED_DOMAINS and email.rpartition("@")[2] not in config.SIGNUP_ALLOWED_DOMAINS:
        return form_error("Sign-up is open to addresses at "
                          + ", ".join(config.SIGNUP_ALLOWED_DOMAINS) + " only.")
    if _may_email(email, ip):
        db.log_event("auth_request", detail={"email": email, "purpose": "signup"},
                     ip=ip, user_agent=request.headers.get("user-agent"))
        user = db.get_user_by_email(email)
        if user:
            # Already registered: send a way back in rather than an error, so
            # the form does not reveal who has an account.
            tok = db.issue_auth_token("reset", email, user["name"], user["id"], RESET_HOURS)
            mail.send_setup_link(email, user["name"], _setup_url(tok), "existing", RESET_HOURS)
        else:
            tok = db.issue_auth_token("signup", email, name, None, SIGNUP_HOURS)
            mail.send_setup_link(email, name, _setup_url(tok), "signup", SIGNUP_HOURS)
    return RedirectResponse("/check-email?what=signup", status_code=303)


@app.get("/password/forgot", response_class=HTMLResponse)
def forgot_form(request: Request):
    return templates.TemplateResponse(request, "forgot.html", _ctx(request))


@app.post("/password/forgot")
def forgot_submit(request: Request, email: str = Form(...)):
    """Also the way in for joiners who predate passwords. Same response whether
    or not the address has an account."""
    email, ip = _norm_email(email), client_ip(request)
    if _looks_like_email(email) and _may_email(email, ip):
        db.log_event("auth_request", detail={"email": email, "purpose": "reset"},
                     ip=ip, user_agent=request.headers.get("user-agent"))
        user = db.get_user_by_email(email)
        if user:
            tok = db.issue_auth_token("reset", email, user["name"], user["id"], RESET_HOURS)
            mail.send_setup_link(email, user["name"], _setup_url(tok), "reset", RESET_HOURS)
    return RedirectResponse("/check-email?what=reset", status_code=303)


@app.get("/check-email", response_class=HTMLResponse)
def check_email(request: Request, what: str = "reset"):
    return templates.TemplateResponse(request, "check_email.html", _ctx(request, what=what))


def _setup_page(request: Request, row: dict | None, token: str, status: int = 200, **kw):
    ctx = _ctx(request, mode="setup", action=f"/account/setup/{token}",
               email=(row or {}).get("email", ""), expired=row is None, **kw)
    return _private(templates.TemplateResponse(request, "set_password.html", ctx,
                                               status_code=status))


@app.get("/account/setup/{token}", response_class=HTMLResponse)
def setup_form(request: Request, token: str):
    """Show the form without using the link up. Corporate mail filters open
    links to scan them, and a link that died on first view would be dead before
    the joiner ever clicked it."""
    row = db.get_auth_token(token)
    return _setup_page(request, row, token, status=200 if row else 400)


@app.post("/account/setup/{token}")
def setup_submit(request: Request, token: str, password: str = Form(...),
                 confirm: str = Form(...)):
    row = db.get_auth_token(token)
    if not row:
        return _setup_page(request, None, token, status=400)
    problem = passwords.problem_with(password, row["email"])
    if not problem and password != confirm:
        problem = "The two passwords do not match."
    if problem:
        return _setup_page(request, row, token, status=400, error=problem)

    user = db.get_user(row["user_id"]) if row["user_id"] else db.get_user_by_email(row["email"])
    created = False
    if not user:
        if row["purpose"] != "signup":      # the account was deleted after the link went out
            return _setup_page(request, None, token, status=400)
        user = db.create_user(row["email"], row["name"])
        created = True
    user = db.set_password(user["id"], passwords.hash_password(password))
    db.consume_auth_tokens(row["email"])
    db.log_event("password_set", user_id=user["id"],
                 detail={"via": row["purpose"], "new_account": created},
                 ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    if created:
        mail.send_new_signup_to_admin(user["email"], user["name"])
    return _private(_sign_in(request, user))


def _password_page(request: Request, user: dict, status: int = 200, **kw):
    return templates.TemplateResponse(request, "set_password.html", _ctx(
        request, user=user, mode="change", action="/account/password",
        email=user["email"], needs_current=user["has_password"], **kw), status_code=status)


@app.get("/account/password", response_class=HTMLResponse)
def account_password_form(request: Request, welcome: str = "", done: str = ""):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _password_page(request, user, welcome=welcome, done=done)


@app.post("/account/password")
def account_password_submit(request: Request, password: str = Form(...),
                            confirm: str = Form(...), current_password: str = Form("")):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    raw = db.get_user(user["id"])
    if raw.get("password_hash") and not passwords.verify_password(current_password,
                                                                  raw["password_hash"]):
        return _password_page(request, user, 400, error="Your current password is not right.")
    problem = passwords.problem_with(password, raw["email"])
    if not problem and password != confirm:
        problem = "The two passwords do not match."
    if problem:
        return _password_page(request, user, 400, error=problem)
    raw = db.set_password(raw["id"], passwords.hash_password(password))
    db.consume_auth_tokens(raw["email"])
    db.log_event("password_set", user_id=raw["id"], detail={"via": "account"},
                 ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    resp = RedirectResponse("/account/password?done=1", status_code=303)
    _set_session(resp, raw)
    return resp


@app.get("/auth/{token}")
def legacy_link(request: Request, token: str):
    """Sign-in links from before passwords, honoured until they expire. They
    lead straight to choosing a password."""
    user = db.redeem_token(token)
    if not user:
        return templates.TemplateResponse(request, "login.html", _ctx(
            request, error="That sign-in link has expired. The site now uses passwords: "
                           "use the link below to set yours."), status_code=400)
    return _sign_in(request, user,
                    "/" if user.get("password_hash") else "/account/password?welcome=1")


@app.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp


# --------------------------------------------------------------------------- #
# machine-facing surface  (see canary.py)
# --------------------------------------------------------------------------- #
@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return canary.ROBOTS_TXT


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms():
    return canary.LLMS_TXT


def _bait(request: Request, path: str):
    user = current_user(request)
    canary.trip(path, user, client_ip(request), request.headers.get("user-agent"))
    if not user:
        return JSONResponse({"error": "sign in to retrieve your personalised answer key"},
                            status_code=401)
    return canary.answer_key(user)


@app.get("/internal/answer-key.json")
def bait_1(request: Request):
    return _bait(request, "/internal/answer-key.json")


@app.get("/internal/solutions.json")
def bait_2(request: Request):
    return _bait(request, "/internal/solutions.json")


@app.get("/.well-known/model-answers.json")
def bait_3(request: Request):
    return _bait(request, "/.well-known/model-answers.json")


@app.get("/solutions/answers.csv")
def bait_csv(request: Request):
    user = current_user(request)
    canary.trip("/solutions/answers.csv", user, client_ip(request),
                request.headers.get("user-agent"))
    if not user:
        return PlainTextResponse("sign in first\n", status_code=401)
    key = canary.answer_key(user)
    rows = ["check_id,question,answer"]
    for cid, rec in key["answers"].items():
        q = str(rec["question"]).replace('"', "'")
        rows.append(f'{cid},"{q}",{rec["answer"]}')
    return PlainTextResponse("\n".join(rows) + "\n", media_type="text/csv")


# --------------------------------------------------------------------------- #
# admin
# --------------------------------------------------------------------------- #
def require_admin(request: Request, token: str = "") -> bool:
    u = current_user(request)
    if u and u.get("is_admin"):
        return True
    if token and token == config.ADMIN_TOKEN:
        return True
    raise HTTPException(403, "admin only")


def _admin_page(request: Request, token: str, **extra):
    """Render /admin. Shared so POST handlers can show a result without a
    redirect - a magic-link token has no business sitting in the URL bar or in
    browser history."""
    users = []
    for raw in db.list_users():
        u = _public(raw)
        p = db.progress(u["id"])
        u["solved"] = sum(1 for v in p.values() if v["solved"])
        u["total"] = len(checks.CHECKS)
        users.append(u)
    return templates.TemplateResponse(request, "admin.html", _ctx(
        request, users=users, token=token,
        n_without_password=sum(1 for u in users if not u["has_password"]),
        events=db.recent_events(["canary", "shortcut", "cadence"], limit=60),
        activity=db.recent_events(["login", "download", "password_set"], limit=40),
        base_url=config.BASE_URL, **extra))


def _invite(user: dict) -> dict:
    """Email a seven-day link to choose a password, and hand the link back so
    it can be passed on by hand if the email does not arrive."""
    tok = db.issue_auth_token("invite", user["email"], user["name"], user["id"], INVITE_HOURS)
    url = _setup_url(tok)
    sent = mail.send_setup_link(user["email"], user["name"], url, "invite", INVITE_HOURS)
    db.log_event("invite_sent", user_id=user["id"], detail={"email": user["email"], "sent": sent})
    return {"email": user["email"], "name": user["name"], "url": url, "emailed": sent,
            "days": INVITE_HOURS // 24}


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, token: str = ""):
    require_admin(request, token)
    return _admin_page(request, token)


@app.post("/admin/users")
def admin_add(request: Request, email: str = Form(...), name: str = Form(""),
              token: str = Form("")):
    require_admin(request, token)
    user = db.create_user(email, name)
    return _admin_page(request, token, new_link=_invite(user))


@app.post("/admin/setup-link")
def admin_setup_link(request: Request, user_id: int = Form(...), token: str = Form("")):
    """Send one joiner a fresh link to choose a password."""
    require_admin(request, token)
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(404, "no such joiner")
    return _admin_page(request, token, new_link=_invite(user))


@app.post("/admin/invite-all")
def admin_invite_all(request: Request, token: str = Form("")):
    """Email a setup link to every account that has no password yet: the way
    to move joiners from before passwords across in one go."""
    require_admin(request, token)
    results = [_invite(u) for u in db.users_without_password()]
    return _admin_page(request, token, invite_summary={
        "sent": [r["email"] for r in results if r["emailed"]],
        "failed": [r["email"] for r in results if not r["emailed"]],
        "days": INVITE_HOURS // 24})


@app.post("/admin/refresh")
def admin_refresh(request: Request, token: str = Form("")):
    require_admin(request, token)
    store.refresh_in_background()
    return RedirectResponse(f"/admin?token={token}", status_code=303)


@app.get("/favicon.ico")
def favicon():
    """Browsers ask for this regardless of the <link rel=icon> data URI in the
    template, and an unanswered request is a 404 in every log."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<circle cx='50' cy='50' r='42' fill='%23C7BBDD'/>"
           "<circle cx='38' cy='40' r='16' fill='%23E9B8BC'/></svg>")
    return Response(svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok" if store.has_data() else "warming"
