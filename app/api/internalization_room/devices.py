"""What a tablet may ask before it belongs to anybody.

The room has no keyboard and shows no written words, with one exception: at installation
the tablet displays a code, a facilitator types it into the Desk and chooses the team, and
the link comes back to the tablet with nobody touching it. These are the two calls that
make that possible from the tablet's side — the one that hands it a code to show, and the
one it polls until the code has been spent.

Both are opened by the shared room key, because a tablet nobody has linked holds nothing
else: it has no device credential, which is the very thing the claim exists to give it.
That is the same dated compromise ``require_room_caller`` already records, and retiring
the key is ENG-455's.

Neither route answers with a credential. The claim issues one to the Desk and the row
keeps only its hash, so there is nothing here to hand back; a tablet still authenticates
with the shared key until the app can hold one of its own.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import room_caller_dep
from app.core.database import get_db
from app.models.device import (
    RoomDeviceCodeRequest,
    RoomDeviceCodeResponse,
    RoomDeviceLinkResponse,
)
from app.services.device.code_for_room_device import code_for_room_device
from app.services.device.link_for_room_device import link_for_room_device

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


@router.get(
    "/devices/{device_id}/link",
    response_model=RoomDeviceLinkResponse,
    responses={status.HTTP_204_NO_CONTENT: {"description": "Nobody has claimed this device yet."}},
    dependencies=[room_caller_dep],
)
async def read_the_team_link(
    device_id: str,
    db: AsyncSession = Depends(get_db),
) -> RoomDeviceLinkResponse | Response:
    """Which team spent this device's code, once somebody has.

    Answers 204 for as long as the code is still on the screen, which is most of the life
    of this route — an empty body is the difference between "not yet" and "there is no
    such device", and the tablet acts on the two differently.
    """
    link = await link_for_room_device(db, device_id)
    if link is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return link
