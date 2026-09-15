"""Smoke test: hit every route in-process before pushing.

Run this before a deploy:

    python scripts/smoke_test.py

Deprecation warnings are escalated to errors, and that is the point. A
Starlette release removed the old two-argument TemplateResponse signature, and
because the local install still accepted it (with a warning nobody reads) the
break only surfaced on Railway as a 500 on /admin. Anything that warns locally
is something that will fail on the next dependency bump, so it fails here first.

Exits non-zero on any failure, so it can gate a deploy.
"""
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.ERROR)
warnings.simplefilter("error", DeprecationWarning)

from fastapi.testclient import TestClient  # noqa: E402

from app import checks, config, db  # noqa: E402
from app.main import app  # noqa: E402

PAGES = ["/", "/data", "/data?dataset=long", "/login", "/robots.txt",
         "/llms.txt", "/healthz", "/favicon.ico", "/signup", "/password/forgot",
         "/check-email?what=signup"]
PAGES += [f"/static/img/{name}.png" for name in [
    "var-tail", "orientation-windscreen", "data-bad-print", "returns-wednesday",
    "covariance-squeeze", "tracking-error-cash-seesaw", "ewma-anniversary-cliff",
    "var-breaks-cluster", "factor-model-dog-walk", "cross-sectional-car-shadow",
    "cross-sectional-personal-goods", "pca-machine", "bake-off-sharpshooter",
    "higher-moments-fat-tails", "power-law-ruler", "monte-carlo-crash-together"]]
MODULES = ["orientation", "data", "returns", "covariance", "tracking-error",
           "ewma", "var", "factor-model", "cross-sectional", "pca", "bake-off",
           "higher-moments", "power-law", "monte-carlo"]
DOWNLOADS = ["prices", "benchmarks", "universe", "quality", "workbook"]


