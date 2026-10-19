"""ENG-1248 — a passage's beads, story so far and Validator material come from its own book.

The references are her headings at the pin 5b5c8d2; the Panorama header and «- (none
recorded)» are what her `buildOverviewContext` renders for a book with no rule. What reached
the Guide, the Validator or the Panorama voice is read off the model seam's fake; nothing
asserts what the fake itself answered.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession, IRSessionStatus
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import run_turn
from app.services.internalization_room.sessions import get_session
from app.services.internalization_room.verdict_turn import run_verdict_turn
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client
from tests.tablet_turn_harness import the_room_opens, the_turn_is_scripted
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
VERDICT_SPEAKER = default_prompt(IRPromptKey.BT_VERDICT_SPEAKER)["prompt"]

JONAH_REFERENCES = (
    "Jonah 1:1\N{EN DASH}3",
    "Jonah 1:4\N{EN DASH}2:1",
    "Jonah 2:2\N{EN DASH}9",
    "Jonah 2:10\N{EN DASH}3:10",
    "Jonah 4:1\N{EN DASH}11",
)
JONAH_HEADER = (
    "# THE BOOK OF JONAH \N{EM DASH} passage digests (map-authored; 5 passages, in story order)"
)
NONE_RECORDED = "- (none recorded)"
STORY_SO_FAR = "# THE STORY SO FAR"

#: A Ruth map grounded in the prompt, or a Ruth digest: what a passage of another book
#: reads when its book falls back to Ruth.
RUTH_MATERIAL = re.compile(r"^# P\d{2} \N{EM DASH} Ruth |\*\*Ruth \d+:\d+", re.M)


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class Heard:
    """The model seam: every system prompt the room handed it, the Validator's apart."""

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.judged: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.judged.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.spoken.append(system_prompt)
        return "Vamos ouvir a passagem."


@pytest.fixture()
def heard(monkeypatch: pytest.MonkeyPatch) -> Heard:
    models = Heard()
    the_room_agent_is(monkeypatch, turn=models)
    return models


@pytest.fixture()
def the_room(monkeypatch: pytest.MonkeyPatch) -> Heard:
    models = Heard()

    async def nothing_said(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="")

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=nothing_said, model=models)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return models


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, the_room: Heard
) -> AsyncIterator[httpx.AsyncClient]:
    async with room_client(db_session, monkeypatch) as served:
        yield served


async def _opened(client: httpx.AsyncClient, credential: str, pericope: str) -> str:
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(credential),
        json={"pericope": pericope, "language": "pt"},
    )
    assert opened.status_code == 200, opened.text[:300]
    session_id: str = opened.json()["session_id"]
    return session_id


def _in_order(text: str, references: tuple[str, ...]) -> bool:
    places = [text.find(f"**{reference}**") for reference in references]
    return -1 not in places and places == sorted(places)


async def test_jonah_1_1_3_opens_on_its_own_map(
    client: httpx.AsyncClient, db_session: AsyncSession, the_room: Heard
) -> None:
    _, credential = await a_claimed_device(db_session)
    session_id = await _opened(client, credential, "J01")

    await the_room_opens(client, credential, session_id)
    necklace = (await get_session(db_session, session_id)).coverage_state or {}

    guide = the_room.spoken[0]
    assert "# J01 \N{EM DASH} Jonah 1:1\N{EN DASH}3" in guide
    assert RUTH_MATERIAL.search(guide) is None
    assert {key for key in necklace if key.startswith("scene:")} == {"scene:S1", "scene:S2"}
    assert [key for key in necklace if key.startswith("preserved:")] == []


async def test_the_story_so_far_of_a_jonah_passage_is_jonahs_earlier_passages(
    heard: Heard,
) -> None:
    await run_turn(
        transcript="",
        coverage_state={},
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num="J04",
        language_code="pt",
        opening=True,
        settings=_settings(),
    )

    guide = heard.spoken[0]
    assert STORY_SO_FAR in guide
    story = guide[guide.index(STORY_SO_FAR) :]
    assert _in_order(story, JONAH_REFERENCES[:3])
    assert f"**{JONAH_REFERENCES[3]}**" not in story
    assert RUTH_MATERIAL.search(guide) is None


async def test_the_verdict_of_a_jonah_passage_reads_jonahs_map(heard: Heard) -> None:
    await run_verdict_turn(
        findings_text='[{"kind": "addition", "frase": 1}]',
        scope="J02",
        pericope_num="J02",
        messages=[],
        telling_back="Jonas fugiu e o mar se agitou.",
        speaker_prompt=VERDICT_SPEAKER,
        validator_prompt=VALIDATOR,
        language_code="pt",
        settings=_settings(),
    )

    judged = heard.judged[0]
    assert "# J02 \N{EM DASH} Jonah 1:4\N{EN DASH}2:1" in judged
    assert f"**{JONAH_REFERENCES[0]}**" in judged
    assert RUTH_MATERIAL.search(judged) is None


async def test_the_panorama_of_jonah_speaks_only_from_jonahs_material(
    client: httpx.AsyncClient, db_session: AsyncSession, the_room: Heard
) -> None:
    _, credential = await a_claimed_device(db_session)
    session_id = await _opened(client, credential, "OV-Jonah")

    await the_room_opens(client, credential, session_id)

    voiced = the_room.spoken[0]
    assert JONAH_HEADER in voiced
    material = voiced[voiced.index(JONAH_HEADER) :]
    material = material[: material.index(NONE_RECORDED) + len(NONE_RECORDED)]
    assert _in_order(material, JONAH_REFERENCES)
    assert all(word not in material for word in ("Ruth", "Rute", "P01"))


def test_the_panorama_of_esther_lists_her_eighteen_passages_and_no_rule() -> None:
    material = build_book_material("Esther")

    assert material.startswith(
        "# THE BOOK OF ESTHER \N{EM DASH} passage digests "
        "(map-authored; 18 passages, in story order)"
    )
    assert material.split("\n\n")[1].startswith("**Esther 1:1\N{EN DASH}9**")
    assert material.rstrip().endswith(NONE_RECORDED)


async def _prepared_after(db: AsyncSession, panorama: str, monkeypatch: pytest.MonkeyPatch) -> str:
    async def voiced(text: str, **_: Any) -> tuple[Any, bool]:
        return (type("Voiced", (), {"key": "tts/v/abertura.mp3"})(), False)

    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", voiced)
    team, _ = await a_claimed_device(db)
    session = IRSession(
        pericope=panorama,
        project_id=team.id,
        status=IRSessionStatus.IN_PROGRESS,
        messages=[],
        coverage_state={},
        back_translation={},
        language="pt",
    )
    db.add(session)
    await db.commit()

    await prepare_opening_module.prepare_opening(session.id)

    await db.refresh(session)
    assert session.prepared_pericope is not None, "nothing was prepared"
    return session.prepared_pericope


async def test_the_panorama_of_jonah_prepares_jonahs_first_passage(
    db_session: AsyncSession, heard: Heard, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await _prepared_after(db_session, "OV-Jonah", monkeypatch) == "J01"


async def test_ruth_still_prepares_ruths_next_passage_after_its_panorama(
    db_session: AsyncSession, heard: Heard, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await _prepared_after(db_session, "OV-Ruth", monkeypatch) == "P01"
