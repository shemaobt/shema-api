"""Turning a presented credential into the device that holds it, or into a refusal.

Three outcomes, and the difference between the last two is the point of the module: the
credential is current or overlapping (a device), it was revoked (``DeviceRevoked``), or it
was never issued (``None``). A caller that cannot tell the last two apart cannot tell a
decommissioned tablet what to do.

**Nothing here is cached, deliberately.** A cache is the only thing that could make
revocation take effect later than the next request, and "immediately" is what ENG-448
promises. The room runs on Cloud Run, which scales to several instances that share no
memory and have no way to invalidate each other — a per-instance cache would mean a
revoked device kept working on whichever instances had not expired their copy yet, for as
long as the TTL. ``app/core/auth_cache.py`` accepts exactly that trade for a user's roles
at ``ttl=300``; a revoked credential is not the same kind of stale.

What it costs is one indexed lookup per request against a unique index. That is the price
of the promise.
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeviceRevoked
from app.db.models.device import Device
from app.services.device.credential import hash_device_credential


async def authenticate_device(db: AsyncSession, credential: str) -> Device | None:
    """The device holding ``credential``, or None if no device ever did.

    Raises ``DeviceRevoked`` when the credential is one a facilitator took away.

    The current and previous hashes are read in a single statement because both are the
    ordinary case — a tablet mid-rotation is not an error path. The revoked hash is only
    reached once neither matched, so a normal request pays for one lookup, not two.
    """
    presented = hash_device_credential(credential)

    device = (
        await db.execute(
            select(Device).where(
                or_(
                    Device.credential_hash == presented,
                    Device.previous_credential_hash == presented,
                )
            )
        )
    ).scalar_one_or_none()

    if device is not None:
        if device.credential_hash == presented and device.previous_credential_hash is not None:
            await _retire_the_previous_credential(db, device)
        return device

    if await _was_revoked(db, presented):
        raise DeviceRevoked("This device is no longer linked.")
    return None


async def _retire_the_previous_credential(db: AsyncSession, device: Device) -> None:
    """The first use of a rotated credential is what ends the one it replaced.

    Proof the tablet received the new credential, which a clock cannot observe. Until it
    arrives both open the device; after it, only one does.
    """
    device.previous_credential_hash = None
    await db.commit()
    await db.refresh(device)


async def _was_revoked(db: AsyncSession, presented: str) -> bool:
    """Whether this hash belonged to a device that was unlinked.

    Read only after authentication has already failed, and never as a way in. Nothing
    here can return a device.
    """
    return (
        await db.execute(select(Device.id).where(Device.revoked_credential_hash == presented))
    ).scalar_one_or_none() is not None
