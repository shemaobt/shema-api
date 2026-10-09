"""ENG-659 — the room reads the checklist's own high_risk_register_complete, not a proxy.

`unwalkable` read only two signals — the preservation layer and `sta-status` — and never the
Compilation Log's own `high_risk_register_complete` flag, even though the two agree on every
vendored passage today. A synthetic canon where they disagree is the only way to tell "the
flag is read" from "the flag happens to match sta-status everywhere it has been checked."
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.services.internalization_room.canon import book_material, parse_map
from tests.canon_harness import (
    A_FABLE_LOG_WITH_AN_INCOMPLETE_REGISTER,
    a_fable_map,
    forget_the_canon,
)


@pytest.fixture
def a_passage_whose_checklist_disagrees_with_its_survey(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """A passage `sta-status` calls finished while its own checklist still calls the register open.

    Real Ruth material never disagrees, so this is the only way to tell "the flag is read"
    from "the flag happens to agree with `sta-status` everywhere it has been checked."
    """
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    maps.mkdir()
    logs.mkdir()
    (maps / "Q01-Fable-1-1-2.md").write_text(a_fable_map(), encoding="utf-8")
    (logs / "Q01-Fable-1-1-2-COMPILATION-LOG.md").write_text(
        A_FABLE_LOG_WITH_AN_INCOMPLETE_REGISTER, encoding="utf-8"
    )

    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Fable"}))
    forget_the_canon()
    yield "Q01"
    forget_the_canon()


def test_a_survey_marked_complete_does_not_open_when_its_own_checklist_is_not(
    a_passage_whose_checklist_disagrees_with_its_survey: str,
) -> None:
    """`sta-status` says the passage is finished; the checklist says its own register is not."""
    meaning_map = parse_map.load_map(a_passage_whose_checklist_disagrees_with_its_survey)

    reason = book_material.unwalkable(meaning_map)

    assert reason is not None, "a checklist that disagrees with the survey has to refuse"
    assert a_passage_whose_checklist_disagrees_with_its_survey in reason
    assert "disagree" in reason.lower(), (
        f"the refusal has to name which signal disagreed, and this one does not: {reason}"
    )
