from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.device import Device


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

    @classmethod
    def of(cls, device: Device) -> "TeamDeviceResponse":
        """One row, built the same way wherever it is answered from."""
        return cls(
            device_id=device.id,
            label=device.label,
            linked_at=device.claimed_at,
            last_seen_at=device.last_seen_at,
        )


class DeviceLabelUpdateRequest(BaseModel):
    """The who-uses-it note. Free text, stored verbatim, empty allowed."""

    label: str = Field(max_length=120)


class DeviceCredentialResponse(BaseModel):
    """A freshly rotated credential, returned once and never stored in the clear.

    Same discipline as ``DeviceClaimResponse``: this object and the device's own memory are
    the only places the string exists.
    """

    device_id: str
    credential: str
