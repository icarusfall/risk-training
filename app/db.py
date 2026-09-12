"""SQLite persistence: joiners, magic-link tokens, attempts and events.

Small enough to keep in one file and one connection-per-call. On Railway this
lives on the mounted volume alongside the price cache.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    seed        INTEGER NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_tokens (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL,
    used_at    TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    check_id   TEXT NOT NULL,
    submitted  TEXT NOT NULL,
    expected   TEXT,
    correct    INTEGER NOT NULL,
    rel_error  REAL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id),
    kind       TEXT NOT NULL,
    detail     TEXT,
    ip         TEXT,
    user_agent TEXT,
    path       TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_attempts_user ON attempts(user_id, check_id);
CREATE INDEX IF NOT EXISTS ix_events_kind ON events(kind, created_at);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
def create_user(email: str, name: str = "", is_admin: bool = False) -> dict:
    """Create a joiner, or return the existing one.

    Whoever is named in ADMIN_EMAIL is promoted automatically. On a fresh
    deployment the database is empty, so the only way in is /admin?token=...;
    without this, adding yourself through that form would create an ordinary
    account with no Admin link and no obvious way to fix it.
    """
    email = email.strip().lower()
    if config.ADMIN_EMAIL and email == config.ADMIN_EMAIL.strip().lower():
        is_admin = True
    with conn() as c:
        existing = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            if is_admin and not existing["is_admin"]:
                c.execute("UPDATE users SET is_admin=1 WHERE id=?", (existing["id"],))
                return dict(c.execute("SELECT * FROM users WHERE id=?",
                                      (existing["id"],)).fetchone())
            return dict(existing)
        # Seed drives that joiner's personal test portfolio, so two people
        # cannot simply copy each other's answers.
        c.execute("INSERT INTO users (email, name, seed, is_admin, created_at) VALUES (?,?,?,?,?)",
                  (email, name, secrets.randbelow(2**31), int(is_admin), now()))
        return dict(c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())


def get_user(user_id: int) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(r) if r else None


def get_user_by_email(email: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        return dict(r) if r else None


def list_users() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users ORDER BY created_at DESC")]


def delete_user(user_id: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM attempts WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM login_tokens WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM users WHERE id=?", (user_id,))


# --------------------------------------------------------------------------- #
# magic links
# --------------------------------------------------------------------------- #
def issue_token(user_id: int, hours: int = 72) -> str:
    tok = secrets.token_urlsafe(32)
    exp = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    with conn() as c:
        c.execute("INSERT INTO login_tokens (token, user_id, expires_at) VALUES (?,?,?)",
                  (tok, user_id, exp))
    return tok


def redeem_token(token: str) -> dict | None:
    """Single-use within its window. Returns the user, or None."""
    with conn() as c:
        r = c.execute("SELECT * FROM login_tokens WHERE token=?", (token,)).fetchone()
        if not r:
            return None
        if datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc):
            return None
        c.execute("UPDATE login_tokens SET used_at=? WHERE token=?", (now(), token))
        u = c.execute("SELECT * FROM users WHERE id=?", (r["user_id"],)).fetchone()
        return dict(u) if u else None


# --------------------------------------------------------------------------- #
# attempts
# --------------------------------------------------------------------------- #
def record_attempt(user_id: int, check_id: str, submitted, expected,
                   correct: bool, rel_error: float | None) -> None:
    with conn() as c:
        c.execute("""INSERT INTO attempts
                     (user_id, check_id, submitted, expected, correct, rel_error, created_at)
                     VALUES (?,?,?,?,?,?,?)""",
                  (user_id, check_id, json.dumps(submitted), json.dumps(expected),
                   int(correct), rel_error, now()))


def attempts_for(user_id: int, check_id: str | None = None) -> list[dict]:
    q = "SELECT * FROM attempts WHERE user_id=?"
    args: list = [user_id]
    if check_id:
        q += " AND check_id=?"
        args.append(check_id)
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY created_at", args)]


def progress(user_id: int) -> dict[str, dict]:
    """Per-check summary: solved, attempts, first-time-right."""
    out: dict[str, dict] = {}
    for a in attempts_for(user_id):
        p = out.setdefault(a["check_id"], {"attempts": 0, "solved": False, "first_try": False})
        p["attempts"] += 1
        if a["correct"] and not p["solved"]:
            p["solved"] = True
            p["first_try"] = p["attempts"] == 1
    return out


# --------------------------------------------------------------------------- #
# events
# --------------------------------------------------------------------------- #
def log_event(kind: str, user_id: int | None = None, detail: dict | None = None,
              ip: str | None = None, user_agent: str | None = None,
              path: str | None = None) -> int:
    with conn() as c:
        cur = c.execute("""INSERT INTO events (user_id, kind, detail, ip, user_agent, path, created_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        (user_id, kind, json.dumps(detail or {}), ip, user_agent, path, now()))
        return int(cur.lastrowid)


def recent_events(kinds: list[str] | None = None, limit: int = 200) -> list[dict]:
    q = "SELECT e.*, u.email, u.name FROM events e LEFT JOIN users u ON u.id=e.user_id"
    args: list = []
    if kinds:
        q += " WHERE e.kind IN (%s)" % ",".join("?" * len(kinds))
        args += kinds
    q += " ORDER BY e.created_at DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, args)]
