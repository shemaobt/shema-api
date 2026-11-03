"""What a case about a halt and the Desk's visit to it needs before it can ask.

The facilitators and their teams, the tablet halting through its own door, a warning raised by
a stretch told until it is hard, and the Desk's two reads and two writes. A write the case does
not name a halt count for names the one the Desk would read, so a case that is not about the
count keeps meaning "the Desk names what it saw". Builders and constants only: each module
keeps its own fixtures.
"""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRTakeKind
from app.services.internalization_room import sessions as room
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from tests.baker import (
    a_language,
    grant_facilitator_app_role,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.hard_stretch_harness import Facilitator, a_new_recording, row

IR = "/api/internalization-room"
DESK = "/api/facilitator/teams"
SESSIONS = "/api/facilitator/sessions"
DEVICE = "tablet-da-equipe-1"
P = "P03"


async def a_facilitator(db: AsyncSession, *, email: str, team_name: str) -> Facilitator:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=email)
    language = await a_language(db, name=f"Lingua {team_name}")
    project = await make_project(db, language.id, name=team_name)
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return Facilitator(
        user.id, project.id, {"Authorization": f"Bearer {access}"}, team_name=team_name
    )


async def a_session(db: AsyncSession, *, team_id: str):
    """A conversation the team has held: one turn lands unconditionally (ENG-964), so a case
    about attending or halting never meets a session without one."""
    session = await room.create_session(
        db,
        pericope=P,
        project_id=team_id,
    )
    return await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")


async def the_tablet_halts(client: httpx.AsyncClient, session_id: str) -> None:
    """The room in front of the team says it cannot go on without a person."""
    asked = await client.post(f"{IR}/sessions/{session_id}/needs-person")
    assert asked.status_code == 200, asked.text[:300]


async def tablet_state(client: httpx.AsyncClient, session_id: str) -> dict:
    answer = await client.get(f"{IR}/sessions/{session_id}")
    assert answer.status_code == 200, answer.text[:300]
    return answer.json()


async def the_queue(client: httpx.AsyncClient, who: Facilitator) -> list[dict]:
    listed = await client.get(f"{IR}/facilitator/sessions", headers=who.headers)
    assert listed.status_code == 200, listed.text[:300]
    return listed.json()["sessions"]


async def queued(client: httpx.AsyncClient, who: Facilitator, session_id: str) -> dict | None:
    return next(
        (row for row in await the_queue(client, who) if row["session_id"] == session_id), None
    )


async def history_row(client: httpx.AsyncClient, who: Facilitator, session_id: str) -> dict:
    answer = await client.get(f"{DESK}/{who.team_id}/sessions", headers=who.headers)
    assert answer.status_code == 200, answer.text[:300]
    return next(card for card in answer.json() if card["session_id"] == session_id)


async def desk_session_row(client: httpx.AsyncClient, who: Facilitator, session_id: str) -> dict:
    """The «Sessões» row the Desk reads for this session."""
    page = await client.get(SESSIONS, params={"team_id": who.team_id}, headers=who.headers)
    assert page.status_code == 200, page.text[:300]
    return next(row for row in page.json()["sessions"] if row["session_id"] == session_id)


#: Name what the Desk reads for the room right now, rather than a halt the case chose.
AS_THE_DESK_READS = "as the Desk reads"


async def the_halt_the_desk_reads(
    client: httpx.AsyncClient, who: Facilitator, session_id: str
) -> dict[str, int | str]:
    """The halt a visit names, off the session's «Sessões» row.

    Not the queue's: its ``warned_at`` is the standing warning's, null once a visit ended it,
    and a finished passage stays on the queue's Refine half with the visit standing.
    """
    row = await desk_session_row(client, who, session_id)
    return naming(row["halts_raised"], row["warned_at"])


def naming(halt: int | str | None, warning: str | None = None) -> dict[str, int | str]:
    """The query a visit sends; ``None`` leaves that parameter out."""
    named: dict[str, int | str] = {} if halt is None else {"halt": halt}
    return named | ({} if warning is None else {"warning": warning})


async def _named(
    client: httpx.AsyncClient,
    session_id: str,
    who: Facilitator,
    halt: int | str | None,
    warning: str | None,
) -> dict[str, int | str]:
    if halt == AS_THE_DESK_READS:
        return await the_halt_the_desk_reads(client, who, session_id)
    return naming(halt, warning)


async def attend(
    client: httpx.AsyncClient,
    session_id: str,
    who: Facilitator,
    *,
    halt: int | str | None = AS_THE_DESK_READS,
    warning: str | None = None,
) -> httpx.Response:
    """A visit naming ``halt`` and ``warning``, or by default the halt the Desk reads."""
    return await client.post(
        f"{IR}/facilitator/sessions/{session_id}/attended",
        params=await _named(client, session_id, who, halt, warning),
        headers=who.headers,
    )


async def unattend(
    client: httpx.AsyncClient,
    session_id: str,
    who: Facilitator,
    *,
    halt: int | str | None = AS_THE_DESK_READS,
    warning: str | None = None,
) -> httpx.Response:
    return await client.delete(
        f"{IR}/facilitator/sessions/{session_id}/attended",
        params=await _named(client, session_id, who, halt, warning),
        headers=who.headers,
    )


async def the_team_opens_the_session(client: httpx.AsyncClient) -> dict:
    opened = await client.post(f"{IR}/sessions", json={"pericope": P, "language": "pt"})
    assert opened.status_code == 200, opened.text[:300]
    return opened.json()


async def a_rehearsal(client: httpx.AsyncClient, session_id: str) -> str:
    kept = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers={"X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": P},
        files={"file": ("tomada.m4a", b"a equipe ensaiou a passagem", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text[:300]
    return kept.json()["take_id"]


async def tell_back_again(
    client: httpx.AsyncClient, session_id: str, take_id: str
) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": DEVICE},
        data={
            "take_id": take_id,
            "starts_ms": "0",
            "ends_ms": "9000",
            "retelling": "true",
        },
        files={"file": ("trecho.m4a", a_new_recording(), "audio/mp4")},
    )


async def a_warning_is_raised(client: httpx.AsyncClient, session_id: str) -> None:
    """The team tells the same stretch back until it becomes a hard stretch."""
    take_id = await a_rehearsal(client, session_id)
    for _ in range(RETELLS_BEFORE_A_WARNING):
        telling = await tell_back_again(client, session_id, take_id)
        assert telling.status_code == 200, telling.text[:300]
    assert telling.json()["needs_person"] is True, "o trecho difícil não levantou o aviso"


async def the_halt_of(db: AsyncSession, session_id: str) -> dict[str, int | str]:
    """The halt a visit names, read off the row as it stands, for a room no Desk read reaches."""
    held = await row(db, session_id)
    return naming(
        held.halts_raised, held.warned_at.isoformat() if held.warned_at is not None else None
    )
