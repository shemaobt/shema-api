"""ENG-1604 — the consultant's turn read serves each turn's moment step.

The step is stored with every turn since ENG-1414 and no route served it. Every case speaks a
turn through the tablet's own door with the Guide and the Validator scripted, then reads it back
as the Desk's facilitator does.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.internalization_room import TurnMomentStep
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_exchange, create_session
from tests.baker import make_app, make_role
from tests.release_harness import PREFIX, P, a_claimed_device, at_the_desk
from tests.room_harness import room_client
from tests.tablet_turn_harness import the_team_says, the_turn_is_scripted


class _Model:
    def __init__(self, drafts: list[str]) -> None:
        self.drafts = drafts
        self.drafted = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" not in system_prompt:
            self.drafted += 1
            return self.drafts[self.drafted - 1]
        return '{"verdict": "pass", "issues": []}'


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
def the_room_hears(monkeypatch: pytest.MonkeyPatch):
    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="estamos prontos")

    def _install(drafts: list[str]) -> None:
        the_turn_is_scripted(monkeypatch, heard=heard, model=_Model(drafts))

    return _install


async def _the_last_turn_as_the_desk_reads_it(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app, *, said_before: list[str]
) -> dict[str, Any]:
    project, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, project)
    session = await create_session(db_session, project_id=project.id, language="pt", pericope=P)
    for line in said_before:
        await append_exchange(db_session, session, team_utterance="ok", guide_response=line)
    await the_team_says(client, tablet, session.id, "turno")
    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/turns", headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()["turns"][-1]


async def test_a_turn_that_opened_scene_two_serves_where_it_began_and_where_it_left_the_room(
    client, db_session, room_app, the_room_hears
) -> None:
    the_room_hears(["Vamos pra Internalização da cena 2."])

    turn = await _the_last_turn_as_the_desk_reads_it(
        client, db_session, room_app, said_before=["Vamos começar pela Familiarização."]
    )

    assert turn["voice"]["moment"] == {
        "before": {"at": "familiarization", "part": None, "closed": False, "fenced": False},
        "after": {"at": "internalization", "part": 2, "closed": False, "fenced": False},
        "by": ["entrance"],
        "ignored": [],
    }


async def test_a_numbered_line_after_the_send_off_serves_the_line_the_room_declined_and_why(
    client, db_session, room_app, the_room_hears
) -> None:
    the_room_hears(["Vamos pra Internalização da cena 3."])

    turn = await _the_last_turn_as_the_desk_reads_it(
        client,
        db_session,
        room_app,
        said_before=[
            "Vamos começar pela Familiarização.",
            "Agora toquem no ponto laranja, no alto da tela, para abrir o Ensaio Final.",
        ],
    )

    assert turn["voice"]["moment"] == {
        "before": {"at": "ensaio_final", "part": None, "closed": False, "fenced": False},
        "after": {"at": "ensaio_final", "part": None, "closed": False, "fenced": False},
        "by": [],
        "ignored": ["entrance 3: after the send-off (Ensaio Final)"],
    }


async def test_a_turn_stored_before_moments_existed_reads_no_moment(
    client, db_session, room_app
) -> None:
    project, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, project)
    session = await create_session(db_session, project_id=project.id, language="pt", pericope=P)
    session.messages = [
        {"role": "guide", "text": "Linha antiga.", "at": "2026-10-01T12:00:00+00:00"}
    ]
    await db_session.commit()

    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/turns", headers=desk)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["turns"][0]["voice"]["moment"] is None


async def test_a_step_a_scene_rehearsal_moved_is_served_to_the_desk_with_its_cause(
    client, db_session, room_app
) -> None:
    project, _ = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, project)
    session = await create_session(db_session, project_id=project.id, language="pt", pericope=P)
    session.messages = [
        {
            "role": "guide",
            "text": "A cena dois chegou.",
            "at": "2026-10-19T12:00:00+00:00",
            "moment": {
                "before": {"at": "articulation", "part": 1, "fenced": True},
                "after": {"at": "articulation", "part": 2, "fenced": False},
                "by": ["scene_rehearsal"],
            },
        }
    ]
    await db_session.commit()

    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/turns", headers=desk)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["turns"][0]["voice"]["moment"]["by"] == ["scene_rehearsal"], (
        "um passo movido por um ensaio de cena derrubava a leitura de turnos da mesa"
    )


async def test_a_closing_heard_as_a_numberless_opening_is_served_with_the_opening_it_kept(
    client, db_session, room_app
) -> None:
    project, _ = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, project)
    session = await create_session(db_session, project_id=project.id, language="pt", pericope=P)
    session.messages = [
        {
            "role": "guide",
            "text": "Se já entenderam, me digam e a gente vai pro ensaio.",
            "at": "2026-10-19T12:00:00+00:00",
            "moment": {
                "before": {"at": "articulation", "part": 2, "fenced": True},
                "after": {
                    "at": "articulation",
                    "part": 2,
                    "fenced": True,
                    "numberlessOpening": True,
                },
                "by": ["part_closing"],
            },
        }
    ]
    await db_session.commit()

    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/turns", headers=desk)

    assert answered.status_code == 200, answered.text[:300]
    moment = answered.json()["turns"][0]["voice"]["moment"]
    assert moment["after"] == {
        "at": "articulation",
        "part": 2,
        "closed": False,
        "fenced": True,
        "numberlessOpening": True,
    }, "a mesa via o fechamento mover o momento sem ver o que ele guardou"
    assert moment["before"] == {"at": "articulation", "part": 2, "closed": False, "fenced": True}


def test_the_published_schema_of_a_step_lists_the_eight_causes_that_can_move_the_room() -> None:
    published = TurnMomentStep.model_json_schema()["properties"]["by"]["items"]

    assert published == {
        "enum": [
            "scene_rehearsal",
            "entrance",
            "articulation_entrance",
            "where_we_are",
            "fence",
            "part_closing",
            "familiarization_closing",
            "send_off",
        ],
        "type": "string",
    }


async def test_a_panorama_turn_reads_no_moment_because_a_book_has_none(
    client, db_session, room_app
) -> None:
    project, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, project)
    session = await create_session(
        db_session, project_id=project.id, language="pt", pericope="OV-Ruth"
    )
    await append_exchange(
        db_session, session, team_utterance="", guide_response="Vamos ouvir o livro de Rute."
    )

    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/turns", headers=desk)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["turns"][0]["voice"]["moment"] is None
