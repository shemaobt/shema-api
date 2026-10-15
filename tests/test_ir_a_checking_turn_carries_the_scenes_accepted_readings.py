from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room_service
from app.services.internalization_room import hearing, passage_turn, takes
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.hearing import SentSceneRehearsal
from app.services.internalization_room.llm import CACHE_BREAK
from tests.hearing_harness import nothing_settles
from tests.text_seam_harness import (
    BEARER,
    GOLDEN,
    GUIDE_LINE,
    RUNNER_KEY,
    the_app,
    the_models_answer,
)
from tests.turn_harness import GUIDE, VALIDATOR, settings, the_room_agent_is

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
P13_S3_LINES = (
    "- R5: A telling 'she took care of him' or 'she raised him' keeps the meaning; accept it "
    "without comment.\n"
    "- R8: A team telling 'King David' ('o rei Davi') is a nuance: the voice names it once "
    "\N{EM DASH} 'a hist\u00f3ria d\u00e1 s\u00f3 o nome dele, Davi' ('the story gives only his "
    "name, David') \N{EM DASH} without a send-back, and moves on.\n"
    "- R9: A telling that recalls Boaz's words at the gate \N{EM DASH} he bought Ruth to raise "
    "up the name of the dead \N{EM DASH} is correct; accept it without comment."
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


async def the_room_stands_in(db: AsyncSession, session_id: str, moment: dict[str, Any]) -> None:
    stored = await room_service.get_session(db, session_id)
    *earlier, guide = [dict(message) for message in stored.messages or []]
    guide["moment"] = {"before": {"at": "familiarization"}, "after": moment, "by": []}
    stored.messages = [*earlier, guide]
    await db.commit()


async def test_an_unmarked_rehearsal_in_the_articulation_of_part_4_is_checked_as_scene_4(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)
    await the_room_stands_in(
        db_session, session_id, {"at": "articulation", "part": 4, "fenced": True}
    )
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, None)

    assert sent.status_code == 200, sent.text
    assert after_the_break(agent.guide_systems[-1]).endswith(f"\n\n{HEADER}\n{P11_S4_R5}"), (
        "um ensaio sem cena marcada, na articulação da parte 4, não era conferido como a cena 4"
    )


async def test_an_unmarked_rehearsal_outside_an_articulation_hands_the_guide_no_accepted_readings(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)
    await the_room_stands_in(db_session, session_id, {"at": "internalization", "part": 4})
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, None)

    assert sent.status_code == 200, sent.text
    assert "ACCEPTED READINGS" not in agent.guide_systems[-1], (
        "um ensaio sem cena marcada, fora de uma articulação, ganhava uma cena por palpite"
    )


class Both:
    def __init__(self) -> None:
        self.validator_inputs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_inputs.append(f"{system_prompt}\n{user_content}")
            return json.dumps({"verdict": "pass", "issues": []})
        return "Obrigado. Vamos ver essa cena juntos."


async def test_the_turn_keeps_only_the_entry_ids_and_the_block_reaches_no_store_no_reply_no_validator(  # noqa: E501
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)
    models = Both()
    the_room_agent_is(monkeypatch, turn=models)

    sent = await a_sent_rehearsal(client, session_id, "S4")
    typed = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": SANDAL[0]}
    )

    assert (sent.status_code, typed.status_code) == (200, 200), (sent.text, typed.text)
    stored = await room_service.get_session(db_session, session_id)
    await db_session.refresh(stored)
    *_, checked, _words, ordinary = stored.messages
    assert checked.get("accepted_ids") == ["R5"], "o turno de conferência não guardava os ids"
    assert "accepted_ids" not in ordinary, "um turno comum guardava ids de leituras aceitas"
    for where, text in (
        ("na conversa guardada", json.dumps(stored.messages, ensure_ascii=False)),
        ("na resposta do turno", sent.text),
        ("no que o Validador leu", "\n".join(models.validator_inputs)),
    ):
        assert "ACCEPTED READINGS" not in text, f"o cabeçalho das leituras aceitas aparecia {where}"
        assert "- R5: A team telling" not in text, f"a linha do R5 aparecia {where}"


