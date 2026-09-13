"""Outbound email via Resend, with a no-op fallback.

With no RESEND_API_KEY set, messages are logged instead of sent, so the whole
site runs locally without any mail configuration. Magic links get printed to
the console, which is what you want in development anyway.
"""
from __future__ import annotations

import logging

import requests

from . import config

log = logging.getLogger(__name__)
_API = "https://api.resend.com/emails"


def send(to: str, subject: str, body: str) -> bool:
    """Plain-text send. Returns True if it actually left the building."""
    if not config.RESEND_API_KEY:
        log.warning("EMAIL (not sent, no RESEND_API_KEY)\n  to: %s\n  subject: %s\n%s",
                    to, subject, body)
        return False
    try:
        r = requests.post(
            _API,
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}",
                     "Content-Type": "application/json"},
            json={"from": config.MAIL_FROM, "to": [to],
                  "subject": subject, "text": body},
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


def send_magic_link(to: str, name: str, url: str) -> bool:
    body = (
        f"Hello{' ' + name if name else ''},\n\n"
        f"Here is your link into the risk model training site:\n\n"
        f"    {url}\n\n"
        f"It is good for 72 hours. You will not need a password.\n\n"
        f"Bring Excel and some patience.\n"
    )
    return send(to, "Your risk model training link", body)


def send_login_link_to_admin(email: str, name: str, url: str) -> bool:
    """A joiner asked for a link from the sign-in page. Send it to the admin in
    a form that can be forwarded as it stands."""
    who = f"{name} ({email})" if name else email
    greeting = f"Hello {name}," if name else "Hello,"
    body = (
        f"{who} asked for a login link to the risk model training site.\n\n"
        f"Forward everything between the lines to {email}:\n\n"
        f"----------------------------------------\n"
        f"{greeting}\n\n"
        f"Here is your link into the risk model training site:\n\n"
        f"    {url}\n\n"
        f"It is good for 72 hours. You will not need a password.\n"
        f"----------------------------------------\n"
    )
    return send_admin(f"[risk-training] Login link for {who}", body)


def send_access_request_to_admin(email: str) -> bool:
    """Someone asked for a link for an address that is not registered."""
    body = (
        f"Someone asked for a login link for {email}, which is not registered on "
        f"the risk model training site.\n\n"
        f"If they should have access, add them from the admin page:\n\n"
        f"    {config.BASE_URL}/admin\n\n"
        f"If you do not recognise the address, you can ignore this.\n"
    )
    return send_admin(f"[risk-training] Access request from {email}", body)
