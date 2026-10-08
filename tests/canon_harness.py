"""What a case that stands a made-up book in place of the canon needs: the book, and the canon back.

The loader reads Marcia's maps and logs through caches, and the passages built from them are
cached in turn, so a case that points the loader at a directory of its own has to forget
everything the loader has held before it and again after it. One list, here, so that a cache
the loader gains is added in one place. Builders and constants only.
"""

from __future__ import annotations

import json
import shutil
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from app.services.internalization_room.canon import (
    book_material,
    elements,
    kept,
    labels,
    parse_map,
)


def forget_the_canon() -> None:
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()
    book_material.preservation_rules.cache_clear()
    book_material._register_complete.cache_clear()
    elements.elements_for.cache_clear()
    elements.scene_of.cache_clear()
    labels._known_pericopes.cache_clear()


def the_canon_moves_on(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pin: str,
    *,
    keeping: Callable[[Path], None] = lambda tree: None,
) -> Path:
    served = kept.deployed_pin()
    tree = tmp_path / "kept" / served
    shutil.copytree(kept.CANON_DIR / "vendor", tree / "vendor")
    shutil.copytree(kept.CANON_DIR / "element-labels", tree / "element-labels")
    shutil.copy(kept.CANON_DIR / "ui-labels.pt.json", tree / "ui-labels.pt.json")
    (tree / "vendor" / "VENDOR_PIN").write_text(f"pin_commit:       {served}\n")
    keeping(tree)
    record = tmp_path / f"{pin}.pin"
    record.write_text(f"pin_commit:       {pin}\n")
    monkeypatch.setattr(kept, "KEPT_DIR", tmp_path / "kept")
    monkeypatch.setattr(kept, "DEPLOYED_PIN", record)
    forget_the_canon()
    return tree


def a_fable_map(number: int = 1, *, sta_status: str = "complete") -> str:
    return textwrap.dedent(
        f"""\
        ---
        type: "pericope"
        pericope-num: "Q0{number}"
        pericope-title: "A fixture, not canon"
        bcv: "Fable 1:{number}-{number + 1}"
        genre-group: "NARRATIVE"
        genre: "HISTORICAL_NARRATIVE"
        status: "complete"
        sta-status: "{sta_status}"
        ---

        # Q0{number} — Fable 1:{number}-{number + 1}

        ## 2. Level 1 — Whole-Passage Movement
        ### 2.1 Prose Arc
        Someone stands somewhere, and the telling stops there.

        ### 2.2 Context
        None. This passage exists only inside this test.

        ### 2.3 Emotion / Tone / Pace
        Flat, because nothing happens.

        ### 2.4 Communicative Function
        To be walked, or to be refused at the door of the room.

        ## 3. Level 2 — Scenes / Episodes

        ### Scene 1 — The only scene (v.{number}-{number + 1})

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


_A_RULE = {
    "id": "R1",
    "kind": "SILENCE",
    "note": "The telling never says why.",
    "do_not_decide": True,
    "required_in_audit": True,
}


def _a_fable_log(audit: list[dict], checklist: dict | None = None) -> str:
    body: dict = {"high_risk_register_audit": audit}
    if checklist is not None:
        body["validation_checklist"] = checklist
    return "# COMPILATION LOG\n\n" + json.dumps(body, indent=2) + "\n"


A_FABLE_LOG_WITH_A_LAYER = _a_fable_log([_A_RULE])
A_FABLE_LOG_WITHOUT_ONE = _a_fable_log([])
A_FABLE_LOG_WITH_A_COMPLETE_REGISTER = _a_fable_log(
    [_A_RULE], {"high_risk_register_complete": True}
)
A_FABLE_LOG_WITH_AN_INCOMPLETE_REGISTER = _a_fable_log(
    [_A_RULE], {"high_risk_register_complete": False}
)
