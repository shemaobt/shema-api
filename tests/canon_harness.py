"""What a case that stands a made-up book in place of the canon needs: the book, and the canon back.

The loader reads Marcia's maps and logs through caches, and the passages built from them are
cached in turn, so a case that points the loader at a directory of its own has to forget
everything the loader has held before it and again after it. One list, here, so that a cache
the loader gains is added in one place. Builders and constants only.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import shutil
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.services import internalization_room as room
from app.services.internalization_room import _default_prompts, canon, fail_safe, name_check
from app.services.internalization_room.canon import (
    accepted_readings,
    book_material,
    elements,
    kept,
    labels,
    names,
    parse_map,
    titles,
)

HER_CANON = Path(__file__).parent / "fixtures" / "her-canon-5b5c8d2"


def forget_the_canon() -> None:
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()
    book_material.preservation_rules.cache_clear()
    book_material.significant_absences.cache_clear()
    accepted_readings.accepted_readings_of.cache_clear()
    elements.elements_for.cache_clear()
    elements.scene_of.cache_clear()
    labels._known_pericopes.cache_clear()
    labels._catalogue.cache_clear()
    labels._legend.cache_clear()
    names._names_list.cache_clear()
    names._passage_labels.cache_clear()
    names._beings_by_scene.cache_clear()
    names.things_by_scene.cache_clear()
    names.verse_ranges.cache_clear()
    names._glosses.cache_clear()
    titles._portuguese.cache_clear()
    name_check._forms.cache_clear()


def _the_modules_of_the_room() -> list[Any]:
    submodules = [
        importlib.import_module(found.name)
        for found in pkgutil.walk_packages(room.__path__, f"{room.__name__}.")
    ]
    return [room, *submodules]


def the_caches_the_loader_holds() -> list[tuple[str, Any]]:
    held: dict[int, tuple[str, Any]] = {}
    for module in _the_modules_of_the_room():
        under_the_canon = module.__name__ == canon.__name__ or module.__name__.startswith(
            f"{canon.__name__}."
        )
        for name, value in sorted(vars(module).items()):
            if isinstance(value, kept.PerCanon) or (
                under_the_canon
                and not isinstance(value, type)
                and hasattr(value, "cache_clear")
                and hasattr(value, "cache_info")
            ):
                held.setdefault(id(value), (name, value))
    for listed in THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT:
        module_name, _, name = listed.rpartition(".")
        value = getattr(importlib.import_module(module_name), name)
        held.setdefault(id(value), (name, value))
    return list(held.values())


_THE_PROMPT_CACHES: tuple[tuple[str, Any], ...] = (
    ("_sections", fail_safe._sections),
    ("fail_safe_utterances", fail_safe.fail_safe_utterances),
    ("load_prompt", _default_prompts.load_prompt),
)


def the_caches_of_the_prompts() -> list[tuple[str, Any]]:
    return list(_THE_PROMPT_CACHES)


def the_names_the_forgotten_caches_are_reached_by() -> set[str]:
    forgotten = {
        id(cache) for _, cache in [*the_caches_the_loader_holds(), *the_caches_of_the_prompts()]
    }
    reached = {
        f"{module.__name__}.{name}"
        for module in _the_modules_of_the_room()
        for name, value in vars(module).items()
        if id(value) in forgotten
    }
    return reached | set(THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT)


def forget_the_prompts() -> None:
    for _, cache in _THE_PROMPT_CACHES:
        cache.cache_clear()


THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT: tuple[str, ...] = (
    "app.services.internalization_room.name_check._forms",
)

THE_CACHES_THAT_READ_NO_CANON: tuple[str, ...] = (
    "app.core.config.get_settings",
    "app.services.internalization_room.passage_lines._sections",
)


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


def a_fable_map(number: int = 1, *, sta_status: str = "complete", status: str = "complete") -> str:
    return textwrap.dedent(
        f"""\
        ---
        type: "pericope"
        pericope-num: "Q0{number}"
        pericope-title: "A fixture, not canon"
        bcv: "Fable 1:{number}-{number + 1}"
        genre-group: "NARRATIVE"
        genre: "HISTORICAL_NARRATIVE"
        status: "{status}"
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


def _a_fable_log(audit: list[dict]) -> str:
    body: dict = {"high_risk_register_audit": audit}
    return "# COMPILATION LOG\n\n" + json.dumps(body, indent=2) + "\n"


A_FABLE_LOG_WITH_A_LAYER = _a_fable_log([_A_RULE])
A_FABLE_LOG_WITHOUT_ONE = _a_fable_log([])
