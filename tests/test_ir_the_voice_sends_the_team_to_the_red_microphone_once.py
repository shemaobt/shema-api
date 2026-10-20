"""ENG-1367 — the voice sends the team to the red microphone once, and answers as hers.

Witness only: her Guide and Validator already say what the ticket asks, and these cases read
them as the room sends them (`get_prompt_text`, the body between her markers). The byte pin
itself is ENG-1238's test (`test_her_eight_prompts_in_use_are_stored_at_the_fingerprints_
appendix_a_lists`); the last case ties the two files to the freeze pin, cited and not copied.

The sentences are written out here from the ticket, never imported from the room.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRPromptKey, IRTake, IRTakeKind
from app.services.internalization_room import background
from app.services.internalization_room.prompts import get_prompt_text
from scripts.sync_doctrine import FREEZE_FILE, REPO_ROOT, digest, read_pin
from tests.canon_harness import forget_the_prompts
from tests.hard_stretch_harness import a_session, rehearse
from tests.room_harness import the_bucket_is_in_memory, the_room_speaks
from tests.scene_rehearsal_harness import IR, a_room, recorded, translated
from tests.turn_harness import the_room_agent_is

MICROPHONE_PT = (
    "Quando estiverem prontos, toquem no microfone vermelho, gravem o ensaio desta cena "
    "e traduzam pra mim frase por frase."
)
MICROPHONE_EN = (
    "When you are ready, tap the red microphone, record this scene's rehearsal, "
    "and translate it for me phrase by phrase."
)
ORAL_TELLING_BACK = "me contem em português"
BOUNDARY_QUESTIONS = (
    "Isso entrou no ensaio",
    "ensaio na língua de vocês?",
    "Did this scene go into your rehearsal",
)
RED_MICROPHONE = ("microfone vermelho", "red microphone")
NOT_AN_INSTRUCTION = ("never", "a team recorded", "went back to")


@pytest.fixture(autouse=True)
def her_prompts_as_stored():
    forget_the_prompts()
    yield
    forget_the_prompts()


def between(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


def quoted(text: str) -> list[str]:
    return re.findall(r'\*"(.+?)"\*', text)


def the_articulation_item() -> str:
    guide = get_prompt_text(IRPromptKey.GUIDE)
    return between(guide, "3. **Open the part, then", "4. **Take what they bring back")


def the_send_off_item() -> str:
    guide = get_prompt_text(IRPromptKey.GUIDE)
    return between(guide, "7. **The send-off", "This shape is a compass")


def test_the_articulation_ends_with_her_one_microphone_sentence_in_each_language() -> None:
    guide = get_prompt_text(IRPromptKey.GUIDE)
    articulation = the_articulation_item()

    assert guide.count(MICROPHONE_PT) == 1
    assert guide.count(MICROPHONE_EN) == 1
    assert (
        articulation.index("the fenced block described under")
        < articulation.index(MICROPHONE_PT)
        < articulation.index(MICROPHONE_EN)
        < articulation.index(ORAL_TELLING_BACK)
    )
    assert "Agora podem ensaiar." in guide
    assert "the one microphone instruction, and nothing after it" in guide


def test_the_voice_is_never_told_to_ask_for_an_oral_telling_back_beside_the_microphone() -> None:
    guide = get_prompt_text(IRPromptKey.GUIDE)
    articulation = the_articulation_item()

    assert guide.count(ORAL_TELLING_BACK) == 1
    forbidding = next(
        sentence
        for sentence in re.split(r"(?<=[.:])\s+", articulation)
        if ORAL_TELLING_BACK in sentence
    )
    assert forbidding.startswith(
        "**Never also ask them, in the same turn, to tell you back orally**"
    )
    sentences = quoted(articulation)
    assert sentences[:2] == [MICROPHONE_PT, MICROPHONE_EN]
    assert len(sentences) == 3
    assert ORAL_TELLING_BACK in sentences[2]


def test_the_validator_keeps_her_microphone_sentence_word_for_word_when_it_corrects() -> None:
    validator = get_prompt_text(IRPromptKey.VALIDATOR)
    fixed_lines = next(
        line
        for line in validator.splitlines()
        if line.startswith("- **The session's fixed lines.**")
    )

    assert "keep each of them word for word" in fixed_lines
    assert MICROPHONE_PT in fixed_lines
    assert MICROPHONE_EN in fixed_lines
    assert ORAL_TELLING_BACK not in validator
    assert "both halves" not in validator.lower()


def test_the_send_off_sends_the_team_to_the_orange_dot_and_never_to_the_red_microphone() -> None:
    send_off = the_send_off_item()
    sentences = quoted(send_off)

    assert any("ponto laranja" in sentence for sentence in sentences)
    assert any("orange dot" in sentence for sentence in sentences)
    assert not [
        sentence for sentence in sentences if any(name in sentence for name in RED_MICROPHONE)
    ]
    assert "Never the red microphone here." in send_off
    naming_it = [
        sentence
        for sentence in re.split(r"(?<=[.!?])\s+", send_off)
        if any(name in sentence for name in RED_MICROPHONE)
    ]
    assert [
        sentence
        for sentence in naming_it
        if not any(marker in sentence.lower() for marker in NOT_AN_INSTRUCTION)
    ] == []


def test_a_rehearsal_after_the_send_off_is_checked_and_closed_again_by_the_orange_dot() -> None:
    send_off = the_send_off_item()
    after = send_off[send_off.index("**After the send-off:**") :]

    assert "check it as any other telling" in after
    assert "close again with the same single instruction (the orange dot)" in after
    closing = "close again with the same single instruction (the orange dot)"
    assert not [name for name in RED_MICROPHONE if name in after.split(closing, 1)[1]]


@pytest.mark.parametrize("key", list(IRPromptKey), ids=lambda key: key.name)
def test_no_prompt_the_room_sends_asks_whether_a_scene_went_into_the_rehearsal(
    key: IRPromptKey,
) -> None:
    body = get_prompt_text(key)

    assert [question for question in BOUNDARY_QUESTIONS if question in body] == []


@pytest.mark.parametrize("name", ["guide_system_prompt.md", "validator_system_prompt.md"])
def test_her_guide_and_validator_are_sent_at_the_freeze_pin(name: str) -> None:
    path = f"app/services/internalization_room/prompts/{name}"

    assert digest((REPO_ROOT / path).read_bytes()) == read_pin(FREEZE_FILE).digests[path]


@pytest.fixture()
async def room(db_session, rival_factory, monkeypatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


@pytest.fixture()
def the_bucket(monkeypatch: pytest.MonkeyPatch, rival_factory):
    async def guide(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Isso. Vocês contaram a cena inteira."

    async def reader(**_: Any) -> str:
        return json.dumps({"decisions": [], "retelling": {"scope": "S2", "approved": True}})

    @asynccontextmanager
    async def fresh() -> AsyncIterator[AsyncSession]:
        async with rival_factory() as session:
            yield session

    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=guide, classifier=reader)
    monkeypatch.setattr(background, "AsyncSessionLocal", fresh)
    return the_bucket_is_in_memory(monkeypatch)


async def rehearsal_takes(rival_factory, session_id: str) -> list[dict[str, Any]]:
    async with rival_factory() as fresh:
        rows = await fresh.scalars(
            select(IRTake)
            .where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.ENSAIO)
            .order_by(IRTake.id)
        )
        return [{c.key: getattr(row, c.key) for c in IRTake.__table__.columns} for row in rows]


@pytest.mark.parametrize("part", [None, 1], ids=["passage_whole", "passage_in_parts"])
async def test_a_scene_rehearsal_sent_leaves_the_rehearsal_as_it_was(
    part: int | None, room, the_bucket, db_session, rival_factory
) -> None:
    session_id = await a_session(db_session, pericope="P01")
    opened = await room.client.post(f"{IR}/sessions/{session_id}/turns")
    assert opened.status_code == 200, opened.text
    passage_take = await rehearse(room.client, session_id, part=part)
    before = await rehearsal_takes(rival_factory, session_id)
    assert [take["id"] for take in before] == [passage_take]
    stores_before = (dict(the_bucket.objects), dict(room.bucket.objects))

    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 20000)])
    sent = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/send",
        data={"turn_id": "turno-da-cena"},
    )
    assert sent.status_code == 200, sent.text

    assert await rehearsal_takes(rival_factory, session_id) == before
    assert not [
        key
        for key in {*stores_before[0], *stores_before[1]}
        if the_bucket.objects.get(key) != stores_before[0].get(key)
        or room.bucket.objects.get(key) != stores_before[1].get(key)
    ]
