import httpx

from app.core.config import get_settings
from app.core.exceptions import ValidationError

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def _siteverify(secret: str, token: str) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            RECAPTCHA_VERIFY_URL,
            data={"secret": secret, "response": token},
        )
        response.raise_for_status()
        payload = response.json()
    return bool(payload.get("success"))


async def verify_recaptcha(token: str | None) -> None:
    secret = get_settings().recaptcha_secret_key
    if not secret:
        return
    if not token:
        raise ValidationError("reCAPTCHA token is required")
    try:
        verified = await _siteverify(secret, token)
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        raise ValidationError("reCAPTCHA verification is unavailable. Please try again.") from exc
    if not verified:
        raise ValidationError("reCAPTCHA verification failed")
