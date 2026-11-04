"""The invitation's two doors — the module's third deliberate hole (OBT-683).

The Admin invites somebody with no account (``access.py``, OBT-543), and the letter carries the
PME's ``/convite?token=…``. That page reads the invitation before the person has an account —
the ``GET``, with no ``Authorization`` at all — and accepts it once they have signed up or in
with the invited address — the ``POST``, open to **any signed-in account**, because an invitee
holds no role in either app until this call grants one. So neither sits under
``authenticated`` (the app gate) nor behind the door (``DOOR``, which wants a role already held).
**The token is the guard, and the guard is a service function**, as the intake's and the exit
link's are.

**Moved, not rewritten.** The two answered under ``/api/resource-requests/access`` until OBT-683,
long after the Admin's surface had moved here; they keep that contract — the same shapes,
snake_case as the form wrote them, and the same refusals — because they declare the same
response models and call the same two services, ``describe_invite`` and ``accept_invite``, which
stay in the form's invite package beside ``invite_store``, the store this module already
composes (``docs/shema.md`` §2.6). The form's two routes keep answering, through the same
functions, until the PR that removes them, in the merge order the form's owner agrees (§6.10).

**No rate limit**, unlike the intake and the exit link: the form's doors had none, and a 429 would
be a new answer on a move that changes the path and nothing else. **No cache keeps either
answer**: the outer router's ``NO_STORE`` writes ``private, no-store`` on both, as on every route
of the module — the one header the form's doors did not send.

Included into the outer router on a named line in ``app/api/shema/__init__.py``. The lookup is
listed in ``UNAUTHENTICATED_PATHS`` (``tests/shema_harness.py``) and the acceptance in
``SIGNED_IN_ROUTES`` (``tests/test_shema/test_access.py``), so another door of either kind is an
edit somebody reads.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.shema._deps import Db, SignedIn
from app.models.resource_request_access import AccessGrantResponse, InviteDescriptionResponse
from app.services.resource_request_access import accept_invite, describe_invite

router = APIRouter()

_INVITATION = "/access/invites/{token}"


@router.get(_INVITATION, response_model=InviteDescriptionResponse)
async def read_invitation(token: str, db: Db) -> InviteDescriptionResponse:
    """What the link gives and whether its address has an account — never the token back."""
    return await describe_invite(db, token)


@router.post(f"{_INVITATION}/accept", response_model=AccessGrantResponse)
async def accept_invitation(token: str, actor: SignedIn, db: Db) -> AccessGrantResponse:
    """Spend the invitation on the signed-in account that holds the invited address."""
    return await accept_invite(db, actor, token)
