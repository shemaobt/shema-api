from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.services.internalization_room.canon import book_material
from tests.canon_harness import forget_the_canon

HER_SENTENCE = (
    "The team has not yet lived any passage: every one of these still lies ahead of them. "
    "The panorama must honor each — never state, pair, name, or attribute what a passage "
    "withholds until its moment."
)


def test_the_ruth_notes_open_with_her_sentence_that_the_team_has_lived_nothing() -> None:
    material = book_material.build_book_material("Ruth")

    assert HER_SENTENCE in material
    assert material.index("## PRESERVATION NOTES") < material.index(HER_SENTENCE)


@pytest.fixture
def a_book_whose_logs_record_no_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    logs = tmp_path / "compilation-log"
    logs.mkdir()
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    forget_the_canon()
    yield "Ruth"
    forget_the_canon()


def test_a_book_with_no_recorded_rule_gets_none_recorded_instead_of_failing(
    a_book_whose_logs_record_no_rule: str,
) -> None:
    material = book_material.build_book_material(a_book_whose_logs_record_no_rule)

    assert material.endswith(f"{HER_SENTENCE}\n\n- (none recorded)\n")
