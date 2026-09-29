"""The link session — what verifying a request link's code hands the holder (BE-26, OBT-537).

A JWT with its own audience, ``rr_link``, and the link's id as ``sub``: the precedent of
``app/services/project_health/interview_token.py``, a bearer credential for someone with no
account. **The audience is what keeps the two sessions apart in both directions, and it is checked
by hand.** ``python-jose`` validates ``aud`` only when the token *has* one: given
``audience="rr_link"``, a user access token — which carries no ``aud`` — decodes cleanly, and
would have been read as a link session naming a user's id. The test that tried it is what found
it. So the decoder demands ``aud == "rr_link"`` and no ``type`` claim. The other direction needs
no help: a link session carries no ``type``, so ``get_current_user_from_access_token`` refuses
it, and ``python-jose`` rejects an ``aud`` nobody asked for.

The token says **which link**, never what the link may do: the resolver reads the link row on
every call, so revoking a link or letting it expire ends every session it opened, with no list
of sessions to chase.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config import get_settings

LINK_SESSION_AUDIENCE = "rr_link"


def encode_link_session(link_id: str, now: datetime | None = None) -> tuple[str, datetime]:
    settings = get_settings()
    now = now or datetime.now(UTC)
    expires_at = now + timedelta(days=settings.rr_link_session_expire_days)
    payload = {
        "sub": link_id,
        "aud": LINK_SESSION_AUDIENCE,
        "jti": str(uuid4()),
        "iat": now,
        "exp": expires_at,
    }
    token = str(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))
    return token, expires_at


def link_session_subject(token: str) -> str | None:
    """The link id a valid link session names, or ``None`` for anything else.

    ``None`` and not an error: a bearer token that is not a link session may be a user's, and
    the resolver hands it to the user path, which refuses it in its own words if it is neither.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=LINK_SESSION_AUDIENCE,
        )
    except JWTError:
        return None
    if payload.get("aud") != LINK_SESSION_AUDIENCE or "type" in payload:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None
