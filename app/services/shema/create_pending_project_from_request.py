"""The mesa approves a request that came by the Admin's link, and the PME gains a project (OBT-547).

Karina, 25/set: *"se o projeto for aprovado pela mesa ele é cadastrado sim, os membros também"*;
Daniel, 25/set: *"sim, o admin confere antes"*. So the approval files a project **pending
confirmation** — built from the form's Parte A by ``_filing.part_a`` — and the list of people it
proposes, and the Admin confirms or discards it (``confirm_project``, ``reject_pending_project``).
Until then nobody reads it: ``_scope.registered`` keeps it out of every statement a reader starts
from.

**Called from the decision's transaction, and only there.** ``save_evaluation`` calls this when it
records ``approved`` on a request with a link and no project, beside the ledger movement and the
notices, and it commits all of them once — so a decision that rolls back files nothing, and a
project is never filed for a decision that did not happen. ``conditional`` does not file: it is not
``approved``, and it moves no money either. The caller hands over values — the frozen document the
mesa evaluated, the request's id, the link's id — and this file imports no service of the form's
module (``_request_notices.py``'s reason: that module imports this one).

**Idempotent, in the order the questions are cheapest to answer:**

1. a request that already filed a project files nothing — whatever became of it;
2. a link that already has a live project — pending or confirmed, not discarded — files nothing
   either: the team is one team however many requests it sends. If that project is confirmed,
   the request is stamped with it now, since the project it belongs to exists; if it is still
   pending, the confirmation stamps every request of the link;
3. otherwise the project is filed.

``uq_shema_projects_source_request`` and ``uq_shema_projects_live_source_link`` hold the same two
rules against a race: a second approval that slipped past the reads fails at the flush, inside
the transaction of its decision, and leaves nothing half-written.

**The id is minted, a UUID** — what the PME itself mints for a record born in the product (the
ficha's ``promote``). The export's slugs are ``<language>-<place>``, and the language and the place
here are the team's own typing, which the Admin is about to correct.

**Born** ``planejado`` **and not sensitive**, as the issue writes it: the form asks no such thing,
and the flag is the Admin's decision at the conference, where the confirmation requires it. The
region is derived from the place by the one owner of that map (``_redaction.derive_region``).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRRequestLink
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaProjectStatus
from app.db.models.shema_pending_member import ShemaProjectPendingMember
from app.services.shema._filing import part_a, stamp_request
from app.services.shema._redaction import derive_region
from app.services.shema._scope import filed_projects, live_project_of_link

logger = logging.getLogger(__name__)


async def create_pending_project_from_request(
    db: AsyncSession, document: Mapping[str, Any], *, request_id: str, link_id: str
) -> ShemaProject | None:
    """File the project an approved link request carries, or find the one already filed.

    Staged and never committed: the decision's transaction owns the commit. Answers the project
    the request now leads to — filed here or before — or ``None`` when the link's project was
    discarded and this request is the one that filed it.
    """
    already = (
        await db.execute(filed_projects().where(ShemaProject.source_request_id == request_id))
    ).scalar_one_or_none()
    if already is not None:
        return None if already.discarded_at is not None else already

    live = (await db.execute(live_project_of_link(link_id))).scalar_one_or_none()
    if live is not None:
        if not live.pending_confirmation:
            await stamp_request(db, request_id, live.id)
        return live

    link = await db.get(RRRequestLink, link_id)
    seed = part_a(document, link_email=link.email if link is not None else "")
    project = ShemaProject(
        id=str(uuid.uuid4()),
        language_name=seed.language_name,
        language_code=seed.language_code,
        location=seed.place,
        status=ShemaProjectStatus.PLANEJADO,
        sensitive_country=False,
        pending_confirmation=True,
        source_request_id=request_id,
        source_link_id=link_id,
    )
    project.region_key = derive_region(project)
    db.add(project)
    await db.flush()

    db.add_all(
        ShemaProjectPendingMember(
            project_id=project.id,
            position=position,
            name=member.name,
            role=member.role,
            email=member.email,
        )
        for position, member in enumerate(seed.members)
    )
    await db.flush()

    logger.info(
        "shema project filed by an approval, pending confirmation",
        extra={
            "shema_operation": "create_pending_project_from_request",
            "shema_project_id": project.id,
            "shema_request_id": request_id,
            "shema_link_id": link_id,
        },
    )
    return project
