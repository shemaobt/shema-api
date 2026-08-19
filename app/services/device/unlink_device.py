from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.device import Device
from app.services.device.get_team_device import get_team_device


async def unlink_device(db: AsyncSession, *, user: User, device_id: str) -> Device:
    """Take a device out of service and revoke the credential it authenticates with.

    Nulling ``credential_hash`` is the revocation, not the timestamp beside it. The lookup
    that authenticates a device compares hashes for equality and NULL equals nothing, so
    once this write lands there is no string anyone could present that would match — not
    the credential the device holds, not one recovered from a backup.

    Coming back takes a fresh claim. Nothing in this slice can put the credential back, and
    that is the point: a device that was revoked because it went missing must not be
    revivable by whoever holds it.
    """
    device = await get_team_device(db, user=user, device_id=device_id)

    device.credential_hash = None
    device.unlinked_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(device)
    return device
