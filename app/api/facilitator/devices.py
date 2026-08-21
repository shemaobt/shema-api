"""The routes that act on one device: claiming it, saying who uses it, taking it out.

Addressed by device, under one prefix. The team-addressed listing lives in ``teams.py``
with its own prefix, so no two routers share a URL space and nothing depends on the order
they are mounted in.

The mapping from a refusal to a response is this module's whole job, and it is the point
at which ENG-437's single answer becomes three. What the service decided, this translates:
the three code states get their own ``code`` in the body, and everything about the team the
caller named collapses into ``CLAIM_CODE_UNKNOWN``.

The refusal is built here rather than by a registered exception handler because the handler
in ``app/core/exceptions.py`` flattens every 4xx to ``BAD_REQUEST``, and a single shared
code is exactly what ENG-460 says is not enough for the Desk.
"""

from collections.abc import Mapping

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.models.device import (
    ERROR_CODE_CLAIM_CODE_ALREADY_USED,
    ERROR_CODE_CLAIM_CODE_EXPIRED,
    ERROR_CODE_CLAIM_CODE_UNKNOWN,
    DeviceClaimRequest,
    DeviceClaimResponse,
    DeviceLabelUpdateRequest,
    TeamDeviceResponse,
)
from app.services.device.claim_device import ClaimRefusal, InvalidClaimCodeError
from app.services.device.claim_device_as_facilitator import claim_device_as_facilitator
from app.services.device.set_team_device_label import set_team_device_label
from app.services.device.unlink_device import unlink_device

facilitator_devices_router = APIRouter()

#: Keyed by ``ClaimRefusal | None`` on purpose: a refusal that names no reason is a
#: legitimate lookup and has to fall to the unknown answer like any other reason not
#: listed here.
_REFUSAL_BODIES: Mapping[ClaimRefusal | None, tuple[str, str]] = {
    ClaimRefusal.ALREADY_SPENT: (
        "That claim code has already been used.",
        ERROR_CODE_CLAIM_CODE_ALREADY_USED,
    ),
    ClaimRefusal.EXPIRED: (
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
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
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


@facilitator_devices_router.patch("/{device_id}", response_model=TeamDeviceResponse)
async def edit_device_label_route(
    device_id: str,
    payload: DeviceLabelUpdateRequest,
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
) -> TeamDeviceResponse:
    """Say who uses this device. Returns the row, so the panel can redraw from the answer."""
    device = await set_team_device_label(db, user=user, device_id=device_id, label=payload.label)
    return TeamDeviceResponse.of(device)


@facilitator_devices_router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_device_route(
    device_id: str,
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Take this device out of service and revoke the credential it authenticates with.

    **Moving a device to another team is deliberately absent.** No requirement asks for it
    in v1 — see the PR for the mismatch with the control the Desk already ships.
    """
    await unlink_device(db, user=user, device_id=device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
