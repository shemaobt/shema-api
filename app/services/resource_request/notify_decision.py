"""The team is told its decision — in-app now, by e-mail once the decision has committed."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRDecision, RRRequest
from app.services.notifications.create_notification import create_notification
from app.services.notifications.get_rr_app_id import get_rr_app_id
from app.services.resource_request._notices import (
    Letter,
    letter,
    product_name,
    request_name,
)

EVENT_TYPE = "rr_decision"

#: Title and sentence per decision — all four, because all four are told. GATE-03 D5, and
#: the client's own words on 28/aug/2026: *"as quatro decisões"*. Telling only the approved
#: team would be telling exactly the one that has nothing left to do, while the team whose
#: request needs a revision — the case the whole flow assumes comes back — would hear
#: nothing at all.
DECISION_COPY: dict[RRDecision, tuple[str, str]] = {
    RRDecision.APPROVED: (
        "Your request was approved",
        "has been approved by the Resource Circle.",
    ),
    RRDecision.CONDITIONAL: (
        "Your request was approved with conditions",
        "has been approved with conditions by the Resource Circle.",
    ),
    RRDecision.REVISE: (
        "Your request needs a revision",
        "has been reviewed by the Resource Circle, which asks for a revision before deciding.",
    ),
    RRDecision.DECLINED: (
        "Your request was not approved",
        "has been reviewed by the Resource Circle and was not approved.",
    ),
}

#: The two decisions whose notice carries the mesa's note to the team. On the other two
#: there is nothing for the team to act on, and ``team_note`` is the only text the mesa
#: writes that a team may read at all — ``comments`` and the ata never leave the mesa
#: (GATE-03 D4).
CARRY_NOTE: frozenset[RRDecision] = frozenset({RRDecision.REVISE, RRDecision.CONDITIONAL})


def _note(decision: RRDecision, team_note: str | None) -> str | None:
    """The note as it goes into a notice, or nothing at all.

    An empty ``team_note`` must not become an empty notice: a message whose body ends in a
    heading with no words under it reads as a mesa that forgot to write, which is worse
    than a message that simply says the decision. Blank, whitespace and ``None`` are one
    case here, and so is a note on a decision that does not carry one.
    """
    if decision not in CARRY_NOTE or team_note is None:
        return None
    stripped = team_note.strip()
    return stripped or None


async def notify_decision(
    db: AsyncSession,
    *,
    request: RRRequest,
    decision: RRDecision,
    team_note: str | None,
    actor_id: str,
) -> list[Letter]:
    """Write the team's in-app notice; hand back the letter for after the commit.

    **The trigger is this call site and no other.** It is made from ``save_evaluation``,
    where the decision is written — never from ``transition_stage`` or ``move_request``,
    where a card moves. GATE-02 D6 made the two coincide in time (recording a decision
    moves the card), and that is exactly where the distinction is easiest to lose: a
    decision implies a column, a column never implies a decision. A card dragged by hand
    tells nobody anything, and ``test_notifications.py`` says so in a test of its own.

    The in-app row is staged inside the caller's transaction — ``commit=False``, the flag
    BE-13 added to ``create_notification`` — so the notice and the decision land together
    or not at all. The e-mail is a value handed back: the caller commits, then posts it.
    """
    app_id = await get_rr_app_id(db)
    team = await db.get(User, request.created_by)
    if team is None:
        return []

    title, sentence = DECISION_COPY[decision]
    name = request_name(request)
    note = _note(decision, team_note)

    body = f"{name} {sentence}"
    if note is not None:
        body = f"{body}\n\n{note}"

    await create_notification(
        db,
        user_id=team.id,
        app_id=app_id,
        event_type=EVENT_TYPE,
        title=title,
        body=body,
        actor_id=actor_id,
        commit=False,
    )

    return [
        letter(
            to=team.email,
            subject=title,
            template="rr_decision.html.jinja",
            app_name=await product_name(db, app_id),
            greeting=team.display_name or team.email,
            request_name=name,
            sentence=sentence,
            team_note=note,
        )
    ]
