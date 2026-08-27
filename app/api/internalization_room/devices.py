"""What a tablet may ask before it belongs to anybody.

The room has no keyboard and shows no written words, with one exception: at installation
the tablet displays a code, a facilitator types it into the Desk and chooses the team, and
the link comes back to the tablet with nobody touching it. This is where the tablet gets
the code it displays.

It is opened by the shared room key, because a tablet nobody has linked holds nothing
else: it has no device credential, which is the very thing the claim exists to give it.
That is the same dated compromise ``require_room_caller`` already records, and retiring
the key is ENG-455's.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import room_caller_dep
from app.core.database import get_db
from app.models.device import RoomDeviceCodeRequest, RoomDeviceCodeResponse
from app.services.device.code_for_room_device import code_for_room_device

router = APIRouter()


@router.post(
    "/devices/code",
    response_model=RoomDeviceCodeResponse,
    dependencies=[room_caller_dep],
)
async def show_a_claim_code(
    payload: RoomDeviceCodeRequest = RoomDeviceCodeRequest(),
    db: AsyncSession = Depends(get_db),
) -> RoomDeviceCodeResponse:
    """The code the tablet puts on its screen, large enough to read across a table."""
    return await code_for_room_device(db, device_id=payload.device_id)
