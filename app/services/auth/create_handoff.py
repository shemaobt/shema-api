"""Minting a handoff code — the half of BE-21 that runs inside a signed-in session.

**Three things are checked before anything is written, and each is read from the database.**
The session behind the request has to be live, the account has to still be active, and the
account has to hold a grant in the app it wants to open. The caller's ``User`` comes from the
dependency's thirty-second cache and ``require_app_access`` reads roles through another; both
are the right trade for *may this account use the app*, asked on every request, and the wrong
one for minting a credential. It is the distinction ``holds_capability`` draws in
``docs/resource_requests.md`` §5.5, applied to the account row as well as to the roles.

**Why the refresh token.** The bearer token proves who is asking and nothing about whether
that session still exists: it is stateless and good for thirty minutes after a logout or a
password reset. The exchange pays out a new seven-day refresh token, so a handoff minted off a
bearer alone would turn any access token that leaked into a session with no end, and one that
survives the password reset that revoked every other. Requiring the session's own refresh
token, read through the same ``read_live_refresh_token`` as ``/refresh``, is what makes
*requires a valid session* a check rather than a signature.

**The grant is the destination's own door, read live.** For every app that door is
``require_app_access``'s rule — a platform admin passes, and anybody else needs a live role in
the app — restated here rather than called because that guard is a FastAPI dependency with the
key fixed at wiring time, and this key arrives in the body. **The resource-request form is the
one app whose door is wider** (BE-19, OBT-520): a live member of a PME project enters it with
no grant, because that is who the team is since GATE-04 (OBT-519). Its rule is
``enters_the_form``, asked here with ``cached=False`` and not restated, because a copy is what
refused the member the door admits and killed the PME → form flow (OBT-538, OBT-544) before it
started. A membership opens nothing else: every other app still asks for a grant.
``FORM_APP_KEY`` repeats ``_deps.APP_KEY`` because a service may not import a router, and a test
keeps the two equal.

**The context is checked here, not in the request model.** It is opaque, so all there is to
check is that it is small and plain: at most ``HANDOFF_CONTEXT_MAX_BYTES`` of compact UTF-8
JSON, with no ``NaN`` or ``Infinity`` — which the request parser accepts and the database's
``json`` type refuses. A model refusal is answered with its input echoed, and the echo of a
``NaN`` fails to serialise, so the check lives where its refusal carries no input.

The raw code leaves once, in the return value. What is stored is its digest.
"""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    UnknownReferenceError,
    UnprocessableValueError,
)
from app.db.models.auth import AuthHandoffCode, User
from app.models.auth import HANDOFF_CONTEXT_MAX_BYTES, HandoffResponse
from app.services.auth.get_user_by_id import get_user_by_id
from app.services.auth.read_live_refresh_token import read_live_refresh_token
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.authorization.list_roles import list_roles
from app.services.common import tokens

#: The resource-request form — the one app whose door admits more than a grant (BE-19).
FORM_APP_KEY = "resource-request-form"


def _check_context(context: dict[str, Any] | None) -> None:
    """Refuse a context that is not small, plain JSON — measured in bytes, not characters."""
    if context is None:
        return
    try:
        encoded = json.dumps(
            context, allow_nan=False, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    except ValueError as exc:
        raise UnprocessableValueError(
            "context: must be plain JSON, with no NaN or Infinity."
        ) from exc
    if len(encoded) > HANDOFF_CONTEXT_MAX_BYTES:
        raise UnprocessableValueError(
            f"context: {len(encoded)} bytes, and it may weigh at most {HANDOFF_CONTEXT_MAX_BYTES}."
        )


async def _enters(db: AsyncSession, account: User, app_key: str) -> bool:
    """Whether ``account`` may enter ``app_key`` — its door's rule, read from the database.

    ``enters_the_form`` is imported here and not at the top: ``app.services`` imports this
    package before it binds ``authorization_service``, which the form's services read — a cycle
    at import time only, the one ``_membership.is_member`` sidesteps the same way.
    """
    if app_key == FORM_APP_KEY:
        from app.services.resource_request import enters_the_form

        return await enters_the_form(db, account, app_key, cached=False)
    return account.is_platform_admin or bool(await list_roles(db, account.id, app_key))


async def create_handoff(
    db: AsyncSession,
    user: User,
    *,
    app_key: str,
    refresh_token: str,
    context: dict[str, Any] | None,
    created_ip: str | None,
    now: datetime | None = None,
) -> HandoffResponse:
    """Mint one code that opens ``app_key`` as ``user``, or refuse before writing anything.

    401 when ``refresh_token`` is not a live session of ``user``; 403 when the account is no
    longer active or may not enter the app; 422 when no app has that key, or when the
    context is too heavy or not plain JSON.
    """
    _check_context(context)
    session = await read_live_refresh_token(db, refresh_token)
    if session.user_id != user.id:
        raise AuthenticationError("The refresh token belongs to another session.")

    account = await get_user_by_id(db, user.id)
    if account is None or not account.is_active:
        raise AuthorizationError("Inactive or missing user")

    app = await get_app_by_key(db, app_key)
    if app is None:
        raise UnknownReferenceError(f"app_key: no application is registered as '{app_key}'.")

    if not await _enters(db, account, app.app_key):
        raise AuthorizationError(
            f"You hold no role in the '{app_key}' application, so no handoff to it is issued."
        )

    minted = tokens.mint()
    expires_at = tokens.expiry(
        now or datetime.now(UTC), seconds=get_settings().auth_handoff_code_expire_seconds
    )
    db.add(
        AuthHandoffCode(
            user_id=account.id,
            app_id=app.id,
            code_hash=minted.digest,
            context=context,
            expires_at=expires_at,
            created_ip=created_ip,
        )
    )
    await db.commit()
    return HandoffResponse(code=minted.raw, expires_at=expires_at)