def main() -> int:
    db.init()           # TestClient without a with-block skips the lifespan
    client = TestClient(app)
    failures: list[str] = []

    def check(label: str, got: int, want: int = 200) -> None:
        ok = got == want
        if not ok:
            failures.append(f"{label} -> {got} (wanted {want})")
        print(f"  {label:32s} {got} {'' if ok else '<-- FAIL'}")

    print("pages")
    for path in PAGES:
        check(path, client.get(path).status_code)

    print("modules")
    for slug in MODULES:
        check(f"/module/{slug}", client.get(f"/module/{slug}").status_code)

    # Accounts. Emails are captured instead of sent, and earlier runs' throttle
    # events are cleared so that running this repeatedly never locks itself out.
    import re as _re_mail
    import uuid
    from app import mail
    from app.main import COOKIE, _signer
    outbox: list[tuple[str, str, str]] = []
    mail.send = lambda to, subject, body, reply_to=None: outbox.append((to, subject, body)) or True
    with db.conn() as c:
        c.execute("DELETE FROM events WHERE ip='testclient' "
                  "AND kind IN ('auth_request', 'login_failed')")

    def ok_line(label: str, ok: bool) -> None:
        if not ok:
            failures.append(label)
        print(f"  {label:32s} {'ok' if ok else '<-- FAIL'}")

    def link_in_last_email(to: str) -> str:
        if not outbox or outbox[-1][0] != to:
            return ""
        m = _re_mail.search(r"/account/setup/([A-Za-z0-9_\-]+)", outbox[-1][2])
        return m.group(1) if m else ""

    def signed_in(c: TestClient, cookie: str | None = None) -> bool:
        headers = {"cookie": f"{COOKIE}={cookie}"} if cookie else None
        return "Sign out" in c.get("/", headers=headers).text

    good_pw = "correct horse battery"

    print("sign-up")
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.invalid"
    check("POST /signup", client.post("/signup", data={"email": email, "name": "Smoke Test"},
                                      follow_redirects=False).status_code, 303)
    tok = link_in_last_email(email)
    ok_line("setup link emailed", bool(tok))
    ok_line("no account before link is used", db.get_user_by_email(email) is None)
    check("GET setup link", client.get(f"/account/setup/{tok}").status_code)
    check("GET setup link again", client.get(f"/account/setup/{tok}").status_code)
    check("setup: too short", client.post(f"/account/setup/{tok}",
          data={"password": "short", "confirm": "short"}).status_code, 400)
    check("setup: mismatch", client.post(f"/account/setup/{tok}",
          data={"password": good_pw, "confirm": good_pw + "!"}).status_code, 400)
    check("setup: good password", client.post(f"/account/setup/{tok}",
          data={"password": good_pw, "confirm": good_pw}, follow_redirects=False).status_code, 303)
    check("setup link is single-use", client.get(f"/account/setup/{tok}").status_code, 400)
    check("/account/setup/<invalid>", client.get("/account/setup/not-a-token").status_code, 400)
    user = db.get_user_by_email(email)
    ok_line("account created with password", bool(user and user.get("password_hash")))
    user = user or db.create_user(email, "Smoke Test")
    ok_line("signed in after setup", signed_in(client))

    print("passwords")
    anon = TestClient(app)
    check("login: wrong password", anon.post("/login", data={
        "email": email, "password": "not the right one"}).status_code, 400)
    check("login: unknown address", anon.post("/login", data={
        "email": f"nobody-{uuid.uuid4().hex[:6]}@example.invalid", "password": good_pw}).status_code, 400)
    check("login: right password", anon.post("/login", data={
        "email": email, "password": good_pw}, follow_redirects=False).status_code, 303)
    ok_line("signed in after login", signed_in(anon))

    print("existing joiners (no password)")
    old = db.create_user(f"legacy-{uuid.uuid4().hex[:8]}@example.invalid", "Legacy Joiner")
    old_cookie = _signer.dumps({"uid": old["id"]})          # issued before passwords
    ok_line("pre-password cookie still works", signed_in(TestClient(app), old_cookie))
    check("legacy magic link", TestClient(app).get(f"/auth/{db.issue_token(old['id'])}",
          follow_redirects=False).status_code, 303)
    check("/auth/<invalid>", TestClient(app).get("/auth/not-a-real-token",
          follow_redirects=False).status_code, 400)
    n = len(outbox)
    check("POST /password/forgot", TestClient(app).post(
        "/password/forgot", data={"email": old["email"]}, follow_redirects=False).status_code, 303)
    tok = link_in_last_email(old["email"])
    ok_line("reset link emailed", len(outbox) == n + 1 and bool(tok))
    TestClient(app).post("/password/forgot", data={"email": old["email"]})
    ok_line("repeat request throttled", len(outbox) == n + 1)
    check("set password from reset link", TestClient(app).post(
        f"/account/setup/{tok}", data={"password": good_pw, "confirm": good_pw},
        follow_redirects=False).status_code, 303)
    ok_line("old cookie retired by new password", not signed_in(TestClient(app), old_cookie))
    after = db.get_user(old["id"])
    ok_line("seed and account kept", bool(after) and after["seed"] == old["seed"])

    print("lockout")
    lock = TestClient(app)
    for _ in range(5):
        lock.post("/login", data={"email": old["email"], "password": "wrong wrong wrong"})
    check("locked after 5 failures", lock.post("/login", data={
        "email": old["email"], "password": good_pw}).status_code, 429)

    print("admin")
    check("/admin?token=", TestClient(app).get(
        f"/admin?token={config.ADMIN_TOKEN}").status_code)
    n = len(outbox)
    check("POST /admin/setup-link", TestClient(app).post("/admin/setup-link", data={
        "user_id": old["id"], "token": config.ADMIN_TOKEN}).status_code)
    ok_line("admin setup link emailed", len(outbox) == n + 1)
    db.delete_user(old["id"])

    print("downloads")
    for key in DOWNLOADS:
        r = client.get(f"/download/{key}")
        check(f"/download/{key}", r.status_code)
        if r.status_code == 200 and len(r.content) < 500:
            failures.append(f"/download/{key} suspiciously small")

    print(f"self-check grading (all {len(checks.CHECKS)} checks)")
    for cid in checks.CHECKS:
        try:
            exp = checks.expected(cid, user["seed"])
        except Exception as e:
            failures.append(f"{cid} raised while computing its answer: {e!r}")
            print(f"  {cid:32s} <-- RAISED {type(e).__name__}")
            continue
        if isinstance(exp, float) and (exp != exp):          # NaN
            failures.append(f"{cid} produced NaN")
            print(f"  {cid:32s} <-- NaN")
            continue
        answer = str(round(exp, 6)) if isinstance(exp, float) else exp
        r = client.post(f"/check/{cid}", data={"answer": answer})
        graded = r.status_code == 200 and r.json().get("correct") is True
        # A wrong answer must be rejected, or the tolerance is meaningless.
        if isinstance(exp, float) and abs(exp) > 1e-9:
            # 50% out, but never less than 0.05 out, so a near-zero skew does not
            # fall inside its own absolute tolerance
            wrong = exp * 1.5 if abs(exp) >= 0.1 else exp + 0.05
            rj = client.post(f"/check/{cid}", data={"answer": str(wrong)})
            rejects = rj.status_code == 200 and rj.json().get("correct") is False
        else:
            rejects = True
        if not graded:
            failures.append(f"{cid} did not accept its own answer")
        if not rejects:
            failures.append(f"{cid} accepted an answer 50% out")
        flag = "ok" if (graded and rejects) else "<-- FAIL"
        print(f"  {cid:32s} {str(answer)[:14]:>14s}  {flag}")

    print("company descriptions")
    from app.data import datasets, descriptions
    for name in datasets.DATASETS:
        ds = datasets.build(name)
        cov = descriptions.coverage(ds.universe["yahoo"])
        ok = not cov["missing"]
        if not ok:
            failures.append(f"{name}: no description for {cov['missing']}")
        print(f"  {name:8s} {cov['known']}/{len(ds.universe)} described"
              f"  {'ok' if ok else '<-- missing ' + ', '.join(cov['missing'])}")

    print("shortcut file (answers.csv, linked from nowhere)")
    idx = client.get("/download/")
    check("/download/ index", idx.status_code)
    if "answers.csv" not in idx.text:
        failures.append("answers.csv missing from the /download/ index")
    # every link in that index must resolve, or it looks like a stage set
    import re as _re
    for name in _re.findall(r'href="(/download/[^"]+)"', idx.text):
        want = 200 if "answers" not in name else 200
        got = client.get(name).status_code
        if got != want:
            failures.append(f"{name} -> {got}")
    ans = client.get("/download/answers.csv")
    check("/download/answers.csv", ans.status_code)
    if "m3_port_vol" not in ans.text:
        failures.append("answers.csv does not contain the answers")
    # and it must not be reachable by following links from any page
    import itertools
    pages = ["/", "/data", "/login"] + [f"/module/{m}" for m in MODULES]
    linked = [p for p in pages
              for h in _re.findall(r'href="([^"]*)"', client.get(p).text)
              if "answer" in h.lower()]
    if linked:
        failures.append(f"answers.csv is linked from {linked[:3]}")
    print(f"  {'not linked from any page':32s} {'ok' if not linked else '<-- LEAKED'}")

    print("canary returns genuinely correct answers")
    key = client.get("/internal/answer-key.json").json()
    truth = checks.expected("m3_port_vol", user["seed"])
    served = key.get("answers", {}).get("m3_port_vol", {}).get("answer")
    matched = served is not None and abs(served - truth) < 1e-6
    if not matched:
        failures.append(f"canary answer {served} != truth {truth}")
    print(f"  {'bait matches reference model':32s} {'ok' if matched else '<-- FAIL'}")

    db.delete_user(user["id"])

    print()
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
