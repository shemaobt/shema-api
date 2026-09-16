"""ENG-659 — the room reads the checklist's own high_risk_register_complete, not a proxy.

`unwalkable` read only two signals — the preservation layer and `sta-status` — and never the
Compilation Log's own `high_risk_register_complete` flag, even though the two agree on every
vendored passage today. A synthetic canon where they disagree is the only way to tell "the
flag is read" from "the flag happens to match sta-status everywhere it has been checked."
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.services.internalization_room.canon import book_material, parse_map

_DISAGREEING_MAP = textwrap.dedent(
    """\
    ---
    type: "pericope"
    pericope-num: "V01"
    pericope-title: "A fixture, not canon"
    bcv: "Fable 1:1-2"
    genre-group: "NARRATIVE"
    genre: "HISTORICAL_NARRATIVE"
    status: "complete"
    sta-status: "complete"
    ---

    # V01 — Fable 1:1-2

    ## 2. Level 1 — Whole-Passage Movement
    ### 2.1 Prose Arc
    Someone stands somewhere, and the telling stops there.

    ### 2.2 Context
    None. This passage exists only inside this test.

    ## 3. Level 2 — Scenes / Episodes

    ### Scene 1 — The only scene (v.1-2)

    **3A — Beings**
    [[B1-Someone]] — מִישֶׁהוּ / Someone

    **3B — Places**
    [[PL1-Somewhere]] — אֵיפֹשֶׁהוּ / Somewhere

    **3E — What Happens**
    Someone stands somewhere.

    **Significant Absence**
    Nobody says why.
    """
)

_LOG_WITH_AN_INCOMPLETE_REGISTER = textwrap.dedent(
    """\
    # V01 — COMPILATION LOG

    {
      "high_risk_register_audit": [
        {
          "id": "R1",
          "kind": "SILENCE",
          "note": "The telling never says why. Kept as it stands.",
          "do_not_decide": true,
          "required_in_audit": true
        }
      ],
      "validation_checklist": {
        "high_risk_register_complete": false
      }
    }
    """
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
    (maps / "V01-Fable-1-1-2.md").write_text(_DISAGREEING_MAP, encoding="utf-8")
    (logs / "V01-Fable-1-1-2-COMPILATION-LOG.md").write_text(
        _LOG_WITH_AN_INCOMPLETE_REGISTER, encoding="utf-8"
    )

    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()
    book_material.preservation_rules.cache_clear()
    book_material._register_complete.cache_clear()
    yield "V01"
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()
    book_material.preservation_rules.cache_clear()
    book_material._register_complete.cache_clear()


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
