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
         "/llms.txt", "/healthz", "/favicon.ico", "/login?sent=1"]
PAGES += [f"/static/img/{name}.png" for name in [
    "var-tail", "orientation-windscreen", "data-bad-print", "returns-wednesday",
    "covariance-squeeze", "tracking-error-cash-seesaw", "ewma-anniversary-cliff",
    "var-breaks-cluster", "factor-model-dog-walk", "cross-sectional-car-shadow",
    "cross-sectional-personal-goods", "pca-machine", "bake-off-sharpshooter"]]
MODULES = ["orientation", "data", "returns", "covariance", "tracking-error",
           "ewma", "var", "factor-model", "cross-sectional", "pca", "bake-off"]
DOWNLOADS = ["prices", "benchmarks", "universe", "quality", "workbook"]


def main() -> int:
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

    # A joiner is needed for the authenticated routes.
    user = db.get_user_by_email("smoke-test@example.invalid") \
        or db.create_user("smoke-test@example.invalid", "Smoke Test")
    token = db.issue_token(user["id"])

    print("auth")
    check("/auth/<valid>", client.get(f"/auth/{token}",
                                      follow_redirects=False).status_code, 303)
    check("/auth/<invalid>", client.get("/auth/not-a-real-token",
                                        follow_redirects=False).status_code, 400)

    print("sign-in requests")
    import uuid
    fresh = db.create_user(f"login-{uuid.uuid4().hex[:8]}@example.invalid", "Login Test")
    stranger = f"stranger-{uuid.uuid4().hex[:8]}@example.invalid"
    before = len(db.recent_events(["login_requested"], limit=1000))
    for label, addr in [("registered", fresh["email"]), ("unregistered", stranger),
                        ("registered, repeated", fresh["email"])]:
        check(f"POST /login {label}", client.post(
            "/login", data={"email": addr}, follow_redirects=False).status_code, 303)
    added = len(db.recent_events(["login_requested"], limit=1000)) - before
    if added != 2:
        failures.append(f"login requests: expected 2 events (repeat throttled), got {added}")
    print(f"  {'repeat request throttled':32s} {'ok' if added == 2 else '<-- FAIL'}")
    db.delete_user(fresh["id"])

    print("admin")
    check("/admin?token=", TestClient(app).get(
        f"/admin?token={config.ADMIN_TOKEN}").status_code)

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
            rj = client.post(f"/check/{cid}", data={"answer": str(exp * 1.5)})
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
