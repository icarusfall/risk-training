"""Outbound email via Resend, with a no-op fallback.

With no RESEND_API_KEY set, messages are logged instead of sent, so the whole
site runs locally without any mail configuration. Setup links get printed to
the console, which is what you want in development anyway.
"""
from __future__ import annotations

import logging

import requests

from . import config

log = logging.getLogger(__name__)
_API = "https://api.resend.com/emails"


def send(to: str, subject: str, body: str, reply_to: str | None = None) -> bool:
    """Plain-text send. Returns True if it actually left the building."""
    if not config.RESEND_API_KEY:
        log.warning("EMAIL (not sent, no RESEND_API_KEY)\n  to: %s\n  subject: %s\n%s",
                    to, subject, body)
        return False
    payload = {"from": config.MAIL_FROM, "to": [to], "subject": subject, "text": body}
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        r = requests.post(
            _API,
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code >= 300:
            log.error("Resend refused (%s): %s", r.status_code, r.text[:400])
            return False
        return True
    except Exception:
        log.exception("Email send failed")
        return False


def send_admin(subject: str, body: str) -> bool:
    if not config.ADMIN_EMAIL:
        log.warning("ADMIN EMAIL (no ADMIN_EMAIL set)\n  subject: %s\n%s", subject, body)
        return False
    return send(config.ADMIN_EMAIL, subject, body)


def _duration(hours: int) -> str:
    if hours >= 48 and hours % 24 == 0:
        return f"{hours // 24} days"
    return f"{hours} hours"


def send_setup_link(to: str, name: str, url: str, purpose: str, hours: int) -> bool:
    """A link to choose a password.

    purpose is "signup" (someone signing themselves up), "invite" (the admin
    setting someone up, including moving an existing joiner onto passwords),
    "existing" (a sign-up attempt for an address that already has an account)
    or "reset" (a forgotten password).
    """
    if purpose == "signup":
        subject = "Choose your password for the risk model training site"
        intro = ("Thanks for signing up to the risk model training site. Choose a "
                 "password here to finish setting up your account:")
        outro = "If you did not sign up, ignore this email and no account will be created."
    elif purpose == "invite":
        subject = "Your account on the risk model training site"
        intro = (f"{config.ADMIN_NAME} has set you up on the risk model training site, "
                 "which signs you in with a password. Choose yours here:")
        outro = ("If you have used the site before, nothing else has changed: your "
                 "portfolio and your progress are exactly where you left them.")
    elif purpose == "existing":
        subject = "You already have an account on the risk model training site"
        intro = ("Someone tried to sign up with this address, but it already has an "
                 "account. If that was you, you can set a new password here:")
        outro = "If it was not you, ignore this email. Your password has not changed."
    else:
        subject = "Set a new password for the risk model training site"
        intro = ("We had a request to set or reset the password for this address. "
                 "Choose a new one here:")
        outro = "If you did not ask for this, ignore this email. Your password has not changed."
    body = (
        f"{'Hello ' + name if name else 'Hello'},\n\n"
        f"{intro}\n\n"
        f"    {url}\n\n"
        f"The link works once, for {_duration(hours)}.\n\n"
        f"{outro}\n\n"
        f"{config.BASE_URL}\n"
    )
    return send(to, subject, body, reply_to=config.MAIL_REPLY_TO or None)


def send_new_signup_to_admin(email: str, name: str) -> bool:
    """Someone finished signing up. Sent once the account exists, not when the
    form is filled in, so a mistyped address does not produce a note."""
    who = f"{name} ({email})" if name else email
    body = (
        f"{who} has created an account on the risk model training site.\n\n"
        f"    {config.BASE_URL}/admin\n\n"
        f"Nothing to do unless you do not recognise them, in which case you can "
        f"delete the account from the database.\n"
    )
    return send_admin(f"[risk-training] New sign-up: {who}", body)
