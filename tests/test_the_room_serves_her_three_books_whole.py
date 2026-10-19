"""ENG-1248 — the room serves her pinned canon whole: Esther, Jonah and Ruth at 5b5c8d2.

Every expected value is hers: the ids, counts and references of her maps at the pin, the order
of her `listPericopes` (every map, sorted by id), one `◈` Panorama `OV-<book>` first in each
book's list, and her approved Panorama line for Ruth. The cases go through the room's doors
with a claimed tablet; the only stand-in is the synthesiser, the provider the lines are voiced
by.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import passages as route
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.voice_handles import clip_url
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client

ESTHER = [f"E{number:02d}" for number in range(1, 19)]
JONAH = [f"J{number:02d}" for number in range(1, 6)]
RUTH = [f"P{number:02d}" for number in range(1, 15)]

#: Her Ruth Panorama line, approved on 2026-09-21.
RUTH_PANORAMA_PT = "Rute — o livro inteiro"


class Voice:
    """The synthesiser: each line it is asked for gets a key of its own, and it remembers."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.refuses: set[str] = set()

    def key_of(self, text: str) -> str:
        return f"tts/v/{abs(hash(text))}.mp3"

    async def __call__(self, text: str, **_: object) -> tuple[SimpleNamespace, bool]:
        self.asked.append(text)
        if text in self.refuses:
            raise RuntimeError("ElevenLabs answered 503")
        return SimpleNamespace(key=self.key_of(text)), False


@pytest.fixture()
def voice(monkeypatch: pytest.MonkeyPatch) -> Voice:
    speaking = Voice()
    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", speaking)
    return speaking


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, voice: Voice
) -> AsyncIterator[httpx.AsyncClient]:
    async with room_client(db_session, monkeypatch) as served:
        yield served


@pytest.fixture()
async def tablet(db_session: AsyncSession) -> dict[str, str]:
    _, credential = await a_claimed_device(db_session)
    return team_headers(credential)


async def the_list_of(
    client: httpx.AsyncClient, tablet: dict[str, str], book: str, language: str = "pt"
) -> list[dict]:
    answer = await client.get(
        f"{PREFIX}/books/{book}/passages", params={"language": language}, headers=tablet
    )
    assert answer.status_code == 200, answer.text[:300]
    passages: list[dict] = answer.json()["passages"]
    return passages


async def opened(
    client: httpx.AsyncClient, tablet: dict[str, str], pericope: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions", headers=tablet, json={"pericope": pericope, "language": "pt"}
    )


async def test_the_room_serves_her_three_books_in_the_order_of_their_passage_ids(
    client: httpx.AsyncClient, tablet: dict[str, str]
) -> None:
    answer = await client.get(f"{PREFIX}/books", headers=tablet)

    assert answer.status_code == 200, answer.text[:300]
    assert answer.json() == {"books": ["Esther", "Jonah", "Ruth"]}


@pytest.mark.parametrize(
    ("book", "passages"), [("Esther", ESTHER), ("Jonah", JONAH), ("Ruth", RUTH)]
)
async def test_each_book_offers_every_published_passage_of_her_pin_in_story_order(
    client: httpx.AsyncClient, tablet: dict[str, str], book: str, passages: list[str]
) -> None:
    listed = await the_list_of(client, tablet, book)

    assert [entry["pericope"] for entry in listed[1:]] == passages


@pytest.mark.parametrize("book", ["Esther", "Jonah", "Ruth"])
async def test_each_book_opens_with_its_own_panorama_and_only_one(
    client: httpx.AsyncClient, tablet: dict[str, str], book: str
) -> None:
    listed = await the_list_of(client, tablet, book)

    first = listed[0]
    assert {key: first[key] for key in ("pericope", "kind", "reference", "approved")} == {
        "pericope": f"OV-{book}",
        "kind": "panorama",
        "reference": None,
        "approved": False,
    }
    assert [entry["kind"] for entry in listed[1:]].count("panorama") == 0


@pytest.mark.parametrize(
    ("book", "pericope", "reference"),
    [
        ("Esther", "E01", "Esther 1:1\N{EN DASH}9"),
        ("Jonah", "J02", "Jonah 1:4\N{EN DASH}2:1"),
        ("Ruth", "P01", "Ruth 1:1\N{EN DASH}5"),
        ("Ruth", "P06", "Ruth 2:8-16"),
    ],
)
async def test_each_passage_carries_its_reference_as_her_heading_writes_it(
    client: httpx.AsyncClient, tablet: dict[str, str], book: str, pericope: str, reference: str
) -> None:
    listed = await the_list_of(client, tablet, book)

    assert {entry["pericope"]: entry["reference"] for entry in listed}[pericope] == reference


