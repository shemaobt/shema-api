"""What a tablet asks about itself: three calls to belong to a team, and one for help.

The room has no keyboard and shows no written words, with one exception: at installation
the tablet displays a code, a facilitator types it into the Desk and chooses the team, and
the link comes back to the tablet with nobody touching it. Three of these calls make that
possible from the tablet's side — the one that hands it a code to show, the one it polls
until the code has been spent, and the one it makes once afterwards to stop depending on
the shared key.

All of them are opened by the shared room key, because a tablet that has not collected yet
holds nothing else. That is the same dated compromise ``require_room_caller`` already
records, and retiring the key is ENG-455's.

The third one answers with a credential, and it is the only route here that does (ENG-622).
The claim mints one and hands it to the Desk, which never reads it; the row keeps only a
hash, so there is no way to give the tablet that copy and nothing is lost by not trying.
Collecting mints a fresh one instead, and the Desk's copy stops authenticating at that
moment — one device, one live credential.

The fourth is not part of installation and is here because it is addressed the same way
(ENG-624): a tablet saying it needs a person when it has no session to say it through. It
is the one route in this module that reads *which* device is calling rather than only that
somebody may — a tablet holding a credential may halt itself and nothing else.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import require_room_caller, room_caller_dep
from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.db.models.device import Device
from app.models.device import (
    DeviceCredentialResponse,
    DeviceNeedsPersonResponse,
    RoomDeviceCodeRequest,
    RoomDeviceCodeResponse,
    RoomDeviceLinkResponse,
)
from app.services.device.code_for_room_device import code_for_room_device
from app.services.device.collect_device_credential import collect_device_credential
from app.services.device.link_for_room_device import link_for_room_device
from app.services.device.needs_person import record_needs_person

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


@router.post(
    "/devices/{device_id}/needs-person",
    response_model=DeviceNeedsPersonResponse,
)
async def ask_for_a_person_without_a_session(
    device_id: str,
    caller: Device | None = Depends(require_room_caller),
    db: AsyncSession = Depends(get_db),
) -> DeviceNeedsPersonResponse:
    """This tablet cannot go on and there is no session to say so through.

    The escalation this system had is addressed by a session id, which is exactly what a
    tablet does not have when the server has forgotten its session or the build broke
    before one was opened. So the halt is recorded on the device — the thing that is still
    there — and the facilitators of its team read it beside the sessions that halted.

    Four answers, and the tablet does something different with each:

    - **200** — recorded, with the moment it was first recorded. Asking again while it
      still stands answers the same moment, so a retry over a bad network costs nothing.
    - **409** — nobody has claimed this device, or it was taken out of service. It belongs
      to no team, so there is nobody the halt could reach; the tablet has an installation
      problem, not a room problem.
    - **403** — the credential presented belongs to a different device. A tablet that can
      name itself may halt itself and nothing else.
    - **404** — no device with that id, as ``link`` and ``credential`` say for the same.

    A caller on the shared key names no device and may halt any claimed one, which is the
    same window the three routes above stand in and closes with them in ENG-455.

    Nothing lifts this from here. The halt ends when that device opens a session, the way a
    session's ``NEEDS_PERSON`` ends when a turn lands; a facilitator saying they attended
    to it is a different event and is ENG-609's.

    **The two halves are not symmetric, and the asymmetry has a floor under it.** Halting is
    open to the shared key; lifting is not, and cannot be — a caller presenting the key names
    no device, so ``POST /sessions`` has nothing to lift. A halt recorded on the key therefore
    has nothing in this slice that clears it. What keeps that off the field is the order the
    work was authorised in: the app collects its credential in ENG-622 and starts presenting
    it in ENG-623, both before ENG-625 makes it call this route at all, so every call that
    happens in a room names its device. A tablet that halted on the key anyway would wait for
    ENG-609's facilitator lift — and that is the sentence to re-read before calling this route
    from anywhere else.
    """
    if caller is not None and caller.id != device_id:
        raise AuthorizationError("A device may only ask for a person for itself.")

    return DeviceNeedsPersonResponse(
        device_id=device_id,
        needs_person_since=await record_needs_person(db, device_id),
    )
