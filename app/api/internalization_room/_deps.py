from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, ValidationError
from app.db.models.device import Device
from app.services.device.authenticate_device import authenticate_device

#: What a claimed tablet presents to say which team it belongs to. Read by the header
#: declaration below and by the tests, so the wire name is written once.
DEVICE_CREDENTIAL_HEADER = "X-Device-Credential"


async def linked_tablet(
    db: AsyncSession = Depends(get_db),
    x_device_credential: str | None = Header(default=None, alias=DEVICE_CREDENTIAL_HEADER),
) -> Device:
    """The tablet at a team door, known by the credential it collected (ADR 0057).

    The team never signs in — the room is operated by voice and has no keyboard — so the
    credential is the device's, not a person's. It names one device row and through it one
    team, and unlinking the tablet from the Desk ends it at the next request.

    Only the credential the tablet collected opens the door: the copy the claim handed the
    Desk does not, and neither does the credential of a tablet whose team is gone. Both are
    refused exactly as a credential nobody issued, because to the tablet they are the same
    thing — it holds nothing that works. A revoked credential is the one refusal told
    apart (``DeviceRevoked``), because that tablet has to forget what it holds.
    """
    device = await authenticate_device(db, x_device_credential) if x_device_credential else None
    if device is None or device.credential_collected_at is None or device.project_id is None:
        raise AuthenticationError("Invalid device credential")
    return device


linked_tablet_dep = Depends(linked_tablet)


async def require_device(x_room_device: str | None = Header(default=None)) -> str:
    """Which tablet is speaking.

    The room has no accounts, so work is attributed to the device that produced it. The app
    mints this once and keeps it, which is what lets an answer find the team days later and
    what a take is filed under until a team login exists.

    Self-issued and unauthenticated: it matches no row anywhere, which is why it says which
    tablet but never which team. ``linked_tablet`` is what answers that.
    """
    if not x_room_device:
        raise ValidationError("Missing X-Room-Device header")
    return x_room_device


device_dep = Depends(require_device)


async def device_project(caller: Device = linked_tablet_dep) -> str:
    """The team of the tablet that is speaking.

    Derived from the gate's own result rather than looked up again — the credential is
    resolved once per request, and FastAPI's dependency cache is what makes the two
    declarations one query.
    """
    assert caller.project_id is not None
    return caller.project_id


device_project_dep = Depends(device_project)
