"""ENG-1219 — a session keeps the canon it opened with until its passage is approved.

Her ruling of 1 October: «It keeps the map it was opened with until it is approved.» A new
canon is published here the way a re-pin publishes one: the canon served until then is kept
under its pin, and the room serves the vendored files at a new pin. The kept P03 map is told
in a line the vendored one does not have, so which map a turn read is read off the prompts
the voice and the Validator were handed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.hearing import HeardSpeech
from tests.canon_harness import the_canon_moves_on
from tests.opening_harness import the_tablet_opens
from tests.release_harness import P, a_claimed_device
from tests.room_harness import room_client, the_bucket_is_in_memory, the_room_speaks
from tests.tablet_turn_harness import the_team_says, the_turn_is_scripted

NEW_PIN = "a" * 40
VENDORED_LINE = "Close-up and slow."
KEPT_LINE = "THE KEPT MAP TELLS IT CLOSE AND SLOW."
VENDORED_P01_ARC = "The passage opens wide, on a whole era,"
KEPT_P01_ARC = "THE KEPT FIRST PASSAGE OPENS ON A WHOLE ERA,"


def _the_kept_p03_is_told_its_own_way(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P03-*.md")
    page.write_text(page.read_text(encoding="utf-8").replace(VENDORED_LINE, KEPT_LINE))


def _the_kept_p01_opens_its_own_way(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P01-*.md")
    page.write_text(page.read_text(encoding="utf-8").replace(VENDORED_P01_ARC, KEPT_P01_ARC))


class Prompts:
    def __init__(self) -> None:
        self.read: list[str] = []

    def since(self, start: int) -> list[str]:
        return self.read[start:]


@pytest.fixture()
def prompts(monkeypatch: pytest.MonkeyPatch) -> Prompts:
    handed = Prompts()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Rute disse que ia junto com Noemi")

    async def model(*, system_prompt: str, user_content: str, **_: Any) -> str:
        handed.read.append(system_prompt + "\n" + user_content)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "O que mais voces lembram da estrada?"

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    return handed


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def _pin_of(per_request: async_sessionmaker[AsyncSession], session_id: str) -> str | None:
    async with per_request() as fresh:
        return await fresh.scalar(select(IRSession.canon_pin).where(IRSession.id == session_id))


async def test_a_session_open_when_a_new_canon_is_published_still_hands_the_voice_and_the_validator_its_own_map(  # noqa: E501
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    _, tablet = await a_claimed_device(db_session)
    _, newcomer = await a_claimed_device(db_session, email="nov@example.com")
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await the_team_says(client, tablet, opened["session_id"], "antes")

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_is_told_its_own_way)
    after = await the_tablet_opens(client, newcomer, {"pericope": P, "language": "pt"})
    await the_team_says(client, newcomer, after["session_id"], "na nova")
    start = len(prompts.read)
    await the_team_says(client, tablet, opened["session_id"], "depois")
    guide, validator = prompts.since(start)

    assert KEPT_LINE in guide, "a voz leu o mapa novo no meio da sessão"
    assert KEPT_LINE in validator, "o Validador conferiu contra o mapa novo"
    assert VENDORED_LINE not in guide and VENDORED_LINE not in validator


async def test_the_story_so_far_of_a_session_open_when_a_new_canon_is_published_is_its_own_canons(
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    _, tablet = await a_claimed_device(db_session)
    _, newcomer = await a_claimed_device(db_session, email="nov@example.com")
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p01_opens_its_own_way)
    after = await the_tablet_opens(client, newcomer, {"pericope": P, "language": "pt"})
    await the_team_says(client, newcomer, after["session_id"], "na nova")
    start = len(prompts.read)
    await the_team_says(client, tablet, opened["session_id"], "depois")
    guide, validator = prompts.since(start)

    assert KEPT_P01_ARC in guide, "a voz contou a história até aqui pelo canon novo"
    assert KEPT_P01_ARC in validator, "o Validador leu a história até aqui do canon novo"
    assert VENDORED_P01_ARC not in guide and VENDORED_P01_ARC not in validator


async def test_a_passage_first_opened_after_a_new_canon_records_it_and_reads_the_vendored_map_as_today(  # noqa: E501
    client, db_session, per_request, prompts, monkeypatch, tmp_path
) -> None:
    _, earlier_tablet = await a_claimed_device(db_session, email="ant@example.com")
    _, later_tablet = await a_claimed_device(db_session, email="dep@example.com")
    earlier = await the_tablet_opens(client, earlier_tablet, {"pericope": P, "language": "pt"})
    await the_team_says(client, earlier_tablet, earlier["session_id"], "antes")
    read_today = prompts.since(0)

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_is_told_its_own_way)
    later = await the_tablet_opens(client, later_tablet, {"pericope": P, "language": "pt"})
    start = len(prompts.read)
    await the_team_says(client, later_tablet, later["session_id"], "depois")
    read_after = prompts.since(start)

    guide, validator = read_after
    assert await _pin_of(per_request, later["session_id"]) == NEW_PIN
    assert read_after == read_today
    assert VENDORED_LINE in guide and VENDORED_LINE in validator
    assert KEPT_LINE not in guide and KEPT_LINE not in validator
