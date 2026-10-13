from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import passages as route
from app.core.exceptions import ValidationError
from app.services.internalization_room.canon import book_material, parse_map
from app.services.internalization_room.sessions import create_session
from tests.canon_harness import HER_CANON, forget_the_canon

RUTH_PASSAGES = [f"P{number:02d}" for number in range(1, 15)]


async def _instantly_voiced(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
    return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False


@pytest.fixture
def ruth_jonah_and_esther_are_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    shutil.copytree(parse_map.MAPS_DIR, maps)
    shutil.copytree(book_material.LOGS_DIR, logs)
    shutil.copytree(HER_CANON / "meaning-map", maps, dirs_exist_ok=True)
    shutil.copytree(HER_CANON / "compilation-log", logs, dirs_exist_ok=True)
    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Jonah", "Esther"}))
    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instantly_voiced)
    forget_the_canon()
    yield
    forget_the_canon()


async def test_the_menu_offers_ruths_fourteen_passages_behind_the_ruth_panorama(
    db_session: AsyncSession, ruth_jonah_and_esther_are_served: None
) -> None:
    answer = await route.passages("Ruth", language="pt", db=db_session)

    assert [view.pericope for view in answer.passages] == ["panorama", *RUTH_PASSAGES]


@pytest.mark.parametrize("book", ["Jonah", "Esther"])
async def test_the_menu_offers_no_panorama_for_a_book_none_of_whose_passages_opens(
    db_session: AsyncSession, ruth_jonah_and_esther_are_served: None, book: str
) -> None:
    answer = await route.passages(book, language="pt", db=db_session)

    assert answer.passages == []


@pytest.mark.parametrize("book", ["Jonah", "Esther"])
async def test_the_panorama_of_a_book_none_of_whose_passages_opens_is_refused_at_the_open(
    db_session: AsyncSession, ruth_jonah_and_esther_are_served: None, book: str
) -> None:
    with pytest.raises(
        ValidationError, match=f"the {book} Panorama: no passage of the {book} canon opens"
    ):
        await create_session(db_session, pericope=f"OV-{book}")


async def test_the_ruth_panorama_still_opens_beside_the_closed_books(
    db_session: AsyncSession, ruth_jonah_and_esther_are_served: None
) -> None:
    session = await create_session(db_session, pericope="OV-Ruth")

    assert session.pericope == "OV-Ruth"