@pytest.mark.parametrize(("pericope", "book"), [("J01", "Jonah"), ("E01", "Esther")])
async def test_no_passage_is_held_back_for_a_skeleton_register_a_pending_survey_or_a_disagreeing_checklist(  # noqa: E501
    client: httpx.AsyncClient, tablet: dict[str, str], pericope: str, book: str
) -> None:
    session = await opened(client, tablet, pericope)
    listed = await the_list_of(client, tablet, book)

    assert session.status_code == 200, session.text[:300]
    assert session.json()["pericope"] == pericope
    assert pericope in [entry["pericope"] for entry in listed]


async def test_jonahs_prayer_from_the_deep_is_read_like_any_other_map(
    client: httpx.AsyncClient, tablet: dict[str, str]
) -> None:
    prayer = load_map("J03")
    listed = await the_list_of(client, tablet, "Jonah")

    assert prayer.reference == "Jonah 2:2\N{EN DASH}9"
    assert [(scene.number, scene.verses) for scene in prayer.scenes] == [
        (1, "2:2; Heb 2:3"),
        (2, "2:3\N{EN DASH}4; Heb 2:4\N{EN DASH}5"),
        (3, "2:5\N{EN DASH}7; Heb 2:6\N{EN DASH}8"),
        (4, "2:8\N{EN DASH}9; Heb 2:9\N{EN DASH}10"),
    ]
    assert "J03" in [entry["pericope"] for entry in listed]


@pytest.mark.parametrize("book", ["Jonah", "Esther"])
async def test_a_books_panorama_opens(
    client: httpx.AsyncClient, tablet: dict[str, str], book: str
) -> None:
    session = await opened(client, tablet, f"OV-{book}")

    assert session.status_code == 200, session.text[:300]
    assert session.json()["pericope"] == f"OV-{book}"


async def test_the_panorama_of_a_book_the_room_does_not_serve_is_refused_at_the_open(
    client: httpx.AsyncClient, tablet: dict[str, str], db_session: AsyncSession
) -> None:
    refused = await opened(client, tablet, "OV-Fable")

    assert refused.status_code == 400, refused.text[:300]
    assert await db_session.scalar(select(func.count()).select_from(IRSession)) == 0


async def test_an_entry_with_no_spoken_line_is_offered_with_no_sound_and_ruth_keeps_hers(
    client: httpx.AsyncClient, tablet: dict[str, str], voice: Voice
) -> None:
    jonah = await the_list_of(client, tablet, "Jonah")
    asked_for_jonah = list(voice.asked)
    ruth = {entry["pericope"]: entry for entry in await the_list_of(client, tablet, "Ruth")}

    assert [entry["audio_url"] for entry in jonah] == [None] * 6
    assert asked_for_jonah == []
    assert ruth["P01"]["audio_url"]
    assert ruth["OV-Ruth"]["audio_url"] == clip_url(voice.key_of(RUTH_PANORAMA_PT))


@pytest.mark.parametrize("pericope", RUTH[7:])
async def test_ruth_p08_to_p14_are_offered_and_each_opens_a_session(
    client: httpx.AsyncClient, tablet: dict[str, str], pericope: str
) -> None:
    listed = await the_list_of(client, tablet, "Ruth")
    session = await opened(client, tablet, pericope)

    assert pericope in [entry["pericope"] for entry in listed]
    assert session.status_code == 200, session.text[:300]
    assert session.json()["pericope"] == pericope


async def test_a_passage_whose_line_cannot_be_voiced_is_offered_with_no_sound_and_the_list_is_still_served(  # noqa: E501
    client: httpx.AsyncClient, tablet: dict[str, str], voice: Voice
) -> None:
    voice.refuses.add("Rute 1:1\N{EN DASH}5")

    listed = {entry["pericope"]: entry for entry in await the_list_of(client, tablet, "Ruth")}

    assert "Rute 1:1\N{EN DASH}5" in voice.asked
    assert listed["P01"]["audio_url"] is None
    assert all(listed[pericope]["audio_url"] for pericope in RUTH[1:])
    assert listed["OV-Ruth"]["audio_url"]
