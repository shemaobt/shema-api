"""The one moment a tablet takes a credential of its own, and the three refusals around it.

Every other room route a tablet calls is opened by ``X-Room-Key``: one string, identical in
every installation, naming nobody and revocable only by shipping a new bundle. The claim
already mints the credential that replaces it — and hands it to the Desk, which
``git grep credential`` says has never read it. So the credential exists and the one party
that needs it has no way to reach it. This is the reach.

**It mints a fresh one rather than handing back the claim's.** Not a choice: the row keeps
only a hash, so the claim-time plaintext is gone the moment that response is written. What
follows from minting is that the Desk's copy stops authenticating here, and that is
wanted rather than tolerated — one device, one live credential, and a copy nobody read is
not worth leaving open.

**Which is why the overlap hash is cleared too, and not only replaced.** A rotation keeps
the credential that was presented alive on purpose, parking its hash in
``previous_credential_hash``, and the door reads that column as readily as the current one.
Anyone holding the claim-time copy can rotate with it — the Desk holds one and never does,
but the route asks for nothing else — and a collection that wrote only ``credential_hash``
would leave that parked hash open behind it. One live credential has to mean the column
that overlaps as well, or it means nothing. Nothing is lost by clearing it: a device
collecting for the first time has never authenticated as itself, so any overlap standing in
the row belongs to somebody who is not the tablet.

**Exactly once, and the guard is the write.** The reads below produce the precise refusal;
they are not what makes it single-use. Between reading a row and writing it another call
can collect, and both would pass a check made on a stale read. So the ``UPDATE`` carries
``WHERE credential_collected_at IS NULL`` and a row count of zero means the other call
won — atomic on any engine, which matters because the suite runs on SQLite and
``SELECT ... FOR UPDATE`` is a no-op there. ``claim_device`` spends its code the same way
and for the same reason.

**What exactly-once costs, stated rather than discovered.** A response lost on the room's
network costs the tablet the credential: it retries, is refused, and has to show a new claim
code. That is the opposite of the trade ``rotate_device_credential`` makes, which keeps the
presented credential alive precisely because a bad network drops the answer. The difference
is that a rotation has a credential to fall back on and a first collection has none, so
there is nothing to keep alive — the only alternative would be handing the same credential
out repeatedly, which is not a thing a row holding a hash can do.

**Three refusals, three statuses, because the tablet acts on them differently.** Never
claimed and taken out of service are one answer (409), as ``link`` also treats them as one:
the device holds no team, it may hold one later, keep polling. Already collected is another
(403): permanent, stop asking, show a new code. An id this server never minted is a fourth
(404), the same as ``link``. A single refusal for all of them leaves the app unable to
choose, and choosing wrong either strands a working tablet or wipes one.
"""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.db.models.device import Device
from app.services.device.credential import generate_device_credential, hash_device_credential
from app.services.device.get_device import get_device

ALREADY_COLLECTED = "This device has already collected its credential."
NOT_LINKED = "This device is not linked to a team."


async def collect_device_credential(db: AsyncSession, device_id: str) -> str:
    """Issue ``device_id`` the credential it will authenticate with, once, and return it.

    The returned string is the only copy; the row keeps a hash. Raises ``NotFoundError``
    for an id this server never minted, ``ConflictError`` while the device belongs to no
    team — never claimed, or taken out of service — and ``AuthorizationError`` once it has
    collected, which never stops being true.

    The guard on the write covers all three states and not only the collected one, so a
    collection racing an unlink cannot slip a credential to a device on its way out of
    service. A lost race is answered as already collected: the reads above already ruled
    out the other two, and of the three refusals it is the one that tells the tablet to
    stop and show a new code, which is the safe reaction to every way this write can lose.
    """
    device = await get_device(db, device_id)
    if device is None:
        raise NotFoundError("No device with that id.")
    if device.claimed_at is None or device.unlinked_at is not None:
        raise ConflictError(NOT_LINKED)
    if device.credential_collected_at is not None:
        raise AuthorizationError(ALREADY_COLLECTED)

    issued = generate_device_credential()
    collected_at = datetime.now(UTC)
    collected = await db.execute(
        update(Device)
        .where(
            Device.id == device.id,
            Device.claimed_at.is_not(None),
            Device.unlinked_at.is_(None),
            Device.credential_collected_at.is_(None),
        )
        .values(
            credential_hash=hash_device_credential(issued),
            previous_credential_hash=None,
            credential_issued_at=collected_at,
            credential_collected_at=collected_at,
        )
    )
    if collected.rowcount != 1:
        raise AuthorizationError(ALREADY_COLLECTED)

    await db.commit()
    await db.refresh(device)
    return issued
