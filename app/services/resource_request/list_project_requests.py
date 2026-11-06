from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.db.models.shema import ShemaProject
from app.models.shema_privacy import ShemaReader
from app.services.resource_request._cards import CardFacts, cards_of
from app.services.resource_request._editing import Editing
from app.services.resource_request._membership import granted_roles, is_member_of
from app.services.shema._redaction import language_name_for, reads_the_truth
from app.services.shema._scope import (
    ADMIN_ROLE,
    GESTOR_ROLE,
    MESA_ROLE,
    reaches,
    readership,
    refuse_out_of_scope,
    scope_from_roles,
)
from app.services.shema._scope import granted_roles as shema_granted_roles
from app.utils.shema_printed_names import printed_name

#: The form's roles that reach every project: they already reach the whole board.
_BOARD_ROLES = frozenset({ADMIN_ROLE, MESA_ROLE, GESTOR_ROLE})

#: The language the generic name is printed in. The PME prints in the language its header names
#: (``X-Shema-Language``, a dependency of the Shemá router this route does not carry); this
#: module's own text is Portuguese, so the card's is too.
PRINTED_IN = "pt-BR"


async def list_project_requests(
    db: AsyncSession, project_id: str, user: User, app_key: str, shema_app_key: str
) -> list[CardFacts]:
    """The requests of one PME project, as cards — BE-24 (OBT-536).

    What the PME's project page draws (OBT-544): each request and where it is, and the open
    instance if there is one, so the *Solicitar recurso* button knows whether to say
    *Iniciar* or *em preenchimento por X*. Cancelled instances are not listed, as in
    ``list_requests``.

    **Who reads it** — the issue's guard, read across the two apps the PME session carries
    (OBT-523):

    * the platform admin, and ``admin``, ``mesa`` or ``gestor`` in either app — the Admin of
      OBT-522 is one role seeded in both, and the mesa and the Gestor already reach the whole
      board;
    * a regional role of the PME whose scope reaches the project's region — ``region_scope``'s
      rule, read through ``scope_from_roles`` so the grants are read once;
    * a live member of the project (OBT-524).

    **Everyone else gets 404**, a missing project included — the Shemá module's convention,
    because a 403 would confirm that a project the caller may not see exists. The refusal is
    logged through ``refuse_out_of_scope`` so it reads like every other scoped miss in the PME.

    **Who reads the cards whole, and who reads them redacted** (OBT-688, A-02 of INT-12 —
    Daniel, 6/nov/2026: redact, do not refuse). ``reg_name`` is the A0 the team typed and in
    practice names the language; ``started_by_name`` is a person. On a project whose place is
    withheld (``sensitive_country``, read through ``_redaction.is_withheld`` by way of
    ``reads_the_truth``) both leave whole only to the readers above who read the truth: the
    board roles and the platform admin — who read the whole request anyway (OBT-571,
    OBT-568) — a live member, and a PME reader the project's region makes ``coordination`` or
    ``trusted`` (``Readership.reader_of``, the same rule the PME's record applies). Whoever
    reaches the project and reads it as ``other`` — the OBT Lab, by Daniel's decision of
    7/oct/2026 — gets every card with the stage, the decision, the amount, the instance's
    ``open`` and ``can_edit`` intact, the A0 replaced by the name the PME prints for that
    project (the public name coordination registered, else *Projeto sensível — <região>*,
    ``shema_printed_names``), and no starter. A project that is not sensitive changes nothing.

    The route asks for a session and nothing else: this module's own door (``_app_member``)
    would refuse a regional coordinator who holds no role in the form, and that coordinator is
    exactly who this read is for.
    """
    form_granted = await granted_roles(db, user.id, app_key)
    shema_granted = await shema_granted_roles(db, user.id, shema_app_key)
    scope = await scope_from_roles(db, user, shema_granted)

    project = await db.get(ShemaProject, project_id)
    if project is None:
        raise refuse_out_of_scope(
            scope, user=user, operation="resource_request_cards", project_id=project_id
        )

    board = (
        user.is_platform_admin
        or bool(form_granted & _BOARD_ROLES)
        or bool(shema_granted & _BOARD_ROLES)
    )
    reader = readership(scope, shema_granted, platform_admin=user.is_platform_admin).reader_of(
        project.region_key
    )
    in_region = board or reaches(scope, project.region_key)
    truth = board or reads_the_truth(project, reader)
    # The membership is asked only when nothing else settles both questions — who reaches the
    # project, and who reads it whole — so a board role or a coordinator pays no query for it.
    member = not (in_region and truth) and await is_member_of(db, user.id, project_id)
    if not (in_region or member):
        raise refuse_out_of_scope(
            scope, user=user, operation="resource_request_cards", project_id=project_id
        )

    rows = await db.execute(
        select(RRRequest)
        .where(RRRequest.shema_project_id == project_id, RRRequest.cancelled_at.is_(None))
        .order_by(RRRequest.created_at.desc())
    )
    editing = Editing(user_id=user.id, admin=user.is_platform_admin or ADMIN_ROLE in form_granted)
    facts = await cards_of(db, list(rows.scalars().all()), editing)
    if truth or member:
        return facts
    return _as_read_by_other(facts, project, reader)


def _as_read_by_other(
    facts: list[CardFacts], project: ShemaProject, reader: ShemaReader
) -> list[CardFacts]:
    """The cards of a withheld project for a reader of the region rather than the place.

    The name is the one the PME prints that reader on the ficha and the list (OBT-560, OBT-657):
    ``language_name_for`` answers the public name coordination registered or the region key,
    and ``printed_name`` turns the key into words. The starter is dropped: a name is a person.
    Everything else on the card is the journey, which the reader may follow.
    """
    name = printed_name(language_name_for(project, reader), withheld=True, language=PRINTED_IN)
    return [fact._replace(reg_name=name, started_by_name=None) for fact in facts]
