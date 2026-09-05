"""Generic e-mail transport.

``send_email`` is the single door every e-mail leaves through: the caller brings
recipient, subject and HTML body (usually rendered by ``render_email``), and the
provider configured in ``settings.email_provider`` does the delivery. An unset or
empty provider falls back to ``"log"``, which only writes a log line — the default
for tests and local development.

Sending is deliberately best-effort: a provider failure is logged and reported as
``False``, never raised, so an outage can never roll back the domain write of
whoever called it. Callers should still commit their own transaction before
sending anything that announces it.
"""

import logging
import time

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_graph_token_cache: dict[str, object] | None = None


async def send_email(
    to: str,
    subject: str,
    html: str,
    *,
    from_address: str | None = None,
    from_name: str | None = None,
) -> bool:
    """Send one e-mail through the configured provider; True when handed off.

    ``from_address`` defaults to ``settings.email_from_address``. ``from_name``
    becomes the display name on providers that support one (Resend); Microsoft
    Graph always sends as the ``from_address`` mailbox.
    """
    settings = get_settings()
    provider = settings.email_provider or "log"
    sender = from_address or settings.email_from_address

    if provider == "log":
        logger.info("[EMAIL] provider=log from=%s to=%s subject=%s", sender, to, subject)
        return True

    try:
        if provider == "resend":
            await _send_via_resend(to, subject, html, sender, from_name, settings.resend_api_key)
        elif provider == "microsoft_graph":
            await _send_via_graph(to, subject, html, sender)
        else:
            logger.warning("Unknown email_provider=%s — e-mail to %s not sent", provider, to)
            return False
    except Exception:
        logger.exception("email_provider=%s failed — e-mail to %s not sent", provider, to)
        return False

    return True


async def _get_graph_token() -> str:
    global _graph_token_cache

    if _graph_token_cache and time.time() < _graph_token_cache["expires_at"] - 60:  # type: ignore[operator]
        return _graph_token_cache["value"]  # type: ignore[return-value]

    import httpx

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.azure_client_id,
                "client_secret": settings.azure_client_secret,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        resp.raise_for_status()

    data = resp.json()
    _graph_token_cache = {
        "value": data["access_token"],
        "expires_at": time.time() + data["expires_in"],
    }
    token: str = data["access_token"]
    return token


async def _send_via_graph(
    to: str,
    subject: str,
    html: str,
    sender: str,
) -> None:
    import httpx

    token = await _get_graph_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": html},
                    "toRecipients": [
                        {"emailAddress": {"address": to}},
                    ],
                },
                "saveToSentItems": False,
            },
        )
        resp.raise_for_status()
    logger.info("[EMAIL] Sent via Microsoft Graph to=%s", to)


async def _send_via_resend(
    to: str,
    subject: str,
    html: str,
    sender: str,
    from_name: str | None,
    api_key: str,
) -> None:
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": f"{from_name} <{sender}>" if from_name else sender,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
        resp.raise_for_status()
    logger.info("[EMAIL] Sent via Resend to=%s", to)
