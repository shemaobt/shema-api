from dataclasses import dataclass

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
