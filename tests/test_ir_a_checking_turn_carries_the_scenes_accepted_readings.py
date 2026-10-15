from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.internalization_room import hearing, takes
from app.services.internalization_room.llm import CACHE_BREAK
from tests.hearing_harness import nothing_settles
from tests.text_seam_harness import BEARER, GOLDEN, RUNNER_KEY, the_app, the_models_answer

HEADER = (
    "ACCEPTED READINGS FOR THE SCENE THIS TELLING CHECKS (a note from the app, in English like "
    "its other notes; never read aloud, never repeated to the team): the passage's rulings on "
    "how a team's telling of this scene is heard. A line counts only when the team's telling "
    "does what the line describes, and it accepts only what it names; the rest of the telling "
    "is checked as usual. When the telling does not do what a line describes, say nothing about "
    "that line. When the telling does what a line accepts, let that part pass in silence: do "
    "not name it, repeat it, praise it, explain it, compare it with the text's words or say "
    "that it is correct or allowed, and do not send it back for it. A line that calls it a "
    "nuance: name it once — in the words the line gives, when it gives them — as a plain "
    "remark, adding nothing to it (no instruction to keep or change it, and no word about "
    "naming it or letting it pass), and do not send it back for it. A line that says a telling "
    "is offered back: offer back only the text's own words for that part, with no other "
    "reason, and do not say the team's words are wrong. Nothing from these lines goes into "
    "anything else you say on this turn: not an invitation to tell the scene again, not the "
    "opening of the next scene, not the send-off."
)
P11_S4_R5 = (
    "- R5: A team telling 'and gave it to Boaz' is correct, not an addition. "
    "The voice accepts it and does not correct or remark on it."
)
SANDAL = ["Ele tirou a sandália e deu pro Boaz."]


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    the_models_answer(monkeypatch)
    nothing_settles(monkeypatch)

    async def _never_heard(*_: Any, **__: Any) -> Any:
        raise AssertionError("a porta dourada pediu ao reconhecedor que ouvisse uma frase")

    def _never_stored(*_: Any, **__: Any) -> Any:
        raise AssertionError("a porta dourada tocou o balde")

    monkeypatch.setattr(hearing, "transcribe_audio", _never_heard)
    monkeypatch.setattr(hearing, "transcribe_audio_detailed", _never_heard)
    monkeypatch.setattr(takes, "_store", _never_stored)
    transport = ASGITransport(app=the_app(db_session))
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=BEARER) as c:
        yield c


async def an_open_session(client: httpx.AsyncClient, pericope: str = "P11") -> str:
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": pericope, "language": "Brazilian Portuguese"}
    )
    assert created.status_code == 200, created.text
    session_id = str(created.json()["sessionId"])
    opened = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"}
    )
    assert opened.status_code == 200, opened.text
    return session_id


async def a_sent_rehearsal(
    client: httpx.AsyncClient, session_id: str, scene: str | None, turn_id: str = "turno-1"
) -> httpx.Response:
    kept = await client.post(
        f"{GOLDEN}/rehearsal", json={"sessionId": session_id, "sceneId": scene, "pieces": SANDAL}
    )
    assert kept.status_code == 200, kept.text
    return await client.post(
        f"{GOLDEN}/rehearsal/send",
        json={
            "sessionId": session_id,
            "rehearsalId": kept.json()["rehearsalId"],
            "turnId": turn_id,
        },
    )


def after_the_break(system_prompt: str) -> str:
    return system_prompt.partition(CACHE_BREAK)[2]


async def test_a_rehearsal_of_p11_scene_4_ends_the_guides_room_facts_with_her_header_and_r5_alone(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    facts = after_the_break(agent.guide_systems[-1])
    assert facts.endswith(f"\n\n{HEADER}\n{P11_S4_R5}"), (
        "o ensaio da cena 4 chegava ao Guia sem as leituras aceitas dela no fim dos fatos da sala"
    )
    assert facts.count("ACCEPTED READINGS") == 1


async def test_the_same_words_typed_hand_the_guide_no_accepted_readings(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    agent = the_models_answer(monkeypatch)

    typed = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": SANDAL[0]}
    )

    assert typed.status_code == 200, typed.text
    assert agent.guide_systems, "o Guia nem foi chamado"
    assert "ACCEPTED READINGS" not in agent.guide_systems[-1], (
        "as mesmas palavras digitadas levavam as leituras aceitas"
    )


async def test_a_rehearsal_of_a_scene_with_no_ruling_hands_the_guide_no_accepted_readings(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S3")

    assert sent.status_code == 200, sent.text
    assert "ACCEPTED READINGS" not in agent.guide_systems[-1], (
        "a cena 3 de P11, sem nenhuma regra, levava um cabeçalho sem linhas"
    )


async def test_a_rehearsal_sent_outside_ruth_3_and_4_hands_the_guide_no_accepted_readings(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client, "P01")
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S2")

    assert sent.status_code == 200, sent.text
    assert "ACCEPTED READINGS" not in agent.guide_systems[-1], (
        "um ensaio de Rute 1 levava leituras aceitas que ela só deu para Rute 3 e 4"
    )
