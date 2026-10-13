from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon import book_material, parse_map
from app.services.internalization_room.progression import resolve
from app.services.internalization_room.sessions import create_session
from tests.canon_harness import (
    A_FABLE_LOG_WITH_A_COMPLETE_REGISTER_AND_NO_RULE,
    A_FABLE_LOG_WITH_A_LAYER,
    A_FABLE_LOG_WITH_A_SKELETON_IN_A_COMPLETE_REGISTER,
    a_fable_map,
    forget_the_canon,
)


@pytest.fixture
def a_passage_with_its_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[str], str]]:
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    maps.mkdir()
    logs.mkdir()
    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Fable"}))

    def written(log: str) -> str:
        (maps / "Q01-Fable-1-1-2.md").write_text(a_fable_map(), encoding="utf-8")
        (logs / "Q01-Fable-1-1-2-COMPILATION-LOG.md").write_text(log, encoding="utf-8")
        forget_the_canon()
        return "Q01"

    yield written
    forget_the_canon()


async def test_a_log_that_does_not_mark_the_register_complete_keeps_the_passage_closed(
    db_session: AsyncSession, a_passage_with_its_log: Callable[[str], str]
) -> None:
    pericope = a_passage_with_its_log(A_FABLE_LOG_WITH_A_LAYER)

    reason = book_material.unwalkable(parse_map.load_map(pericope))

    assert reason is not None
    assert pericope in reason
    with pytest.raises(ValidationError):
        await create_session(db_session, pericope=pericope)


def test_a_passage_whose_three_signals_agree_opens_with_no_preservation_rule_recorded(
    a_passage_with_its_log: Callable[[str], str],
) -> None:
    pericope = a_passage_with_its_log(A_FABLE_LOG_WITH_A_COMPLETE_REGISTER_AND_NO_RULE)

    assert book_material.unwalkable(parse_map.load_map(pericope)) is None
    assert resolve(set(), book="Fable") == pericope


async def test_a_register_holding_a_skeleton_entry_keeps_the_passage_closed_though_marked_complete(
    db_session: AsyncSession, a_passage_with_its_log: Callable[[str], str]
) -> None:
    pericope = a_passage_with_its_log(A_FABLE_LOG_WITH_A_SKELETON_IN_A_COMPLETE_REGISTER)

    reason = book_material.unwalkable(parse_map.load_map(pericope))

    assert reason is not None
    assert pericope in reason
    assert resolve(set(), book="Fable") is None
    with pytest.raises(ValidationError):
        await create_session(db_session, pericope=pericope)
