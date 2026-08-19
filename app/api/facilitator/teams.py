"""The Desk's devices panel: which tablets a team has, who uses them, and taking one out.

Every refusal on these routes is a 404 with one message, whether the row does not exist,
belongs to someone else's team, belongs to no team, or has already been unlinked. That is
the same rule ENG-443 holds at the claim, moved to the route next door: a facilitator who
could tell "not yours" from "no such thing" could map an installation by asking about ids,
and closing that at one door and leaving it open at another closes nothing.

**Moving a device to another team is deliberately absent.** No requirement asks for it in
v1 — see the PR for the mismatch with the control the Desk already ships.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.device import Device
from app.models.device import DeviceLabelUpdateRequest, TeamDeviceResponse
from app.services.device.list_team_devices import list_team_devices
from app.services.device.set_team_device_label import set_team_device_label
from app.services.device.unlink_device import unlink_device
from app.services.project.can_access_project import can_access_project

facilitator_team_devices_router = APIRouter()

TEAM_NOT_FOUND = "Team not found"


def _as_row(device: Device) -> TeamDeviceResponse:
    return TeamDeviceResponse(
        device_id=device.id,
        label=device.label,
        linked_at=device.claimed_at,
        last_seen_at=device.last_seen_at,
    )


@facilitator_team_devices_router.get("/teams/{team_id}/devices")
async def list_team_devices_route(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TeamDeviceResponse]:
    """The devices linked to this team. A team with none answers with an empty list."""
    if not await can_access_project(db, user.id, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    return [_as_row(device) for device in await list_team_devices(db, team_id)]


@facilitator_team_devices_router.patch("/devices/{device_id}")
async def edit_device_label_route(
    device_id: str,
    payload: DeviceLabelUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TeamDeviceResponse:
    """Say who uses this device. Returns the row, so the panel can redraw from the answer."""
    device = await set_team_device_label(db, user=user, device_id=device_id, label=payload.label)
    return _as_row(device)


@facilitator_team_devices_router.delete(
    "/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unlink_device_route(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Take this device out of service and revoke the credential it authenticates with."""
    await unlink_device(db, user=user, device_id=device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
