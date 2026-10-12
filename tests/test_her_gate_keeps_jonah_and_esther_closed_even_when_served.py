from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon import book_material, parse_map
from app.services.internalization_room.progression import resolve
from app.services.internalization_room.sessions import create_session
from tests.canon_harness import HER_CANON, forget_the_canon


@pytest.fixture
def jonah_and_esther_are_served(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(parse_map, "MAPS_DIR", HER_CANON / "meaning-map")
    monkeypatch.setattr(book_material, "LOGS_DIR", HER_CANON / "compilation-log")
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Jonah", "Esther"}))
    forget_the_canon()
    yield
    forget_the_canon()


@pytest.mark.parametrize("pericope", ["J01", "J02", "J03", "J04", "J05", "E01"])
async def test_a_passage_of_jonah_or_esther_is_refused_at_the_open_though_its_book_is_served(
    db_session: AsyncSession, jonah_and_esther_are_served: None, pericope: str
) -> None:
    assert book_material.unwalkable(parse_map.load_map(pericope)) is not None
    with pytest.raises(ValidationError):
        await create_session(db_session, pericope=pericope)


@pytest.mark.parametrize("book", ["Jonah", "Esther"])
def test_the_progression_never_lands_a_team_on_jonah_or_esther(
    jonah_and_esther_are_served: None, book: str
) -> None:
    assert resolve(set(), book=book) is None
