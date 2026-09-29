from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request._endorsement import issue_endorsement
from app.services.resource_request._links import require_link_admin
from app.services.resource_request._notices import post


class Resent(NamedTuple):
    request: RRRequest
    #: Whether the provider accepted the letter — false with no ``app_url`` to point one at, and
    #: false when the provider refused it.
    sent: bool


async def resend_endorsement(
    db: AsyncSession, request_id: str, user: User, app_key: str, shema_app_key: str
) -> Resent:
    """Revoke the live endorsement link and mail a fresh one — BE-23 (OBT-535), the Admin alone.

    For a leader who lost the e-mail, let the link run out, or spent five codes. **The address
    does not change here**: it is the one frozen with the submission, and a different leader is
    a revision (FE-47), not a resend. **Nothing secret comes back**: the token and the code go
    to the leader's address only — the Admin reading them would be one more person able to
    endorse a request that is not theirs to vouch for.

    Refused for a request not submitted (no link exists before the form is complete), for one
    already endorsed (a spent link is not reissued), and for one that names no leader — every
    request submitted before ``20260930_rr12`` carries an empty ``leader_email``, and a link
    addressed to nobody is not a resend (PR #579, review). ``sent`` is what the provider
    accepted, not whether a letter was built.
    """
    await require_link_admin(
        db, user, app_key, shema_app_key, refusal="Only the Admin resends an endorsement link."
    )
    request = await db.get(RRRequest, request_id)
    if request is None:
        raise NotFoundError("Resource request not found")
    if request.submitted_at is None:
        raise ConflictError("The endorsement link is issued at submission; this is a draft.")
    if request.endorsed_at is not None:
        raise ConflictError("This request was already endorsed.")
    if not request.leader_email:
        raise ConflictError(
            "This request names no base leader: it was submitted before the address was asked "
            "for. A revision is how the team gives one."
        )

    letter = await issue_endorsement(db, request)
    await db.commit()
    await db.refresh(request)
    accepted = await post([letter]) if letter is not None else 0
    return Resent(request=request, sent=accepted > 0)
