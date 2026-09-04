from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.device import Device
from app.utils.stored_time import as_utc


@dataclass(frozen=True)
class MintedDevice:
    """A newly created device together with the one and only copy of its claim code.

    The code is returned here and nowhere else: the row keeps a hash, so this object is
    the single moment the plaintext exists. Whatever receives it is responsible for
    putting it on the tablet's screen and then forgetting it.
    """

    device: Device
    claim_code: str


@dataclass(frozen=True)
class ClaimedDevice:
    """A just-claimed device together with the one and only copy of its credential.

    Same discipline as ``MintedDevice``: the row keeps a hash, so this object is the single
    moment the plaintext exists, and whatever receives it must put it on the wire once and
    forget it.
    """

    device: Device
    credential: str


class DeviceClaimRequest(BaseModel):
    """What the Desk sends: the code on the screen, the team, and an optional human note."""

    code: str = Field(min_length=1, max_length=32)
    project_id: str = Field(min_length=1, max_length=36)
    label: str | None = Field(default=None, max_length=120)


class DeviceClaimResponse(BaseModel):
    """The answer to a successful claim. The only time the credential is ever on the wire."""

    device_id: str
    project_id: str
    label: str | None
    credential: str


class DeviceSelfResponse(BaseModel):
    """What a device may read about itself. Carries no credential, by construction."""

    device_id: str
    project_id: str | None
    label: str | None


#: The machine-readable reasons the Desk switches on (ENG-460). They ride in the standard
#: ``code`` field of this API's error body, which is what already tells error shapes apart
#: elsewhere — see ``UnknownReferenceError`` in ``app/core/exceptions.py``.
#:
#: There are three, not four: a team the caller does not facilitate is reported as
#: ``CLAIM_CODE_UNKNOWN``, and so is a project that does not exist. Adding a fourth for
#: them is exactly the enumeration the issue forbids.
ERROR_CODE_CLAIM_CODE_UNKNOWN = "CLAIM_CODE_UNKNOWN"
ERROR_CODE_CLAIM_CODE_ALREADY_USED = "CLAIM_CODE_ALREADY_USED"
ERROR_CODE_CLAIM_CODE_EXPIRED = "CLAIM_CODE_EXPIRED"


class TeamDeviceResponse(BaseModel):
    """One row of the Desk's devices panel.

    Descriptive, not a credential list: it exists so a facilitator can say "that one is
    so-and-so's" while looking at the screen. Nothing here is secret, and nothing here
    can be presented to the API as proof of anything.
    """

    device_id: str
    label: str | None
    linked_at: datetime | None
    last_seen_at: datetime | None
    #: When this tablet said it needs a person and the room has not started again since
    #: (ENG-624), or null. Additive: the Desk's reader takes the fields it knows off the row
    #: and ignores the rest, so this is served before anything draws it.
    needs_person_since: datetime | None = None

    @classmethod
    def of(cls, device: Device) -> "TeamDeviceResponse":
        """One row, built the same way wherever it is answered from.

        Every moment goes through `as_utc` because `DateTime(timezone=True)` reads back naive on
        SQLite, and a naive value serialises with no offset. Bare, the digits are read as local
        by whoever receives them — near midnight that moves the **day**, so the panel would
        date a tablet's last activity to a day it was not used.
        """
        return cls(
            device_id=device.id,
            label=device.label,
            linked_at=as_utc(device.claimed_at) if device.claimed_at else None,
            last_seen_at=as_utc(device.last_seen_at) if device.last_seen_at else None,
            needs_person_since=(
                as_utc(device.needs_person_since) if device.needs_person_since else None
            ),
        )


class RoomDeviceCodeRequest(BaseModel):
    """What a tablet sends when it already has a device row and only needs a live code.

    Absent on the very first run, and present from then on: a tablet that keeps asking
    without naming itself would leave a fresh unclaimed device behind every fifteen
    minutes it sat on a table waiting for someone.
    """

    device_id: str | None = Field(default=None, max_length=36)


class RoomDeviceCodeResponse(BaseModel):
    """The code a tablet puts on its screen, and the device it was drawn for.

    The plaintext code exists here and in ``MintedDevice`` and nowhere else — the row keeps
    a hash — so this is the one moment it can be shown to anybody.
    """

    device_id: str
    code: str
    expires_at: datetime

    @classmethod
    def of(cls, device: Device, code: str) -> "RoomDeviceCodeResponse":
        """The answer, with the expiry read the way `TeamDeviceResponse.of` reads its moments.

        `as_utc` for the same reason it is used there: `DateTime(timezone=True)` reads back
        naive on SQLite, and a tablet deciding when to draw a fresh code off a bare digit
        string would read it as local time and sit on a dead code for hours.
        """
        return cls(
            device_id=device.id,
            code=code,
            expires_at=as_utc(device.claim_code_expires_at),
        )


class RoomDeviceLinkResponse(BaseModel):
    """The team a tablet was linked to. Carries no credential, like ``DeviceSelfResponse``."""

    project_id: str
    label: str | None


class DeviceLabelUpdateRequest(BaseModel):
    """The who-uses-it note. Free text, stored verbatim, empty allowed."""

    label: str = Field(max_length=120)


class DeviceCredentialResponse(BaseModel):
    """A credential a device just received, returned once and never stored in the clear.

    Two routes answer with this and both mint the string they carry: the tablet collecting
    its first credential (ENG-622) and a device trading the one it holds for a fresh one.
    Same discipline as ``DeviceClaimResponse`` either way — this object and the device's own
    memory are the only places the string exists.
    """

    device_id: str
    credential: str


class DeviceNeedsPersonResponse(BaseModel):
    """What a tablet gets back when it says it needs a person.

    The moment is the one the halt was *first* recorded at, not the moment of this call. A
    tablet retrying over a room's network gets the same answer every time, which is what
    makes the retry free and what keeps the facilitator's queue aging honestly.
    """

    device_id: str
    needs_person_since: datetime
