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
    #: Whether a letter left: an installation with no ``app_url`` has nowhere to point one.
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

    Refused for a request not submitted (no link exists before the form is complete) and for
    one already endorsed (a spent link is not reissued).
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

    letter = await issue_endorsement(db, request)
    await db.commit()
    await db.refresh(request)
    if letter is not None:
        await post([letter])
    return Resent(request=request, sent=letter is not None)
