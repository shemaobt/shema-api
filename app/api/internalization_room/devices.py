"""What a tablet may ask before it belongs to anybody.

The room has no keyboard and shows no written words, with one exception: at installation
the tablet displays a code, a facilitator types it into the Desk and chooses the team, and
the link comes back to the tablet with nobody touching it. These are the three calls that
make that possible from the tablet's side — the one that hands it a code to show, the one
it polls until the code has been spent, and the one it makes once afterwards to stop
depending on the shared key.

All three are opened by the shared room key, because a tablet that has not collected yet
holds nothing else. That is the same dated compromise ``require_room_caller`` already
records, and retiring the key is ENG-455's.

The third one answers with a credential, and it is the only route here that does (ENG-622).
The claim mints one and hands it to the Desk, which never reads it; the row keeps only a
hash, so there is no way to give the tablet that copy and nothing is lost by not trying.
Collecting mints a fresh one instead, and the Desk's copy stops authenticating at that
moment — one device, one live credential.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import room_caller_dep
from app.core.database import get_db
from app.models.device import (
    DeviceCredentialResponse,
    RoomDeviceCodeRequest,
    RoomDeviceCodeResponse,
    RoomDeviceLinkResponse,
)
from app.services.device.code_for_room_device import code_for_room_device
from app.services.device.collect_device_credential import collect_device_credential
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


@router.post(
    "/devices/{device_id}/credential",
    response_model=DeviceCredentialResponse,
    dependencies=[room_caller_dep],
)
async def collect_the_device_credential(
    device_id: str,
    db: AsyncSession = Depends(get_db),
) -> DeviceCredentialResponse:
    """The credential this tablet authenticates with from now on. Issued once, never again.

    Called once, after ``link`` has answered 200, and the answer is the only copy — the row
    keeps a hash. From here the tablet presents ``X-Device-Credential`` and stops needing
    the key every installation shares.

    Four answers, and the tablet does something different with each:

    - **200** — the credential. Store it and use it.
    - **409** — nobody has claimed this device, or it was taken out of service. It has no
      team yet and may have one later: keep polling ``link``. The same answer for both,
      exactly as ``link`` answers 204 for both.
    - **403** — this device already collected. Permanent: stop asking, forget what you have,
      and show a new claim code. That is also the answer to a response lost in transit, and
      the cost of issuing exactly once.
    - **404** — no device with that id, as ``link`` says for the same.
    """
    return DeviceCredentialResponse(
        device_id=device_id,
        credential=await collect_device_credential(db, device_id),
    )
