"""The base leader's public door — read, confirm the code, endorse (BE-23, OBT-535).

No session: the token in the path is the credential, and it opens exactly one request's
endorsement. The leader has no account (OBT-522), so the code confirmed once is what the read and
the act check afterwards — ``verified_at`` on the link, not a bearer token.

Two limits stacked, the request link's pattern (``link_public.py``): per address, and per
**token digest**, so a forwarded link worked by many phones is one bucket. The key is the digest,
never the token.

**No ``from __future__ import annotations`` in this file**, for ``link_public.py``'s reason:
``@limiter.limit`` wraps the handler, FastAPI resolves string annotations against the wrapper's
globals, and ``Db`` would stop being a dependency.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from slowapi.util import get_remote_address

from app.api.resource_requests._deps import Db
from app.api.resource_requests.link_public import (
    LINK_READ_RATE_LIMIT,
    LINK_TOKEN_RATE_LIMIT,
    LINK_VERIFY_RATE_LIMIT,
    link_token_key,
)
from app.core.rate_limit import limiter
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])

GONE = {
    "detail": "This endorsement link has expired or was revoked.",
    "code": "ENDORSEMENT_LINK_GONE",
}


class PublicEndorsementOut(BaseModel):
    """What the leader's page shows: the state always, the request only after the code."""

    model_config = ConfigDict(extra="forbid")

    status: service.EndorsementState
    email_hint: str
    request_name: str
    expires_at: datetime
    submitted_at: datetime
    document: dict[str, Any] | None


class EndorsementCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)


class VerifiedEndorsementOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: bool


class EndorseIn(BaseModel):
    """The name the leader signs with — the one thing typed, since there is no account."""

    model_config = ConfigDict(extra="forbid")

    leader_name: str = Field(min_length=1, max_length=160)


class EndorsedOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endorsed_at: datetime
    leader_name: str


@router.get("/endorse/{token}")
@limiter.limit(LINK_READ_RATE_LIMIT, key_func=get_remote_address)
@limiter.limit(LINK_TOKEN_RATE_LIMIT, key_func=link_token_key)
async def read_endorsement(token: str, request: Request, db: Db) -> PublicEndorsementOut:
    """A known link's state is read, never refused; an unknown token is 404."""
    found = await service.read_endorsement(db, token)
    return PublicEndorsementOut(**found._asdict())


@router.post("/endorse/{token}/verify", response_model=VerifiedEndorsementOut)
@limiter.limit(LINK_VERIFY_RATE_LIMIT, key_func=get_remote_address)
@limiter.limit(LINK_TOKEN_RATE_LIMIT, key_func=link_token_key)
async def verify_endorsement(
    token: str, body: EndorsementCodeIn, request: Request, db: Db
) -> VerifiedEndorsementOut | JSONResponse:
    """A wrong code is 401 and says how many tries are left; an expired or revoked link — the
    fifth wrong code included — is 410."""
    refused = await service.verify_endorsement(db, token, body.code)
    if refused is None:
        return VerifiedEndorsementOut(verified=True)
    if refused.reason == "gone":
        return JSONResponse(status_code=status.HTTP_410_GONE, content=GONE)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": "That code does not match this link.",
            "code": "ENDORSEMENT_CODE_WRONG",
            "attempts_left": refused.attempts_left,
        },
    )


@router.post("/endorse/{token}", response_model=EndorsedOut)
@limiter.limit(LINK_VERIFY_RATE_LIMIT, key_func=get_remote_address)
@limiter.limit(LINK_TOKEN_RATE_LIMIT, key_func=link_token_key)
async def endorse(
    token: str, body: EndorseIn, request: Request, db: Db
) -> EndorsedOut | JSONResponse:
    """Unverified is 403, twice is 409, an expired or revoked link is 410."""
    endorsed = await service.endorse_by_link(db, token, body.leader_name)
    if endorsed == "gone":
        return JSONResponse(status_code=status.HTTP_410_GONE, content=GONE)
    assert endorsed.endorsed_at is not None
    return EndorsedOut(endorsed_at=endorsed.endorsed_at, leader_name=endorsed.leader_name)
