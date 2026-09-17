from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import RoomDeviceCodeResponse
from app.services.device.create_device import create_device
from app.services.device.get_device import get_device
from app.services.device.refresh_claim_code import refresh_claim_code


async def code_for_room_device(
    db: AsyncSession, *, device_id: str | None
) -> RoomDeviceCodeResponse:
    """A live code for a tablet to display, on its own device row whenever it still has one.

    A tablet names itself with the device id it was given the first time it asked. Anything
    else — no id yet, an id from a database that has since been replaced, an id that has
    already been claimed — is answered with a fresh device, because the alternative is a
    tablet that can never show a code again.
    """
    device = await get_device(db, device_id) if device_id else None
    if device is not None and device.claimed_at is None and device.unlinked_at is None:
        return RoomDeviceCodeResponse.of(device, await refresh_claim_code(db, device))

    minted = await create_device(db)
    return RoomDeviceCodeResponse.of(minted.device, minted.claim_code)
