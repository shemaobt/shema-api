"""The one write the Desk makes to a room's configuration.

The mapping from a refusal to a response is this module's whole job, and it is the point
at which ENG-437's single answer becomes three. What the service decided, this translates:
the three code states get their own ``code`` in the body, and everything about the team the
caller named collapses into ``CLAIM_CODE_UNKNOWN``.

The refusal is built here rather than by a registered exception handler because the handler
in ``app/core/exceptions.py`` flattens every 4xx to ``BAD_REQUEST``, and a single shared
code is exactly what ENG-460 says is not enough for the Desk.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.device import (
    ERROR_CODE_CLAIM_CODE_ALREADY_USED,
    ERROR_CODE_CLAIM_CODE_EXPIRED,
    ERROR_CODE_CLAIM_CODE_UNKNOWN,
    DeviceClaimRequest,
    DeviceClaimResponse,
)
from app.services.device.claim_device import (
    REASON_ALREADY_SPENT,
    REASON_EXPIRED,
    InvalidClaimCodeError,
)
from app.services.device.claim_device_as_facilitator import claim_device_as_facilitator

facilitator_devices_router = APIRouter()

_REFUSAL_BODIES = {
    REASON_ALREADY_SPENT: (
        "That claim code has already been used.",
        ERROR_CODE_CLAIM_CODE_ALREADY_USED,
    ),
    REASON_EXPIRED: (
        "That claim code has expired.",
        ERROR_CODE_CLAIM_CODE_EXPIRED,
    ),
}
_UNKNOWN_REFUSAL = ("That claim code is not valid.", ERROR_CODE_CLAIM_CODE_UNKNOWN)


def _refusal_response(error: InvalidClaimCodeError) -> JSONResponse:
    """One refused claim, told to the Desk in the terms it can act on.

    Anything not in the table — an unknown code, a team the caller does not facilitate, a
    project that does not exist — falls to the same unknown answer. That default is doing
    security work, not tidying: a reason that is not listed must never invent a new code
    for itself, because a new code is a new thing a facilitator can learn by guessing.
    """
    detail, code = _REFUSAL_BODIES.get(error.reason, _UNKNOWN_REFUSAL)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": detail, "code": code},
    )


@facilitator_devices_router.post("/claim", response_model=None)
async def claim_device_route(
    payload: DeviceClaimRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeviceClaimResponse | JSONResponse:
    """Trade the code the tablet is showing for the credential it will authenticate with."""
    try:
        claimed = await claim_device_as_facilitator(
            db,
            user=user,
            code=payload.code,
            project_id=payload.project_id,
            label=payload.label,
        )
    except InvalidClaimCodeError as error:
        return _refusal_response(error)

    return DeviceClaimResponse(
        device_id=claimed.device.id,
        project_id=payload.project_id,
        label=claimed.device.label,
        credential=claimed.credential,
    )
