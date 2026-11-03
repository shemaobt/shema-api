"""ENG-1379 — the MOMENT line says when a scene rehearsal of its part has reached the voice.

In her app an Articulation whose scene has a labelled rehearsal that reached the voice, the
one arriving on this turn included, reads «— a scene rehearsal of this part has reached you.»
(her src/turn/moment.ts:336, app/lib/liveTurn.ts:487). Ours only had the other forms.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.golden_rehearsal_harness import (
    a_golden_client,
    a_sent_rehearsal,
    after_the_break,
    an_open_session,
    the_room_stands_in,
)
from tests.text_seam_harness import GOLDEN, the_models_answer

REACHED = (
    "MOMENT: Articulation of part 2 of 3 \N{EM DASH} "
    "a scene rehearsal of this part has reached you."
)
PLAIN = "MOMENT: Articulation of part 2 of 3."
FENCED = "MOMENT: Articulation of part 2 of 3 \N{EM DASH} its fenced block has been given."


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with a_golden_client(db_session, monkeypatch) as c:
        yield c


async def test_a_labelled_rehearsal_of_the_articulations_scene_arriving_now_reads_as_reached(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    await the_room_stands_in(db_session, session_id, {"at": "articulation", "part": 2})
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S2")

    assert sent.status_code == 200, sent.text
    facts = after_the_break(agent.guide_systems[-1])
    assert REACHED in facts, "o ensaio da cena 2 chegando agora não aparecia no momento"


async def test_a_turn_after_a_labelled_rehearsal_of_the_articulations_scene_reads_as_reached(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    sent = await a_sent_rehearsal(client, session_id, "S2")
    assert sent.status_code == 200, sent.text
    await the_room_stands_in(db_session, session_id, {"at": "articulation", "part": 2})
    agent = the_models_answer(monkeypatch)

    typed = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": "Vamos continuar."}
    )

    assert typed.status_code == 200, typed.text
    facts = after_the_break(agent.guide_systems[-1])
    assert REACHED in facts, "o ensaio da cena 2 já enviado não aparecia no momento"


async def test_a_rehearsal_of_another_scene_leaves_the_articulation_plain(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    sent = await a_sent_rehearsal(client, session_id, "S1")
    assert sent.status_code == 200, sent.text
    await the_room_stands_in(db_session, session_id, {"at": "articulation", "part": 2})
    agent = the_models_answer(monkeypatch)

    typed = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": "Vamos continuar."}
    )

    assert typed.status_code == 200, typed.text
    facts = after_the_break(agent.guide_systems[-1])
    assert PLAIN in facts, "o ensaio da cena 1 contava como ensaio da cena 2 no momento"


async def test_a_fenced_block_still_reads_as_given_after_its_rehearsal_reached_the_voice(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    sent = await a_sent_rehearsal(client, session_id, "S2")
    assert sent.status_code == 200, sent.text
    await the_room_stands_in(
        db_session, session_id, {"at": "articulation", "part": 2, "fenced": True}
    )
    agent = the_models_answer(monkeypatch)

    typed = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": "Vamos continuar."}
    )

    assert typed.status_code == 200, typed.text
    facts = after_the_break(agent.guide_systems[-1])
    assert FENCED in facts, "o ensaio da cena 2 apagava o bloco cercado já dado no momento"


async def test_a_rehearsal_of_the_open_scene_arriving_now_reads_as_reached_in_its_articulation(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    await the_room_stands_in(db_session, session_id, {"at": "internalization", "part": 2})
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S2")

    assert sent.status_code == 200, sent.text
    facts = after_the_break(agent.guide_systems[-1])
    assert REACHED in facts, "o ensaio da cena aberta chegando agora não movia o momento da voz"
    assert "Internalization of part" not in facts, "a voz ainda lia a Internalização da cena"


async def test_a_rehearsal_of_the_scene_a_numberless_opening_opened_reads_as_reached_in_its_articulation(  # noqa: E501
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    opened = {"at": "articulation", "part": 1, "fenced": True, "numberlessOpening": True}
    await the_room_stands_in(db_session, session_id, opened)
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S2")

    assert sent.status_code == 200, sent.text
    facts = after_the_break(agent.guide_systems[-1])
    assert REACHED in facts, "a cena aberta sem número foi ensaiada e a voz ainda lia a anterior"
