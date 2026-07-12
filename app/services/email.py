from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    pass


async def send_email_verification_code(email: str, code: str) -> None:
    provider = settings.EMAIL_PROVIDER.lower()
    if provider == "console":
        _send_console_verification(email, code)
        return
    if provider == "brevo":
        await asyncio.to_thread(_send_brevo_verification, email, code)
        return
    raise EmailDeliveryError(f"Unsupported EMAIL_PROVIDER: {settings.EMAIL_PROVIDER}")


def _send_console_verification(email: str, code: str) -> None:
    if settings.APP_ENV == "production":
        raise EmailDeliveryError("Console email provider cannot be used in production")
    print(f"[email-verification] to={email} code={code}")


def _send_brevo_verification(email: str, code: str) -> None:
    if not settings.BREVO_API_KEY:
        raise EmailDeliveryError("BREVO_API_KEY must be configured")
    if not settings.EMAIL_FROM:
        raise EmailDeliveryError("EMAIL_FROM must be configured")

    payload = {
        "sender": {"email": settings.EMAIL_FROM},
        "to": [{"email": email}],
        "subject": "Codigo de verificacao CamelBox",
        "textContent": f"Seu codigo de verificacao CamelBox e: {code}",
        "htmlContent": f"<p>Seu codigo de verificacao CamelBox e: <strong>{code}</strong></p>",
    }
    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-key": settings.BREVO_API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                raise EmailDeliveryError(f"Brevo returned status {response.status}")
    except urllib.error.URLError as exc:
        raise EmailDeliveryError("Brevo email delivery failed") from exc
