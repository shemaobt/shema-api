"""The one reading of a token's state.

``revoked > expired > used > pending`` — the leader link's order (BE-12), and each step is
deliberate:

* **Revoked first.** A token somebody took back must not later present itself as merely
  expired: *the door a person walked through must not later present itself as merely
  expired*, in ``app/services/resource_request_access/_invite_status.py``'s words.
* **Expired before used.** On a multi-use link ``used_at`` records the first answer, not the
  end of the link's life, so a link whose clock ran out is dead whether or not it was ever
  answered.

The access invite reads the other way — ``used`` before ``expired``, because for a single-use
token acceptance *is* the end, and an accepted invite should still read as accepted after its
clock runs out. That is one of the two reasons it is not read here yet (``docs/shema.md``
§6.7): whoever moves it decides that order first.
"""

from datetime import datetime
from typing import Literal, Protocol

from app.utils.stored_time import as_utc

TokenStatus = Literal["revoked", "expired", "used", "pending"]


class TokenRow(Protocol):
    """What :func:`status` reads, and the whole of it.

    Structural rather than a base class: each purpose keeps its own table, and giving them a
    common parent to satisfy a type checker would put a mapped inheritance in the schema to
    express a fact about a predicate — the argument ``_media_sharing.Authorizable`` makes.

    **``expires_at`` is not optional.** A token with no expiry has no state here, which is the
    failure this module exists to prevent. **``used_at`` is the only name read**: the invite's
    ``accepted_at`` is the same moment under another name, and it is not accepted until the
    invite moves and decides its order.
    """

    expires_at: datetime
    revoked_at: datetime | None
    used_at: datetime | None


def status(row: TokenRow, now: datetime) -> TokenStatus:
    """The state of ``row`` at ``now``, by the order above.

    Pure: the caller brings the clock. A token is dead at the instant its clock reaches, and
    the stored moment is read through ``as_utc`` because SQLite hands it back naive.
    """
    if row.revoked_at is not None:
        return "revoked"
    if as_utc(row.expires_at) <= now:
        return "expired"
    if row.used_at is not None:
        return "used"
    return "pending"
