"""A failed turn hears her A line for the draft it stopped at, and never her pause.

Her turn loop gives up at its first, second or third draft and voices the A line of that
attempt, so the first of her four is never said and nothing counts failures across turns.
"""

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus
from app.services.internalization_room.conversation import conversation_of
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.sessions import create_session, get_session
from app.services.internalization_room.verdict_turn import run_verdict_turn
from app.services.platform.tts import SynthesizedSpeech
from tests.device_harness import TABLET_TEAM
from tests.release_harness import PREFIX, P
from tests.room_harness import room_client
from tests.turn_harness import the_room_agent_is

REFUSED = json.dumps({"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]})

FIRST_DRAFT = [""]
SECOND_DRAFT = ["Rute casou com Malom.", ""]
THIRD_DRAFT = ["Rute casou com Malom."] * 3


class _DraftsInOrder:
    def __init__(self, *turns: list[str]) -> None:
        self.drafts = [draft for turn in turns for draft in turn]

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return REFUSED
        return self.drafts.pop(0)


async def _heard(*_: Any, **__: Any) -> HeardSpeech:
    return HeardSpeech(text="a fome chegou")


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/t.mp3"
    )
    return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session, monkeypatch):
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def _a_take(client, session_id: str) -> dict[str, Any]:
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


@pytest.mark.parametrize(
    ("drafts", "name", "heard"),
    [
        (
            FIRST_DRAFT,
            "A1",
            "Quero que a gente fique perto da passagem. Vamos voltar juntos a esta cena.",
        ),
        (
            SECOND_DRAFT,
            "A2",
            "Vamos com calma. Me contem o que vocês estão vendo nesta parte da história até aqui.",
        ),
        (
            THIRD_DRAFT,
            "A3",
            "Tem bastante coisa aqui. Vamos devagar e ficar mais um pouco nesta cena.",
        ),
    ],
    ids=["first-draft", "second-draft", "third-draft"],
)
async def test_a_failed_turn_hears_the_a_line_of_the_draft_it_gave_up_at_never_the_first(
    client, db_session: AsyncSession, monkeypatch, drafts: list[str], name: str, heard: str
) -> None:
    the_room_agent_is(monkeypatch, turn=_DraftsInOrder(drafts))
    session = await create_session(db_session, project_id=TABLET_TEAM, language="pt", pericope=P)

    reply = await _a_take(client, session.id)

    stored = (await get_session(db_session, session.id)).messages[-1]
    assert reply["fixed_line"] == name, (
        "a linha A era escolhida pela contagem de turnos falhos e a primeira falha dizia A-1, "
        "que ela nunca fala"
    )
    assert stored["text"] == heard


async def test_three_failed_turns_in_a_row_each_hear_their_own_draft_and_never_the_pause(
    client, db_session: AsyncSession, monkeypatch
) -> None:
    the_room_agent_is(monkeypatch, turn=_DraftsInOrder(FIRST_DRAFT, THIRD_DRAFT, SECOND_DRAFT))
    session = await create_session(db_session, project_id=TABLET_TEAM, language="pt", pericope=P)

    spoken = [(await _a_take(client, session.id))["fixed_line"] for _ in range(3)]

    assert spoken == ["A1", "A3", "A2"], (
        "a terceira falha seguida virava a pausa E e pedia o facilitador"
    )
    assert (await get_session(db_session, session.id)).status is IRSessionStatus.IN_PROGRESS


async def test_an_english_failed_turn_points_to_scene_one_and_is_voiced_with_the_pointer(
    client, db_session: AsyncSession, monkeypatch
) -> None:
    voiced: list[str] = []

    async def _voice_it(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        voiced.append(text)
        return await _voice(text)

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice_it)
    the_room_agent_is(monkeypatch, turn=_DraftsInOrder(FIRST_DRAFT))
    session = await create_session(db_session, project_id=TABLET_TEAM, language="en", pericope=P)

    reply = await _a_take(client, session.id)

    assert voiced == [
        "I want us to stay close to the passage here. Let's go back to this scene together"
        " — this is the part about naomi's last appeal."
    ], "a linha A em inglês saía pelo nome, sem o ponteiro da cena que ela acrescenta"
    assert reply["fixed_line"] == ""
    assert reply["audio_url"]


async def test_an_english_failed_turn_with_its_pointer_still_reads_as_unrepairable(
    client, db_session: AsyncSession, monkeypatch
) -> None:
    the_room_agent_is(monkeypatch, turn=_DraftsInOrder(FIRST_DRAFT))
    session = await create_session(db_session, project_id=TABLET_TEAM, language="en", pericope=P)

    await _a_take(client, session.id)

    last = conversation_of(await get_session(db_session, session.id)).turns[-1]
    assert last.fail_safe is True
    assert last.fail_safe_category == "unrepairable", (
        "a linha com o ponteiro não tinha nome, e a sala de observação perdia a categoria"
    )


async def test_an_english_telling_back_verdict_that_fails_points_to_scene_one_too(
    monkeypatch,
) -> None:
    the_room_agent_is(monkeypatch, turn=_DraftsInOrder(FIRST_DRAFT))

    outcome = await run_verdict_turn(
        findings_text='[{"kind": "addition", "frase": 1}]',
        scope=P,
        pericope_num=P,
        messages=[],
        telling_back="Naomi told them to go home.",
        speaker_prompt=get_prompt_text(IRPromptKey.BT_VERDICT_SPEAKER),
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        session_language="English",
        language_code="en",
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    assert outcome.speech == (
        "I want us to stay close to the passage here. Let's go back to this scene together"
        " — this is the part about naomi's last appeal."
    ), "o veredito da contação de volta caía na linha A sem o ponteiro que o app dela põe"
    assert outcome.fixed_line == ""
