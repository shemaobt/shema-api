"""ENG-1237 — a new session starts the way hers does.

Every bead at not encountered, whatever the team worked before; her 12 beads in the coverage
answer, filled in her proportion (`beadsFilled`, `src/session/types.ts`); and, from a book's
second passage on, the team's status on every earlier passage, read when the session is
created and never again. Folded from ENG-1282: the open door opens exactly the pericope it is
asked for, the Panorama included.

The cases go through `POST /sessions` and the turn route with a real tablet's credential, and
read what the tablet is answered or what the Guide is handed. Three read the stored session:
the Panorama's and the first passage's stamp, which no prompt renders, and the `after_panorama`
mark, which the open's answer does not carry.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.db.models.project import Project
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    apply_coverage,
    create_session,
    get_session,
    is_panorama,
)
from tests.baker import make_app, make_role
from tests.release_harness import (
    PREFIX,
    a_claimed_device,
    at_the_desk,
    ready_session,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent

ENGAGED = CoverageStatus.ENGAGED.value
EARLIER = "EARLIER PASSAGES FOR THIS TEAM:"
ALL_THREE_NOT_WORKED = (
    "EARLIER PASSAGES FOR THIS TEAM: Not worked yet: Ruth 1:1\N{EN DASH}5, "
    "Ruth 1:6\N{EN DASH}14, Ruth 1:15\N{EN DASH}18."
)


@pytest.fixture()
def agent(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    guide = ScriptedAgent([])

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belem com Rute")

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=guide)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return guide


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, agent, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def opened(
    client: httpx.AsyncClient, tablet: str, body: dict[str, Any], *, language: str = "pt"
) -> dict[str, Any]:
    answered = await client.post(
        f"{PREFIX}/sessions", headers=team_headers(tablet), json={"language": language, **body}
    )
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


async def read_back(client: httpx.AsyncClient, tablet: str, session_id: str) -> dict[str, Any]:
    answered = await client.get(f"{PREFIX}/sessions/{session_id}", headers=team_headers(tablet))
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


async def the_guides_first_prompt(
    client: httpx.AsyncClient, agent: ScriptedAgent, tablet: str, session_id: str
) -> str:
    before = len(agent.guide_systems)
    await the_room_opens(client, tablet, session_id)
    return agent.guide_systems[before]


def earlier_line(system_prompt: str) -> str | None:
    lines = [line for line in system_prompt.splitlines() if line.startswith(EARLIER)]
    return lines[0] if lines else None


async def entered(client: httpx.AsyncClient, tablet: str, pericope: str, *, language: str) -> str:
    """The team opens the passage and the room speaks its opening, which enters it."""
    session = await opened(client, tablet, {"pericope": pericope}, language=language)
    await the_room_opens(client, tablet, session["session_id"])
    return session["session_id"]


async def approved(
    client: httpx.AsyncClient, db: AsyncSession, team: Project, tablet: str, pericope: str
):
    session = await ready_session(db, pericope=pericope, project_id=team.id)
    answered = await client.post(team_release(session.id), headers=team_headers(tablet))
    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["version"] == 1, answered.text[:300]
    return session


async def engaged(
    per_request: async_sessionmaker[AsyncSession], session_id: str, keys: list[str]
) -> None:
    async with per_request() as fresh:
        await apply_coverage(fresh, session_id, dict.fromkeys(keys, ENGAGED))


async def stored_stamp(per_request: async_sessionmaker[AsyncSession], session_id: str):
    async with per_request() as fresh:
        return (await get_session(fresh, session_id)).earlier_passages


async def zerar(
    client: httpx.AsyncClient, db: AsyncSession, room_app, team: Project, pericope: str
) -> None:
    desk, _ = await at_the_desk(db, room_app, team)
    answered = await client.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/{pericope}/archive", headers=desk
    )
    assert answered.status_code == 200, answered.text[:300]


async def having_heard_the_panorama(client: httpx.AsyncClient, tablet: str) -> str:
    launched = await opened(client, tablet, {"pericope": "OV"})
    assert is_panorama(launched["pericope"])
    went_on = await opened(client, tablet, {"after_session": launched["session_id"]})
    assert not is_panorama(went_on["pericope"])
    return launched["session_id"]


# ----------------------------------------------------------------------------- 12 beads


async def test_a_new_ruth_p01_session_shows_12_beads_none_filled_and_no_earlier_passages_status(
    client, db_session, agent
) -> None:
    """Acceptance 1."""
    _team, tablet = await a_claimed_device(db_session)

    session = await opened(client, tablet, {"pericope": "P01"})
    first = await the_guides_first_prompt(client, agent, tablet, session["session_id"])

    assert session["coverage"]["beads_total"] == 12
    assert session["coverage"]["beads_filled"] == 0
    assert earlier_line(first) is None


async def test_a_new_sessions_coverage_reads_12_beads_and_fills_them_in_her_proportion(
    client, db_session, per_request
) -> None:
    """Acceptance 5: P03 has 30 elements, and 10 engaged of 30 is 4 of her 12."""
    _team, tablet = await a_claimed_device(db_session)
    session = await opened(client, tablet, {"pericope": "P03"})

    await engaged(per_request, session["session_id"], element_keys("P03")[:10])
    coverage = (await read_back(client, tablet, session["session_id"]))["coverage"]

    assert (coverage["beads_total"], coverage["beads_filled"]) == (12, 4)


async def test_a_half_bead_rounds_up_as_her_app_rounds_it(client, db_session, per_request) -> None:
    """P07 has 56 elements: 21 engaged is 4.5 beads, and her `Math.round` answers 5."""
    _team, tablet = await a_claimed_device(db_session)
    session = await opened(client, tablet, {"pericope": "P07"})

    await engaged(per_request, session["session_id"], element_keys("P07")[:21])
    coverage = (await read_back(client, tablet, session["session_id"]))["coverage"]

    assert coverage["beads_filled"] == 5


async def test_the_panorama_answers_12_beads_with_none_filled(client, db_session) -> None:
    _team, tablet = await a_claimed_device(db_session)

    panorama = await opened(client, tablet, {"pericope": "OV"})

    assert is_panorama(panorama["pericope"])
    assert (panorama["coverage"]["beads_total"], panorama["coverage"]["beads_filled"]) == (12, 0)


async def test_every_bead_of_a_new_session_starts_not_encountered_whatever_the_team_worked_before(
    client, db_session, per_request
) -> None:
    """Acceptance 3, its coverage half: the team's English P02 has engaged beads, and their
    new Portuguese P02 starts with every bead not encountered."""
    _team, tablet = await a_claimed_device(db_session)
    english = await entered(client, tablet, "P02", language="en")
    await engaged(per_request, english, element_keys("P02")[:20])

    portuguese = await opened(client, tablet, {"pericope": "P02"}, language="pt")

    assert portuguese["session_id"] != english
    assert portuguese["coverage"]["surfaced"] == 0
    assert portuguese["coverage"]["beads_filled"] == 0


# ---------------------------------------------------------------------- earlier passages


async def test_a_p04_opening_already_knows_each_earlier_passages_status(
    client, db_session, agent
) -> None:
    """Acceptance 2: P01 approved, P02 started, P03 never opened."""
    team, tablet = await a_claimed_device(db_session)
    await approved(client, db_session, team, tablet, "P01")
    await entered(client, tablet, "P02", language="pt")

    session = await opened(client, tablet, {"pericope": "P04"})
    first = await the_guides_first_prompt(client, agent, tablet, session["session_id"])

    assert earlier_line(first) == (
        "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1\N{EN DASH}5. "
        "Started, not approved yet: Ruth 1:6\N{EN DASH}14. Not worked yet: Ruth 1:15\N{EN DASH}18."
    )


async def test_a_session_the_team_opened_but_never_entered_does_not_make_its_passage_started(
    client, db_session, agent
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    await opened(client, tablet, {"pericope": "P02"})

    session = await opened(client, tablet, {"pericope": "P04"})
    first = await the_guides_first_prompt(client, agent, tablet, session["session_id"])

    assert earlier_line(first) == ALL_THREE_NOT_WORKED


async def test_a_session_the_team_entered_in_another_language_makes_its_passage_started(
    client, db_session, agent
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    await entered(client, tablet, "P02", language="en")

    session = await opened(client, tablet, {"pericope": "P04"}, language="pt")
    first = await the_guides_first_prompt(client, agent, tablet, session["session_id"])

    assert earlier_line(first) == (
        "EARLIER PASSAGES FOR THIS TEAM: Started, not approved yet: Ruth 1:6\N{EN DASH}14. "
        "Not worked yet: Ruth 1:1\N{EN DASH}5, Ruth 1:15\N{EN DASH}18."
    )


async def test_an_archived_release_does_not_make_its_passage_approved_nor_an_archived_session_started(  # noqa: E501
    client, db_session, agent, room_app
) -> None:
    """A Zerar of P01 archives its release and its entered session together."""
    team, tablet = await a_claimed_device(db_session)
    await approved(client, db_session, team, tablet, "P01")
    await zerar(client, db_session, room_app, team, "P01")

    session = await opened(client, tablet, {"pericope": "P04"})
    first = await the_guides_first_prompt(client, agent, tablet, session["session_id"])

    assert earlier_line(first) == ALL_THREE_NOT_WORKED


async def test_another_teams_work_never_reaches_this_teams_stamp(client, db_session, agent) -> None:
    other, other_tablet = await a_claimed_device(db_session, email="outra@example.com")
    _team, tablet = await a_claimed_device(db_session, email="esta@example.com")
    await approved(client, db_session, other, other_tablet, "P01")
    await entered(client, other_tablet, "P02", language="pt")

    session = await opened(client, tablet, {"pericope": "P04"})
    first = await the_guides_first_prompt(client, agent, tablet, session["session_id"])

    assert earlier_line(first) == ALL_THREE_NOT_WORKED


async def test_the_stamp_a_session_was_created_with_stays_when_an_earlier_passage_is_approved_later(
    client, db_session, agent
) -> None:
    """Acceptance 4: P04 is created while P01 is only started, then P01 is approved."""
    team, tablet = await a_claimed_device(db_session)
    p01 = await ready_session(db_session, pericope="P01", project_id=team.id)
    session = await opened(client, tablet, {"pericope": "P04"})
    await the_room_opens(client, tablet, session["session_id"])
    approval = await client.post(team_release(p01.id), headers=team_headers(tablet))
    assert approval.json()["version"] == 1, approval.text[:300]

    before = len(agent.guide_systems)
    await the_team_says(client, tablet, session["session_id"], str(uuid.uuid4()))

    assert earlier_line(agent.guide_systems[before]) == (
        "EARLIER PASSAGES FOR THIS TEAM: Started, not approved yet: Ruth 1:1\N{EN DASH}5. "
        "Not worked yet: Ruth 1:6\N{EN DASH}14, Ruth 1:15\N{EN DASH}18."
    )


async def test_the_first_passage_of_a_book_and_the_panorama_carry_no_earlier_passages_status(
    client, db_session, per_request
) -> None:
    team, tablet = await a_claimed_device(db_session)
    await approved(client, db_session, team, tablet, "P02")

    first = await opened(client, tablet, {"pericope": "P01"})
    panorama = await opened(client, tablet, {"pericope": "OV"})
    third = await opened(client, tablet, {"pericope": "P03"})

    assert await stored_stamp(per_request, first["session_id"]) is None
    assert await stored_stamp(per_request, panorama["session_id"]) is None
    assert await stored_stamp(per_request, third["session_id"]) == {
        "P01": "not_worked",
        "P02": "approved",
    }, "o controle: a sala carimba as passagens anteriores de uma passagem que as tem"


async def test_the_golden_doors_earlier_passages_win_over_the_rooms_own_reading(
    client, db_session, per_request
) -> None:
    """Her runner's stamp is taken at its word. The Golden door names no team, so a stamp that
    disagrees with a team's rows is handed to the service the door calls: P02 is started in the
    rows and not worked in the stamp."""
    team, tablet = await a_claimed_device(db_session)
    await entered(client, tablet, "P02", language="pt")
    handed = {"P01": "approved", "P02": "not_worked", "P03": "not_worked"}

    session = await create_session(
        db_session, pericope="P04", project_id=team.id, earlier_passages=handed
    )

    assert await stored_stamp(per_request, session.id) == handed


# -------------------------------------------------------------------------- the open door


async def test_opening_ov_ruth_on_a_tablet_whose_team_already_heard_the_panorama_opens_the_panorama(
    client, db_session, per_request
) -> None:
    """Acceptance 6, by the book's id and by its alias, each with the mark it asked for."""
    _team, tablet = await a_claimed_device(db_session)
    heard = await having_heard_the_panorama(client, tablet)

    by_id = await opened(client, tablet, {"pericope": "OV-Ruth"})
    by_alias = await opened(client, tablet, {"pericope": "OV", "after_panorama": True})

    assert (by_id["pericope"], by_id["session_id"]) == ("OV-Ruth", heard)
    assert (by_alias["pericope"], by_alias["session_id"]) == ("OV-Ruth", heard)
    async with per_request() as fresh:
        assert (await get_session(fresh, heard)).after_panorama is True


async def test_a_panorama_opened_without_the_mark_is_not_marked(
    client, db_session, per_request
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    await having_heard_the_panorama(client, tablet)

    panorama = await opened(client, tablet, {"pericope": "OV-Ruth"})

    async with per_request() as fresh:
        assert (await get_session(fresh, panorama["session_id"])).after_panorama is False


async def test_a_request_that_still_says_chosen_is_answered_as_if_it_did_not(
    client, db_session
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    heard = await having_heard_the_panorama(client, tablet)

    unchosen = await opened(client, tablet, {"pericope": "OV", "chosen": False})
    chosen = await opened(client, tablet, {"pericope": "OV", "chosen": True})

    assert (unchosen["pericope"], unchosen["session_id"]) == ("OV-Ruth", heard)
    assert (chosen["pericope"], chosen["session_id"]) == ("OV-Ruth", heard)
