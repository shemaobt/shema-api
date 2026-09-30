"""Shared dependencies for resource-request routers.

``CurrentUser`` gates on holding *any* role in the app — a grant, or since BE-19
(OBT-520) a live membership of a PME project, which is how the team holds ``equipe`` —
the two role aliases gate on a specific one, and the nine capability aliases gate on
what the product actually models. Capabilities are the ones routes should reach for: four of the
nine belong to more than one role, and ``require_role`` cannot say OR — guarding
``view_evaluation`` as ``MesaUser`` would refuse the Gestor, which is the whole of
that role's point. The table and the query behind them are
``app/services/resource_request/capabilities.py``; what lives here is the wiring.

Reading rides on ``edit_requests``, and which rows it reaches stays ``_scope.py``'s. BE-16's
OR with ``endorse_request`` left with the base leader's account (BE-23, OBT-535): the leader
reads through the endorsement link's public door (``endorse.py``) and holds no session here.

``APP_KEY`` is named here and nowhere else in the module, which is where every
other application in this repository keeps its own. The service layer takes it as
a parameter rather than re-declaring it, so the literal has one home even now that
the module has two halves.

The role keys are the ids of the frontend's ``capabilities.ts`` verbatim, and since BE-03
the pairing is no longer held by hand: ``capabilities.json`` is vendored from that file's own
emission and ``test_capabilities.py`` refuses a mismatch.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_role
from app.core.auth_middleware import get_current_user, oauth2_scheme
from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.resource_request import (
    LinkActor,
    enters_the_form,
    holds_capability,
    link_actor,
)
from app.services.resource_request.link_session import link_session_subject

APP_KEY = "resource-request-form"

Db = Annotated[AsyncSession, Depends(get_db)]


async def _app_member(user: Annotated[User, Depends(get_current_user)], db: Db) -> User:
    """The app's door: a grant here, **or a live membership of a PME project** (BE-19).

    It was ``require_app_access(APP_KEY)`` until OBT-520, which admits whoever holds a row in
    ``user_app_roles`` for this app. The team no longer does: GATE-04 D1 (OBT-519) made the
    team the members of a project in the PME, and ``20260928_rr08`` revokes the ``equipe``
    grants.

    **The rule is** ``enters_the_form``'s, not this door's: the handoff that opens the form from
    the PME asks the same question, and two copies of it are how the handoff came to refuse the
    member this door admits. What the door keeps is its trade, ``cached=True`` — the grants are
    read through the role cache (``auth_cache``, ENG-551), exactly as ``require_app_access``
    reads them, so this door and ``require_role`` behind ``MesaUser``/``GestorUser`` read the
    same thing, and the membership is asked only when there is no grant (PR #569, review).

    The refusal keeps ``require_app_access``'s wording, because what it tells an outsider has
    not changed.
    """
    if not await enters_the_form(db, user, APP_KEY, cached=True):
        raise AuthorizationError(
            f"You don't have access to the '{APP_KEY}' application. "
            "Please contact support to request access."
        )
    return user


CurrentUser = Annotated[User, Depends(_app_member)]
MesaUser = Annotated[User, require_role(APP_KEY, "mesa")]
GestorUser = Annotated[User, require_role(APP_KEY, "gestor")]


def require_capability(capability: str) -> Any:
    """Gate on one capability, resolved through the roles the account holds here.

    Chained behind ``CurrentUser`` rather than beside it, so an account with no role in
    this app is refused by the app gate with the message that names the app, and only a
    member gets as far as being asked what they may do.

    **A platform admin passes, as they pass the two guards above.** That is the
    installation's standing rule and not a hole this file punches: ``require_app_access``
    and ``require_role`` both return early on ``is_platform_admin``, so refusing here
    would make one route in this module stricter than the route beside it — and buy
    nothing, since a platform admin can grant themselves ``mesa`` with one call to
    ``grant_app_role``. The cost is real and lands on the tests: a negative test written
    per role **must not** use an admin account, or it passes for the wrong reason.
    """

    async def _check(user: CurrentUser, db: Db) -> User:
        if user.is_platform_admin:
            return user
        if not await holds_capability(db, user.id, APP_KEY, capability):
            raise AuthorizationError(f"Capability '{capability}' is required for this action.")
        return user

    return Depends(_check)


def reads_capability(capability: str) -> Any:
    """Whether the caller holds ``capability`` — a **fact handed to the handler**, never a
    door that refuses.

    The two guards above answer *may this person be here at all*; this one answers *how
    much of the answer is theirs to read*, on a route they already passed. It exists
    because ``fund_id`` on the request envelope has two audiences on one route: the
    Painel — ``manage_funds``, mesa and Gestor — reads which fund a card draws from, and
    the team reading its own row does not (GATE-03 D4). A second route for the same row
    would be an N+1 on the board; a second model would put the choice in the router.

    A platform admin reads it, for the same standing reason the guards admit them: an
    admin who wanted the value can grant themselves ``mesa`` with one call.

    It costs one ``list_roles`` beyond the guard's own, deliberately not shared with it:
    ``holds_capability`` reads the database on every call so a grant made mid-request is
    visible immediately, and threading a cache through here to save a small query would
    trade that property for the wrong half.
    """

    async def _reads(user: CurrentUser, db: Db) -> bool:
        if user.is_platform_admin:
            return True
        return await holds_capability(db, user.id, APP_KEY, capability)

    return Depends(_reads)


CanEditRequests = Annotated[User, require_capability("edit_requests")]
CanViewEvaluation = Annotated[User, require_capability("view_evaluation")]
CanEditEvaluation = Annotated[User, require_capability("edit_evaluation")]
CanManageFunds = Annotated[User, require_capability("manage_funds")]
CanMoveBoard = Annotated[User, require_capability("move_board")]
CanAssignFund = Annotated[User, require_capability("assign_fund")]
CanAllocateFunds = Annotated[User, require_capability("allocate_funds")]
CanAdministerFunds = Annotated[User, require_capability("administer_funds")]

ReadsFunds = Annotated[bool, reads_capability("manage_funds")]


def reader_with(*capabilities: str) -> Any:
    """Resolve the caller to **a user or a request link** — BE-26 (OBT-537), PR B.

    The subject resolver BE-01 foresaw: a bearer token that is a link session (``aud=rr_link``,
    ``link_session.py``) answers the link's ``LinkActor``, and the resolver refuses it with a
    401 once the link is revoked or expired; any other token takes the user path this module
    already had — the app's door (``_app_member``) and then any one of ``capabilities`` —
    unchanged. The route's signature does not change, only what its reader can be, and the
    service decides what each reaches (``read_as.py``).

    Only the reads a team makes take it today; the writes a link makes are PR C's.
    """

    async def _resolve(db: Db, token: str = Depends(oauth2_scheme)) -> User | LinkActor:
        link_id = link_session_subject(token)
        if link_id is not None:
            return await link_actor(db, link_id)

        from app.services import auth_service

        user = await _app_member(
            await auth_service.get_current_user_from_access_token(db, token), db
        )
        if user.is_platform_admin:
            return user
        for capability in capabilities:
            if await holds_capability(db, user.id, APP_KEY, capability):
                return user
        raise AuthorizationError(
            f"One of the capabilities {', '.join(capabilities)} is required for this action."
        )

    return Depends(_resolve)


RequestReader = Annotated[User | LinkActor, reader_with("edit_requests")]
TeamReader = Annotated[User | LinkActor, reader_with("edit_requests")]


async def _reader_reads_funds(reader: RequestReader, db: Db) -> bool:
    """``ReadsFunds`` for a route whose reader may be a link: a link never reads the fund."""
    if isinstance(reader, LinkActor):
        return False
    if reader.is_platform_admin:
        return True
    return await holds_capability(db, reader.id, APP_KEY, "manage_funds")


ReaderReadsFunds = Annotated[bool, Depends(_reader_reads_funds)]

#: The writes a request link makes (BE-26, OBT-537, PR C): start, save, submit, cancel. For an
#: account the guard is ``edit_requests``, exactly what ``CanEditRequests`` asked before.
TeamWriter = Annotated[User | LinkActor, reader_with("edit_requests")]


async def _writer_reads_funds(writer: TeamWriter, db: Db) -> bool:
    if isinstance(writer, LinkActor):
        return False
    if writer.is_platform_admin:
        return True
    return await holds_capability(db, writer.id, APP_KEY, "manage_funds")


WriterReadsFunds = Annotated[bool, Depends(_writer_reads_funds)]
