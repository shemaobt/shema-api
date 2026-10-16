"""ENG-1323 — a scene counts as rehearsed only when a sent rehearsal carries its label.

On every passage turn the Guide's room facts carry her **Scene rehearsals** line, counted from
the session's **Rehearsal turns** as each one's label stood at sending, and from the rehearsal
arriving on this turn. Nothing anyone says marks a scene, and the Validator reads none of it.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import internalization_room as room_service
from app.services.internalization_room import scene_rehearsals as scenes
from tests.golden_rehearsal_harness import (
    Both,
    a_golden_client,
    a_sent_rehearsal,
    after_the_break,
    an_open_session,
    the_room_stands_in,
)
from tests.text_seam_harness import GOLDEN, the_models_answer
from tests.turn_harness import the_room_agent_is


def her_line(reached: str, none: str) -> str:
    return (
        "SCENE REHEARSALS: parts whose recorded and translated scene rehearsal has reached you: "
        f"{reached}. Parts with none: {none}."
    )


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with a_golden_client(db_session, monkeypatch) as c:
        yield c


async def typed(client: httpx.AsyncClient, session_id: str, words: str, **extra: object) -> None:
    answered = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": words, **extra}
    )
    assert answered.status_code == 200, answered.text


async def sent(client: httpx.AsyncClient, session_id: str, scene: str | None, n: int) -> None:
    answered = await a_sent_rehearsal(
        client, session_id, scene, turn_id=f"turno-{n}", pieces=[f"A cena contada, vez {n}."]
    )
    assert answered.status_code == 200, answered.text


async def test_two_labelled_rehearsals_of_s1_and_s2_make_the_next_turn_tell_the_voice_s1_and_s2_reached_and_s3_none(  # noqa: E501
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client, "P02")
    await sent(client, session_id, "S2", 1)
    await sent(client, session_id, "S1", 2)
    agent = the_models_answer(monkeypatch)

    await typed(client, session_id, "Vamos continuar.")

    facts = after_the_break(agent.guide_systems[-1])
    assert facts.count(her_line("S1, S2", "S3")) == 1, (
        "o turno seguinte não dizia à voz que S1 e S2 chegaram e S3 não"
    )


async def test_a_scene_rehearsed_twice_is_named_once_in_passage_order(client, monkeypatch) -> None:
    session_id = await an_open_session(client, "P02")
    await sent(client, session_id, "S2", 1)
    await sent(client, session_id, "S1", 2)
    await sent(client, session_id, "S2", 3)
    agent = the_models_answer(monkeypatch)

    await typed(client, session_id, "Vamos continuar.")

    assert her_line("S1, S2", "S3") in after_the_break(agent.guide_systems[-1]), (
        "a cena ensaiada duas vezes aparecia repetida ou fora da ordem da passagem"
    )


async def test_with_no_rehearsal_sent_every_scene_has_none(client, monkeypatch) -> None:
    agent = the_models_answer(monkeypatch)
    session_id = await an_open_session(client, "P02")

    await typed(client, session_id, "Vamos continuar.")

    opening, turn = (after_the_break(system) for system in agent.guide_systems)
    for where, facts in (("na abertura", opening), ("no turno digitado", turn)):
        assert her_line("none", "S1, S2, S3") in facts, (
            f"sem ensaio enviado, a voz não ouvia que nenhuma cena chegou, {where}"
        )


async def test_the_voice_saying_it_finished_scene_3_does_not_mark_scene_3_rehearsed(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client, "P02")
    agent = the_models_answer(monkeypatch, "Pronto, terminamos a cena 3.")

    await typed(client, session_id, "pronto, terminamos a cena 3")
    await typed(client, session_id, "Vamos continuar.")

    assert her_line("none", "S1, S2, S3") in after_the_break(agent.guide_systems[-1]), (
        "uma fala dizendo que a cena 3 acabou marcava a cena 3 como ensaiada"
    )


async def test_no_prompt_handed_to_the_voice_names_a_practice_done_block(
    client, monkeypatch
) -> None:
    agent = the_models_answer(monkeypatch)
    session_id = await an_open_session(client, "P02")
    await sent(client, session_id, "S2", 1)
    await typed(client, session_id, "pronto, terminamos a cena 3")
    await typed(client, session_id, "Vamos continuar.")

    assert agent.guide_systems, "nenhum turno chegou ao Guia"
    for system in agent.guide_systems:
        assert "PRACTICE DONE" not in system, "um prompt da voz falava de um bloco de prática"


async def test_a_rehearsal_sent_with_no_label_is_counted_for_no_scene(client, monkeypatch) -> None:
    session_id = await an_open_session(client, "P02")
    await sent(client, session_id, None, 1)
    agent = the_models_answer(monkeypatch)

    await typed(client, session_id, "Vamos continuar.")

    assert her_line("none", "S1, S2, S3") in after_the_break(agent.guide_systems[-1]), (
        "um ensaio enviado sem cena era contado para alguma cena"
    )


async def test_a_rehearsal_labelled_with_a_scene_the_passage_lacks_is_counted_for_no_scene(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client, "P02")
    await sent(client, session_id, "S99", 1)
    agent = the_models_answer(monkeypatch)

    await typed(client, session_id, "Vamos continuar.")

    facts = after_the_break(agent.guide_systems[-1])
    assert her_line("none", "S1, S2, S3") in facts, (
        "um ensaio marcado com uma cena que a passagem não tem era contado para alguma cena"
    )
    assert "S99" not in facts, "a cena que a passagem não tem aparecia nos fatos da voz"


async def test_the_rehearsal_arriving_on_this_turn_is_already_counted_on_its_own_turn(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client, "P02")
    agent = the_models_answer(monkeypatch)

    await sent(client, session_id, "S2", 1)

    assert her_line("S2", "S1, S3") in after_the_break(agent.guide_systems[-1]), (
        "o ensaio que chega neste turno só era contado no turno seguinte"
    )


async def test_a_labelled_rehearsal_of_the_current_scene_2_moves_the_moment_to_articulation_of_scene_2(  # noqa: E501
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client, "P02")
    await the_room_stands_in(db_session, session_id, {"at": "internalization", "part": 2})
    agent = the_models_answer(monkeypatch, "Vamos pra Articulação da cena 2.")

    await sent(client, session_id, "S2", 1)

    assert her_line("S2", "S1, S3") in after_the_break(agent.guide_systems[-1]), (
        "o turno do ensaio marcado da cena 2 não dizia à voz que S2 chegou"
    )
    stored = await room_service.get_session(db_session, session_id)
    await db_session.refresh(stored)
    *_, guide = stored.messages
    assert guide["moment"]["after"] == {"at": "articulation", "part": 2, "fenced": False}, (
        "o ensaio marcado da cena 2 não levava o momento à articulação da cena 2"
    )


async def test_a_rehearsal_turn_of_scene_4_hands_the_voice_scene_4s_accepted_readings_and_the_validator_none_of_the_room_facts(  # noqa: E501
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client, "P11")
    models = Both()
    the_room_agent_is(monkeypatch, turn=models)

    await sent(client, session_id, "S4", 1)

    facts = after_the_break(models.guide_systems[-1])
    assert "reached you: S4." in facts, "o turno do ensaio da cena 4 não dizia que S4 chegou"
    assert "ACCEPTED READINGS" in facts and "- R5:" in facts, (
        "o turno do ensaio da cena 4 não levava as leituras aceitas da cena 4"
    )
    read = "\n".join(models.validator_inputs)
    assert models.validator_inputs, "o Validador nem foi chamado"
    for fact in ("SCENE REHEARSALS", "ACCEPTED READINGS", "Parts with none"):
        assert fact not in read, f"o Validador lia {fact!r}"


async def test_a_golden_turns_carried_list_is_what_the_voice_is_told(client, monkeypatch) -> None:
    session_id = await an_open_session(client, "P02")
    agent = the_models_answer(monkeypatch)

    await typed(client, session_id, "Vamos continuar.", sceneRehearsals=["S3"])
    await typed(client, session_id, "Vamos continuar.", sceneRehearsals=[])

    carried, empty = (after_the_break(system) for system in agent.guide_systems)
    assert her_line("S3", "S1, S2") in carried, "a lista levada pelo turno dourado não chegava"
    assert her_line("none", "S1, S2, S3") in empty, "a lista vazia não era lida como nenhuma"


async def test_a_scene_labelled_only_after_its_rehearsal_was_sent_is_not_counted(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    """Labelled through `label_the_scene` itself: the golden harness has no label door, and the
    tablet's Room does not reach a following turn without a second app."""
    session_id = await an_open_session(client, "P02")
    kept = await client.post(
        f"{GOLDEN}/rehearsal",
        json={"sessionId": session_id, "sceneId": None, "pieces": ["A cena contada."]},
    )
    rehearsal_id = kept.json()["rehearsalId"]
    send = await client.post(
        f"{GOLDEN}/rehearsal/send",
        json={"sessionId": session_id, "rehearsalId": rehearsal_id, "turnId": "turno-1"},
    )
    assert send.status_code == 200, send.text
    rehearsal = await scenes.scene_rehearsal_in_session(db_session, session_id, rehearsal_id)
    await scenes.label_the_scene(db_session, rehearsal, "S2")
    stored = await db_session.execute(
        text("SELECT scene FROM ir_scene_rehearsals WHERE id = :id"), {"id": rehearsal_id}
    )
    assert stored.scalar_one() == "S2", "a cena dada depois do envio não ficou no ensaio"
    agent = the_models_answer(monkeypatch)

    await typed(client, session_id, "Vamos continuar.")

    assert her_line("none", "S1, S2, S3") in after_the_break(agent.guide_systems[-1]), (
        "a cena marcada depois do envio era contada como ensaiada"
    )
