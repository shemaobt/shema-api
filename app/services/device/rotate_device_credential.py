"""Replacing a device's credential on the strength of the one it already holds.

A claim needs a facilitator, a code read off a screen, and someone standing next to the
tablet. If that were the only way to replace a credential, then "we think this one leaked"
would cost a trip to the room, and the honest answer to a suspected leak would be to do
nothing at all. So a device can trade a credential it holds for a fresh one, with no claim
and nobody in the room.

**The old credential is not retired here, and that is the design.** ``credential.py``
already argues the credential has no expiry because the room has no reliable network. The
same argument forbids a dry swap: the response carrying the new credential is exactly what
a bad network drops, and a device left holding a credential the server has already
forgotten is a room that stops until someone walks in with a claim code.

So the credential that was *presented* stays valid, and the new one joins it. The window
closes when the new credential is used — evidence the tablet received it — and not before.
``authenticate_device`` is what closes it.

Note which hash is kept: the one presented, not whatever was current. A device that rotates
twice because it never saw either answer is still holding its original credential, and that
is the one that must keep working. Keeping the *current* hash instead would retire the
credential in the tablet's hand in favour of one that only ever existed in a response
nobody received — the dry swap again, one step further along.
"""

from app.db.models.device import Device
from app.services.device.credential import generate_device_credential, hash_device_credential


def rotate_device_credential(device: Device, *, presented: str) -> str:
    """Issue ``device`` a new credential and return it. Does not commit.

    ``presented`` is the credential the caller authenticated with; it keeps working until
    the returned one is used.
    """
    issued = generate_device_credential()
    device.previous_credential_hash = hash_device_credential(presented)
    device.credential_hash = hash_device_credential(issued)
    return issued
