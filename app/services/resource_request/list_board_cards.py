"""The Painel's cards in one read — OBT-667 (RRF-MESA-084), the request half of the board.

``GET /requests`` serves the spine with ``document: {}`` on purpose (§4.2: a listing never
drags the 45 answers it does not show), and the Painel's card draws five of those answers —
A0's name, the solicitante, the language, the people and item 9's amount. So the form read
``GET /requests/{id}`` once per card to get them: 73 cards, 73 calls, on the 29/out bench.
This is the same five answers for every card the caller reaches, in **two statements whatever
the number of cards**: the spine through ``list_requests`` — the scope every list in this module
already applies — and the sections of all those ids in one ``IN``.

**Nothing new is disclosed.** Who reaches this read holds ``manage_funds`` (the route's guard —
the mesa and the Gestor, the Painel's own readers), and each of them already reads every one of
these answers through ``GET /requests/{id}``. What changes is the number of calls, not who
reads what. The team is refused at the door, so ``lang_name`` and ``people_name`` never reach a
projection the team or the PME's coordinators read: ``RequestCardOut`` is untouched, because a
language and a people on *that* card would have to pass the sensitive-project rule the PME
applies to a location, and this read is not read by the PME.

**An answer the sections do not carry is ``""``, never a missing card.** ``document()`` reads
the same way (``content.get("fields", {})``), and a request whose sections row is missing — a
dump restored mid-write — still has a spine, so it still has a card.
"""

from collections.abc import Iterable
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest, RRRequestSections
from app.services.resource_request.list_requests import list_requests


class BoardCard(NamedTuple):
    """One card: the spine row and the two card answers that are not spine columns — the
    language and the people live in the sections document; the rest ride on ``RRRequest``."""

    request: RRRequest
    lang_name: str
    people_name: str


def _answer(fields: dict[str, Any], key: str) -> str:
    value = fields.get(key)
    return value if isinstance(value, str) else ""


async def _section_answers(db: AsyncSession, ids: Iterable[str]) -> dict[str, tuple[str, str]]:
    wanted = list(ids)
    if not wanted:
        return {}
    rows = await db.execute(
        select(RRRequestSections.request_id, RRRequestSections.content).where(
            RRRequestSections.request_id.in_(wanted)
        )
    )
    answers: dict[str, tuple[str, str]] = {}
    for request_id, content in rows.tuples().all():
        fields = dict((content or {}).get("fields", {}))
        answers[request_id] = (_answer(fields, "lang_name"), _answer(fields, "people_name"))
    return answers


async def list_board_cards(db: AsyncSession, user: User, app_key: str) -> list[BoardCard]:
    """Every request this caller reaches, as the Painel's card — ``list_requests``' rows and
    order, each with its language and people, from one sections statement for all of them."""
    rows = await list_requests(db, user, app_key)
    answers = await _section_answers(db, (row.id for row in rows))
    return [BoardCard(row, *answers.get(row.id, ("", ""))) for row in rows]
