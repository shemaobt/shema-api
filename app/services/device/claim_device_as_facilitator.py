"""The facilitator's claim: check the team first, then spend the code, then pay out.

This module is where ENG-437's indistinguishability is deliberately half-reversed, so the
split is worth stating in one place.

**The three code states become distinguishable.** ENG-437 collapsed unknown, spent and
expired into one answer because its caller was anyone at all, and a caller who can tell
them apart can enumerate live codes. This caller is an authenticated facilitator standing
in a room, and the three refusals ask for three different things — retype, go find the
device, make the tablet show a new code. A single generic failure sends them back to the
keyboard in all three, and in two the keyboard is not the answer (ENG-460).

**The team check stays indistinguishable.** Claiming into a project the caller does not
facilitate answers exactly like an unknown code — same status, same body, byte for byte.
Otherwise a facilitator could walk the project space by trying to claim into it and learn
which teams exist. A project that does not exist answers the same way for the same reason:
telling "not yours" from "no such thing" maps the installation just as well.

**Order matters, and not only for tidiness.** The team check runs *before* the code is
spent. Reversed, a claim aimed at someone else's team would burn a live code on its way to
being refused, and the facilitator would have to go make the tablet show a new one.

**The spend and the payment are one transaction.** ``claim_device`` is called with
``commit=False`` so the guarded write and the credential land together. Committed
separately, a failure between them would leave the row claimed with no credential: refused
as already used on the next attempt, and with nothing left that issues one. A transient
failure would permanently strand a tablet.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.device import ClaimedDevice
from app.services.device.claim_device import (
    ClaimRefusal,
    InvalidClaimCodeError,
    claim_device,
)
from app.services.device.credential import generate_device_credential, hash_device_credential
from app.services.project.can_access_project import can_access_project


def _refuse_without_naming_the_team() -> InvalidClaimCodeError:
    """The refusal for a team the caller does not facilitate, or that does not exist.

    Deliberately labelled as an unknown code. It is not one, and that is the point: the
    facilitator learns nothing about the project they named.
    """
    error = InvalidClaimCodeError()
    error.reason = ClaimRefusal.UNKNOWN_CODE
    return error


async def claim_device_as_facilitator(
    db: AsyncSession,
    *,
    user: User,
    code: str,
    project_id: str,
    label: str | None = None,
) -> ClaimedDevice:
    """Bind the device holding ``code`` to ``project_id`` and issue its credential.

    Returns the device together with the one and only copy of its credential. Raises
    ``InvalidClaimCodeError`` for every refusal; ``reason`` says which, and the caller is
    trusted to decide how much of that to pass on.

    The credential is minted here rather than in ``claim_device`` because ENG-437 stopped
    at "the code can be spent" on purpose. This is what spending pays for.
    """
    if not await can_access_project(db, user.id, project_id):
        raise _refuse_without_naming_the_team()

    device = await claim_device(db, code=code, project_id=project_id, commit=False)

    credential = generate_device_credential()
    device.credential_hash = hash_device_credential(credential)
    device.credential_issued_at = device.claimed_at
    if label is not None:
        device.label = label

    await db.commit()
    await db.refresh(device)

    return ClaimedDevice(device=device, credential=credential)
