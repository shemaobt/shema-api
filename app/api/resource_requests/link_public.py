"""The request link's public door — read its state, verify its code (BE-26, OBT-537, PR B).

No session: the token in the path is the credential, and it opens exactly one link. Two limits
stacked, the leader link's pattern (``app/api/shema/forms.py``): per address, and per **token
digest** — a forwarded link worked by many phones is one token, and the bucket that notices is
the token's. The key is the digest, never the token, because a limiter's store is not a place a
credential should be readable from.

**No ``from __future__ import annotations`` in this file**, for ``forms.py``'s reason:
``@limiter.limit`` wraps the handler, FastAPI resolves string annotations against the wrapper's
globals — slowapi's module — and ``Db`` would stop being a dependency.
"""

import hashlib
from datetime import datetime

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from slowapi.util import get_remote_address

from app.api.resource_requests._deps import Db
from app.core.rate_limit import limiter
from app.models.resource_request import LinkStatus
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])

#: Reading a link's state: a person reopening an e-mail on a bad connection, and no more.
LINK_READ_RATE_LIMIT = "30/minute"
#: Verifying: the code has its own limit of five, and this keeps a script from spending them
#: across many links from one address.
LINK_VERIFY_RATE_LIMIT = "10/minute"
#: What one link may take, whoever is holding it and from wherever.
LINK_TOKEN_RATE_LIMIT = "20/minute"


def link_token_key(request: Request) -> str:
    token = request.path_params.get("token")
    if not token:
        return get_remote_address(request)
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


class PublicLinkOut(BaseModel):
    """What the public screen shows before the code: the state, the masked address, the hint."""

    model_config = ConfigDict(extra="forbid")

    status: LinkStatus
    email_hint: str
    project_hint: str
    expires_at: datetime


class LinkCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)


class LinkSessionOut(BaseModel):
    """The link session: a bearer token for this module's routes, when it dies, and the link's
    address — whole, because the code that was sent to it has just been typed (FE-55)."""

    model_config = ConfigDict(extra="forbid")

    session: str
    expires_at: datetime
    email: str


@router.get("/link/{token}")
@limiter.limit(LINK_READ_RATE_LIMIT, key_func=get_remote_address)
@limiter.limit(LINK_TOKEN_RATE_LIMIT, key_func=link_token_key)
async def read_link(token: str, request: Request, db: Db) -> PublicLinkOut:
    """A known link's state is read, never refused; an unknown token is 404."""
    found = await service.read_request_link(db, token)
    return PublicLinkOut(**found._asdict())


@router.post("/link/{token}/verify", response_model=LinkSessionOut)
@limiter.limit(LINK_VERIFY_RATE_LIMIT, key_func=get_remote_address)
@limiter.limit(LINK_TOKEN_RATE_LIMIT, key_func=link_token_key)
async def verify_link(
    token: str, body: LinkCodeIn, request: Request, db: Db
) -> LinkSessionOut | JSONResponse:
    """The code for a link session. A wrong code is 401 and says how many tries are left; an
    expired or revoked link — the fifth wrong code included — is 410."""
    outcome = await service.verify_request_link(db, token, body.code)
    if isinstance(outcome, service.Verified):
        return LinkSessionOut(
            session=outcome.session, expires_at=outcome.expires_at, email=outcome.email
        )
    if outcome.reason == "gone":
        return JSONResponse(
            status_code=status.HTTP_410_GONE,
            content={
                "detail": "This request link has expired or was revoked.",
                "code": "LINK_GONE",
            },
        )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": "That code does not match this link.",
            "code": "LINK_CODE_WRONG",
            "attempts_left": outcome.attempts_left,
        },
    )
