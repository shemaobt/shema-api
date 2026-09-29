from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, UnknownReferenceError, UnprocessableValueError
from app.db.models.auth import User
from app.db.models.resource_request import RRBudgetLine, RRRequest, RRRequestSections
from app.db.models.shema import ShemaProject
from app.models.resource_request import RequestDraftIn
from app.services.resource_request._document import split
from app.services.resource_request._instance import flush_the_instance, refuse_a_second_open
from app.services.resource_request._link_actor import LinkActor
from app.services.resource_request._membership import is_member_of, member_project_ids
from app.services.resource_request._scope import reach


async def _project_for(
    db: AsyncSession, user: User, app_key: str, project_id: str | None
) -> str | None:
    """The project the new request belongs to — GATE-04 D1 (OBT-519), BE-19 (OBT-520).

    **A member opens a request from one of their projects, and nothing else.** The PME's
    pass code (OBT-527) hands the form that project, but the server keeps no context in the
    session, so the project arrives as a parameter of the creation and is **checked against
    the caller's live memberships** — that check is what makes it theirs rather than a claim.
    Never read from the document body: ``RequestDraftIn`` forbids extra keys, and the body
    is the document.

    **A member of exactly one project may leave it unsaid**, and that project is stamped:
    it is the only one the request could belong to, and it is what the pass code would have
    carried. A member of several must say which — guessing between two of their own projects
    would file a request under a team that never opened it.

    A caller whose reach is the whole board — the mesa, the Gestor, the platform admin —
    may open a request with no project (FE-41 gave the Gestor that door back) or name any
    project that exists. Anyone else must name a project they belong to: a request with no
    project would be reachable by its author alone, which is the account-shaped team GATE-04
    retired.
    """
    reaches = await reach(db, user, app_key)
    if project_id is None:
        if reaches.every:
            return None
        memberships = list((await db.execute(member_project_ids(user.id).limit(2))).scalars())
        if len(memberships) == 1:
            return memberships[0]
        raise UnprocessableValueError(
            "A request opens from a project you are a member of: send its project_id."
        )
    if await is_member_of(db, user.id, project_id):
        return project_id
    if not reaches.every:
        raise AuthorizationError("You are not a member of that project.")
    if await db.get(ShemaProject, project_id) is None:
        raise UnknownReferenceError(f"Unknown project: {project_id}")
    return project_id


async def _instance_of_link(
    db: AsyncSession, actor: LinkActor, project_id: str | None, spine: dict[str, Any]
) -> RRRequest:
    """The instance a request link starts — BE-26 (OBT-537).

    **Bound to the link and to no project**: a request is born with a project or with a link,
    never both, and the mesa's approval is what gives it a project later (OBT-547). Naming a
    project from a link is refused rather than ignored, because silently dropping it would let
    a caller believe the request was filed there.

    ``created_by`` is the Admin who issued the link — the column is ``NOT NULL`` and a link is
    no person — and ``started_by`` is empty: ``started_by_link_id`` holds the pen. Who *typed*
    is the link, and the trail says so (``_writer.trail_author``); who is *filed under* is the
    Admin, which is only the scope's bookkeeping.
    """
    if project_id is not None:
        raise UnprocessableValueError("A request link opens a request of its own, with no project.")
    await refuse_a_second_open(db, None, link_id=actor.link.id)
    return RRRequest(
        **spine,
        created_by=actor.link.created_by,
        request_link_id=actor.link.id,
        started_by_link_id=actor.link.id,
    )


async def create_draft(
    db: AsyncSession,
    draft: RequestDraftIn,
    user: User | LinkActor,
    app_key: str,
    project_id: str | None = None,
) -> RRRequest:
    """Open a request on the server, owned by the session that opened it.

    The author comes from the bearer token and never from the payload, and so does the
    right to the project (``_project_for``). GATE-02 D1 made
    that possible by answering that everyone has an account — the design's §5.2 named the
    cost of the other answer, an author with no stable identity, and it is the reason
    ``created_by`` is nullable in the schema and non-null in practice.

    ``stage`` is left to the column's own default, ``triagem``. A request that has not been
    submitted is not on the board yet, and giving it a stage here would be this service
    deciding something BE-08 owns.

    **Opening a request is starting the project's instance** (BE-25, OBT-534): the caller
    becomes ``started_by`` — the one member who writes it until it is submitted or cancelled —
    and a project that already has an open one refuses a second with 409 (``_instance.py``).
    ``POST /requests/start`` and ``POST /requests`` both land here, so the lock cannot be
    stepped around by choosing the older door.
    """
    parts = split(draft)
    if isinstance(user, LinkActor):
        request = await _instance_of_link(db, user, project_id, parts.spine)
    else:
        project = await _project_for(db, user, app_key, project_id)
        await refuse_a_second_open(db, project)
        request = RRRequest(
            **parts.spine, created_by=user.id, started_by=user.id, shema_project_id=project
        )
    db.add(request)
    await flush_the_instance(db)

    db.add(RRRequestSections(request_id=request.id, content=parts.sections))
    for line in parts.budget:
        db.add(RRBudgetLine(request_id=request.id, **line))

    await db.commit()
    await db.refresh(request)
    return request
