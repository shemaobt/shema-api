from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.services.device.credential import hash_device_credential


async def get_device_by_credential(db: AsyncSession, credential: str) -> Device | None:
    """The device that holds ``credential``, or None.

    Looked up by hash, because the plaintext is not stored anywhere to compare against.
    """
    return (
        await db.execute(
            select(Device).where(Device.credential_hash == hash_device_credential(credential))
        )
    ).scalar_one_or_none()