async def test_a_redraft_the_validator_asks_for_is_drafted_under_the_same_accepted_readings(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    regenerate = json.dumps(
        {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}
    )
    agent = the_models_answer(monkeypatch, None, regenerate, None, None)

    sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    first, second = (after_the_break(system) for system in agent.guide_systems)
    assert first.endswith(f"\n\n{HEADER}\n{P11_S4_R5}")
    assert second == first, "o rascunho pedido pelo Validador perdia as leituras aceitas"


async def test_a_register_that_cannot_be_read_leaves_the_turn_whole_and_says_where_never_what(
    client, monkeypatch, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    session_id = await an_open_session(client)
    agent = the_models_answer(monkeypatch)

    def _unreadable(pericope_num: str) -> Any:
        raise ValueError(f"{pericope_num}: o registro não abre")

    monkeypatch.setattr(passage_turn, "accepted_readings_of", _unreadable)

    with caplog.at_level(logging.WARNING, logger=passage_turn.__name__):
        sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    assert "ACCEPTED READINGS" not in agent.guide_systems[-1]
    stored = await room_service.get_session(db_session, session_id)
    await db_session.refresh(stored)
    *_, guide = stored.messages
    assert "accepted_ids" not in guide, "um turno sem leituras guardava ids"
    said = [
        record.getMessage() for record in caplog.records if record.name == passage_turn.__name__
    ]
    assert len(said) == 1 and session_id in said[0] and "S4" in said[0], (
        "a falha da leitura do registro passava calada, ou sem dizer a sessão e a cena"
    )
    assert "ACCEPTED READINGS" not in said[0]


async def test_a_scene_mark_the_passage_lacks_hands_the_guide_nothing_and_keeps_no_ids(
    monkeypatch,
) -> None:
    agent = the_models_answer(monkeypatch)

    outcome = await passage_turn.run_turn(
        transcript=SANDAL[0],
        coverage_state=initial_state("P11"),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num="P11",
        language_code="pt",
        settings=settings(),
        scene_rehearsal=SentSceneRehearsal(rehearsal_id="ensaio-1", n=1, frases=1, scene="S99"),
    )

    assert agent.guide_systems, "o Guia nem foi chamado"
    assert "ACCEPTED READINGS" not in agent.guide_systems[-1], (
        "uma cena que a passagem não tem levava as leituras aceitas de alguma outra"
    )
    assert outcome.accepted_ids == [], "uma cena que a passagem não tem guardava ids"


async def test_a_marked_rehearsal_sent_late_at_the_ensaio_final_is_still_checked_as_its_scene(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)
    await the_room_stands_in(db_session, session_id, {"at": "ensaio_final"})
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    assert after_the_break(agent.guide_systems[-1]).endswith(f"\n\n{HEADER}\n{P11_S4_R5}"), (
        "um ensaio marcado, enviado tarde, depois do envio, perdia as leituras aceitas da cena"
    )


async def test_a_rehearsal_of_p13_scene_3_telling_the_king_david_hands_the_guide_the_nuance_line(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client, "P13")
    agent = the_models_answer(monkeypatch)

    kept = await client.post(
        f"{GOLDEN}/rehearsal",
        json={
            "sessionId": session_id,
            "sceneId": "S3",
            "pieces": ["Ela criou o filho do rei Davi."],
        },
    )
    sent = await client.post(
        f"{GOLDEN}/rehearsal/send",
        json={
            "sessionId": session_id,
            "rehearsalId": kept.json()["rehearsalId"],
            "turnId": "turno-1",
        },
    )

    assert sent.status_code == 200, sent.text
    assert after_the_break(agent.guide_systems[-1]).endswith(f"\n\n{HEADER}\n{P13_S3_LINES}"), (
        "o ensaio da cena 3 de P13, com o rei Davi, chegava ao Guia sem a linha do R8"
    )


async def test_an_unmarked_rehearsal_in_the_familiarization_of_part_2_hands_the_guide_no_readings(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)
    await the_room_stands_in(db_session, session_id, {"at": "familiarization", "part": 2})
    agent = the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, None)

    assert sent.status_code == 200, sent.text
    assert "ACCEPTED READINGS" not in agent.guide_systems[-1], (
        "um ensaio sem cena marcada, na familiarização da parte 2, ganhava as leituras da cena 2"
    )


def regenerating(claim: str) -> str:
    return json.dumps(
        {
            "verdict": "regenerate",
            "issues": [
                {"claim": claim, "problem": "invented_detail", "explanation": "o mapa não diz"}
            ],
        }
    )


def the_sendbacks_said(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == passage_turn.__name__ and "[accepted-sendback]" in record.getMessage()
    ]


async def test_a_send_back_on_a_turn_that_handed_readings_is_reported_with_the_ids_and_the_issue(
    client, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    session_id = await an_open_session(client)
    agent = the_models_answer(monkeypatch, None, regenerating("deu a sandália ao Boaz"), None, None)

    with caplog.at_level(logging.WARNING, logger=passage_turn.__name__):
        sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    assert len(agent.guide_systems) == 2
    (said,) = the_sendbacks_said(caplog)
    for expected in (session_id, "scene=S4", "ids=['R5']", "attempt=1", "deu a sandália ao Boaz"):
        assert expected in said, f"o aviso do reenvio não trazia {expected!r}: {said}"
    assert "ACCEPTED READINGS" not in said and "- R5: A team telling" not in said, (
        "o aviso do reenvio repetia as palavras do bloco"
    )
    assert GUIDE_LINE not in said, "o aviso do reenvio repetia o rascunho do Guia"


async def test_every_send_back_of_a_checking_turn_is_reported_not_only_the_first(
    client, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    session_id = await an_open_session(client)
    first, second = regenerating("deu a sandália ao Boaz"), regenerating("o Boaz ficou com ela")
    the_models_answer(monkeypatch, None, first, None, second)

    with caplog.at_level(logging.WARNING, logger=passage_turn.__name__):
        sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    one, two = the_sendbacks_said(caplog)
    assert "attempt=1" in one and "deu a sandália ao Boaz" in one
    assert "attempt=2" in two and "o Boaz ficou com ela" in two, (
        "o segundo reenvio do mesmo turno não era contado"
    )


async def test_a_send_back_on_a_rehearsal_that_handed_no_readings_is_not_reported(
    client, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    session_id = await an_open_session(client)
    agent = the_models_answer(monkeypatch, None, regenerating("deu a sandália ao Boaz"), None, None)

    with caplog.at_level(logging.WARNING, logger=passage_turn.__name__):
        sent = await a_sent_rehearsal(client, session_id, "S3")

    assert sent.status_code == 200, sent.text
    assert len(agent.guide_systems) == 2, "o Validador não mandou o rascunho de volta"
    assert the_sendbacks_said(caplog) == [], (
        "um reenvio num turno sem leituras aceitas entrava na contagem dos que as contradizem"
    )


async def test_a_draft_the_validator_lets_stand_on_a_checking_turn_is_not_reported(
    client, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    session_id = await an_open_session(client)
    the_models_answer(monkeypatch)

    with caplog.at_level(logging.WARNING, logger=passage_turn.__name__):
        sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    assert the_sendbacks_said(caplog) == [], (
        "um rascunho aprovado de primeira entrava na contagem dos reenvios"
    )


async def test_the_golden_send_answers_with_the_ids_of_the_readings_the_guide_was_handed(
    client, monkeypatch, db_session: AsyncSession
) -> None:
    session_id = await an_open_session(client)
    the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    assert sent.json().get("acceptedIds") == ["R5"], (
        "a resposta do envio dourado não dizia quais leituras aceitas o Guia recebeu"
    )
    stored = await room_service.get_session(db_session, session_id)
    await db_session.refresh(stored)
    *_, guide = stored.messages
    assert guide["accepted_ids"] == sent.json()["acceptedIds"]


async def test_the_golden_send_of_a_scene_with_no_ruling_says_nothing_of_accepted_ids(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    the_models_answer(monkeypatch)

    sent = await a_sent_rehearsal(client, session_id, "S3")

    assert sent.status_code == 200, sent.text
    assert "acceptedIds" not in sent.json(), (
        "a resposta do envio de uma cena sem leituras aceitas trazia a chave vazia"
    )


async def test_an_ordinary_golden_turn_says_nothing_of_accepted_ids(client, monkeypatch) -> None:
    session_id = await an_open_session(client)
    the_models_answer(monkeypatch)

    typed = await client.post(
        f"{GOLDEN}/turn", json={"sessionId": session_id, "teamText": SANDAL[0]}
    )

    assert typed.status_code == 200, typed.text
    assert "acceptedIds" not in typed.json(), (
        "a resposta de um turno comum trazia a chave de leituras aceitas"
    )


async def test_the_golden_send_counts_the_send_back_the_validator_made_on_the_readings_turn(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    agent = the_models_answer(monkeypatch, None, regenerating("deu a sandália ao Boaz"), None, None)

    sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    assert len(agent.guide_systems) == 2, "o Validador não mandou o rascunho de volta"
    assert sent.json().get("acceptedSendBacks") == 1, (
        "a resposta do envio dourado não contava o reenvio do Validador num turno com leituras"
    )


async def test_the_golden_send_counts_every_send_back_of_the_turn_not_only_the_first(
    client, monkeypatch
) -> None:
    session_id = await an_open_session(client)
    first, second = regenerating("deu a sandália ao Boaz"), regenerating("o Boaz ficou com ela")
    the_models_answer(monkeypatch, None, first, None, second)

    sent = await a_sent_rehearsal(client, session_id, "S4")

    assert sent.status_code == 200, sent.text
    assert sent.json().get("acceptedSendBacks") == 2, (
        "a resposta do envio dourado contava só um dos dois reenvios do mesmo turno"
    )
