"""One reading of an invite's state, shared by lookup, acceptance and listing.

Precedence is deliberate: a revoked invite stays revoked even after its clock
runs out, and a used one stays used — the door a person walked through must not
later present itself as merely expired.
"""

from datetime import UTC, datetime

from app.db.models.auth import AccessInvite
from app.models.resource_request_access import InviteStatus
from app.utils.stored_time import as_utc


def invite_status(invite: AccessInvite) -> InviteStatus:
    if invite.revoked_at is not None:
        return "revoked"
    if invite.accepted_at is not None:
        return "used"
    if as_utc(invite.expires_at) <= datetime.now(UTC):
        return "expired"
    return "pending"
