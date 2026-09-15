"""Password hashing and the rules for choosing one.

scrypt from the standard library, so there is no extra wheel to build on
Railway. Each hash carries its own parameters and salt, which means the cost
can be raised later without breaking existing passwords.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

N, R, P, DKLEN = 2 ** 14, 8, 1, 32      # about 16MB and a few tens of ms per hash
MIN_LENGTH = 10
MAX_LENGTH = 200

# Not an exhaustive list, just the ones people actually type into a form that
# asks for ten characters.
_COMMON = {
    "password12", "password123", "password1234", "passwordpassword", "1234567890",
    "12345678910", "0123456789", "qwertyuiop", "qwertyuiop1", "letmein123",
    "iloveyou12", "welcome123", "abcdefghij", "abc1234567", "riskmodel1",
    "changeme123", "trustno1234",
}


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=DKLEN)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        return False
    try:
        algo, n, r, p, salt, expected = stored.split("$")
        if algo != "scrypt":
            return False
        want = _unb64(expected)
        got = hashlib.scrypt(password.encode("utf-8"), salt=_unb64(salt),
                             n=int(n), r=int(r), p=int(p), dklen=len(want))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, want)


_DUMMY = hash_password("not a real password, only here to take up time")


def burn_time(password: str) -> None:
    """Do the same work as a real check, so a login for an address with no
    account takes as long as one for an address that has one."""
    verify_password((password or "x")[:MAX_LENGTH], _DUMMY)


def problem_with(password: str, email: str = "") -> str | None:
    """A reason to refuse this password, or None.

    Length is what matters, so there are no rules about digits and symbols,
    which mostly produce Password1! and a sticky note.
    """
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters. A short phrase works well."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    low = password.strip().lower()
    if email and low in {email.lower(), email.split("@")[0].lower()}:
        return "Choose something other than your email address."
    if low in _COMMON or len(set(low)) < 4:
        return "That one is too easy to guess. Try a short phrase instead."
    return None
