"""
Push-notification dispatcher for ledger health alerts (Phase 1.11 hardening).

Single entry point ``notify_alert(subject, body, severity)`` used by the
``check_ledger_health`` Celery task when a paper-trading engine is stalled or its
books don't reconcile. Delivery is **opt-in via env vars**: it ALWAYS logs loudly
(visible in ``docker logs`` + Flower) and additionally pushes to a webhook and/or
email ONLY if the corresponding env vars are set:

  - Webhook : ``ALERT_WEBHOOK_URL`` (Slack / Discord / generic incoming webhook).
               Optional ``ALERT_WEBHOOK_FORMAT`` ∈ {slack, discord} (default slack;
               slack POSTs ``{"text": ...}``, discord POSTs ``{"content": ...}``).
  - Email   : ``ALERT_SMTP_HOST`` + ``ALERT_SMTP_USER`` + ``ALERT_SMTP_PASSWORD``
               + ``ALERT_EMAIL_FROM`` + ``ALERT_EMAIL_TO`` (STARTTLS; port 587
               unless ``ALERT_SMTP_PORT`` overrides).

Fault tolerance is load-bearing here: a failed webhook/email MUST NOT raise — that
would abort the very health task that detected the problem, turning a delivery
hiccup into a silent loss of the alert. Every channel is wrapped and its failure
is logged + reported, never propagated.

Stdlib only (urllib, smtplib, email) — no new dependency.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib import request, error

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 10


def webhook_configured() -> bool:
    return bool(os.getenv("ALERT_WEBHOOK_URL"))


def _webhook_format() -> str:
    fmt = (os.getenv("ALERT_WEBHOOK_FORMAT") or "slack").strip().lower()
    return fmt if fmt in ("slack", "discord") else "slack"


def email_configured() -> bool:
    """True only if ALL the SMTP pieces are present (else email is silently skipped)."""
    return all(os.getenv(k) for k in (
        "ALERT_SMTP_HOST", "ALERT_SMTP_USER", "ALERT_SMTP_PASSWORD",
        "ALERT_EMAIL_FROM", "ALERT_EMAIL_TO",
    ))


def _push_webhook(subject: str, body: str, severity: str) -> None:
    """POST a JSON payload to the configured webhook (Slack-style by default).

    ``urlopen`` raises ``HTTPError`` on a non-2xx response; Discord's success code
    is 204, which ``urlopen`` treats as success. Any error propagates to the caller
    (notify_alert) which logs it and carries on.
    """
    url = os.getenv("ALERT_WEBHOOK_URL")
    if not url:
        return
    text = f"[{severity.upper()}] {subject}\n\n{body}"
    payload = {"content": text} if _webhook_format() == "discord" else {"text": text}
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SECONDS)  # raises on failure (caught above)


def _push_email(subject: str, body: str, severity: str) -> None:
    """Send an alert email via STARTTLS. Silently skipped when not fully configured."""
    if not email_configured():
        return
    host = os.getenv("ALERT_SMTP_HOST")
    port = int(os.getenv("ALERT_SMTP_PORT") or "587")
    user = os.getenv("ALERT_SMTP_USER")
    password = os.getenv("ALERT_SMTP_PASSWORD")
    sender = os.getenv("ALERT_EMAIL_FROM")
    recipient = os.getenv("ALERT_EMAIL_TO")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    # Subject passed verbatim — the digest already encodes severity in its
    # '[StockAnalyzer] Digest/Alert …' subject, and a clean subject is what Gmail
    # filters on. Severity still shows in the log + webhook payload.
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=WEBHOOK_TIMEOUT_SECONDS) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(user, password)
        server.send_message(msg)


def notify_alert(subject: str, body: str, severity: str = "warning") -> dict:
    """Dispatch an alert. Always logs; pushes to webhook/email if configured.

    Returns a small report of what was attempted/ok (handy for logging + tests).
    NEVER raises — a delivery failure is logged and reported, not propagated (see
    the module docstring: the alert path must not become a second failure).
    """
    report: dict = {"subject": subject, "severity": severity, "channels": {}}

    # Always log — the log line itself is the zero-config alert channel.
    (logger.error if severity != "info" else logger.info)(
        "[ALERT][%s] %s\n%s", severity.upper(), subject, body
    )

    if webhook_configured():
        try:
            _push_webhook(subject, body, severity)
            report["channels"]["webhook"] = "ok"
        except (error.URLError, error.HTTPError, OSError) as e:
            report["channels"]["webhook"] = f"failed: {e}"
            logger.warning("[ALERT] webhook delivery failed: %s", e)

    if email_configured():
        try:
            _push_email(subject, body, severity)
            report["channels"]["email"] = "ok"
        except Exception as e:  # noqa: BLE001 — must never propagate
            report["channels"]["email"] = f"failed: {e}"
            logger.warning("[ALERT] email delivery failed: %s", e)

    return report
