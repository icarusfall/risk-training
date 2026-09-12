"""FastAPI application.

Route map:
    /                     dashboard: data freshness, downloads, module list
    /module/{n}           a lesson, plus its self-checks
    /check/{check_id}     POST an answer, get graded
    /data                 what we downloaded, what we cleaned, what we dropped
    /download/{key}       CSVs and the starter workbook
    /login, /auth/{tok}   passwordless sign-in
    /admin                joiners, progress, canary events
    plus the bait paths in canary.py
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse,
                               RedirectResponse, Response)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer

from . import canary, checks, config, content, db, mail
from .data import datasets, exports, store

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
app = FastAPI(title="FTSE 100 Risk Model Training", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

_signer = URLSafeSerializer(config.SECRET_KEY, salt="session")
COOKIE = "rt_session"


@app.on_event("startup")
def _startup() -> None:
    db.init()
    if not store.has_data():
        log.info("Cold start: fetching prices (this takes about 30s)...")
        store.refresh_in_background()


# --------------------------------------------------------------------------- #
# auth helpers
# --------------------------------------------------------------------------- #
def current_user(request: Request) -> dict | None:
    raw = request.cookies.get(COOKIE)
    if not raw:
        return None
    try:
        uid = _signer.loads(raw)["uid"]
    except (BadSignature, KeyError, TypeError):
        return None
    return db.get_user(int(uid))


def require_user(request: Request) -> dict:
    u = current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="sign in first")
    return u


def _set_session(resp: Response, user: dict) -> None:
    resp.set_cookie(COOKIE, _signer.dumps({"uid": user["id"]}),
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
            "datasets": datasets.DATASETS, **kw}


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    store.ensure_fresh()
    user = current_user(request)
    prog = db.progress(user["id"]) if user else {}
    ds = datasets.build(datasets.DEFAULT_DATASET) if store.has_data() else None
    portfolio = None
    if user and ds:
        ctx = checks.context_for(int(user["seed"]))
        portfolio = {"weights": ctx["w"], "stock": ctx["stock"],
                     "bench": ctx["wb"]}
    return templates.TemplateResponse("index.html", _ctx(
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
    return templates.TemplateResponse("module.html", _ctx(
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
    return templates.TemplateResponse("data.html", _ctx(
        request, summary=ds.summary(), ds=ds, selected=dataset,
        universe=ds.universe.to_dict("records"),
        quality=ds.quality_report, files=exports.FILES))


@app.get("/download/{key}")
def download(key: str, request: Request, dataset: str = datasets.DEFAULT_DATASET):
    if key not in exports.FILES:
        raise HTTPException(404, "no such file")
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
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, sent: str = ""):
    return templates.TemplateResponse("login.html", _ctx(request, sent=sent))


@app.post("/login")
def login_submit(request: Request, email: str = Form(...)):
    user = db.get_user_by_email(email)
    if user:
        token = db.issue_token(user["id"])
        url = f"{config.BASE_URL}/auth/{token}"
        mail.send_magic_link(user["email"], user["name"], url)
        db.log_event("login_requested", user_id=user["id"], ip=client_ip(request),
                     user_agent=request.headers.get("user-agent"))
    # Same response either way, so the form cannot be used to enumerate joiners.
    return RedirectResponse("/login?sent=1", status_code=303)


@app.get("/auth/{token}")
def auth(request: Request, token: str):
    user = db.redeem_token(token)
    if not user:
        return templates.TemplateResponse("login.html",
                                          _ctx(request, error="That link has expired. Ask for another."),
                                          status_code=400)
    resp = RedirectResponse("/", status_code=303)
    _set_session(resp, user)
    db.log_event("login", user_id=user["id"], ip=client_ip(request),
                 user_agent=request.headers.get("user-agent"))
    return resp


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


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, token: str = ""):
    require_admin(request, token)
    users = db.list_users()
    for u in users:
        p = db.progress(u["id"])
        u["solved"] = sum(1 for v in p.values() if v["solved"])
        u["total"] = len(checks.CHECKS)
    return templates.TemplateResponse("admin.html", _ctx(
        request, users=users, token=token,
        events=db.recent_events(["canary", "cadence"], limit=60),
        activity=db.recent_events(["login", "download"], limit=40),
        base_url=config.BASE_URL))


@app.post("/admin/users")
def admin_add(request: Request, email: str = Form(...), name: str = Form(""),
              token: str = Form("")):
    require_admin(request, token)
    user = db.create_user(email, name)
    link = f"{config.BASE_URL}/auth/{db.issue_token(user['id'])}"
    sent = mail.send_magic_link(user["email"], user["name"], link)
    if not sent:
        log.warning("Magic link for %s: %s", user["email"], link)
    return RedirectResponse(f"/admin?token={token}", status_code=303)


@app.post("/admin/refresh")
def admin_refresh(request: Request, token: str = Form("")):
    require_admin(request, token)
    store.refresh_in_background()
    return RedirectResponse(f"/admin?token={token}", status_code=303)


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok" if store.has_data() else "warming"
