from __future__ import annotations

import json
import shutil
from pathlib import Path

import scripts.fill_scene_titles as fill
from app.services.internalization_room.canon.titles import PORTUGUESE_TITLES


def _never(todo: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    raise AssertionError(f"a model was asked to translate {todo}")


def test_a_fill_over_a_list_where_every_scene_has_a_title_changes_nothing(
    tmp_path: Path,
) -> None:
    listed = tmp_path / "ui-labels.pt.json"
    shutil.copy(PORTUGUESE_TITLES, listed)
    before = listed.read_bytes()

    assert fill.fill(listed, translate=_never) == 0

    assert listed.read_bytes() == before, "a lista completa era reescrita pelo preenchimento"


def test_a_fill_adds_the_one_missing_title_and_leaves_every_title_she_has_as_written(
    tmp_path: Path,
) -> None:
    listed = tmp_path / "ui-labels.pt.json"
    hers = json.loads(PORTUGUESE_TITLES.read_text(encoding="utf-8"))
    without_it = json.loads(PORTUGUESE_TITLES.read_text(encoding="utf-8"))
    del without_it["scenes"]["P03"]["S2"]
    listed.write_text(json.dumps(without_it, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    asked: list[dict[str, dict[str, str]]] = []

    def translate(todo: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        asked.append(todo)
        return {"P03": {"S2": "O voto, traduzido de novo"}}

    assert fill.fill(listed, translate=translate) == 0

    filled = json.loads(listed.read_text(encoding="utf-8"))
    hers["scenes"]["P03"]["S2"] = "O voto, traduzido de novo"
    assert asked == [{"P03": {"S2": "Ruth's vow"}}], (
        "o modelo era chamado para cenas que já têm título"
    )
    assert filled == hers, "o preenchimento reescrevia títulos que já existiam"
