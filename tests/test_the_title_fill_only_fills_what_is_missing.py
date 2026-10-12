from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

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


def test_a_fill_that_needs_a_title_without_a_key_fails_naming_the_key_and_the_scene(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    listed = tmp_path / "ui-labels.pt.json"
    without_it = json.loads(PORTUGUESE_TITLES.read_text(encoding="utf-8"))
    del without_it["scenes"]["P03"]["S2"]
    listed.write_text(json.dumps(without_it, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    before = listed.read_bytes()

    with pytest.raises(SystemExit) as refused:
        fill.fill(listed)

    assert refused.value.code == (
        "ANTHROPIC_API_KEY is not set, so no Portuguese title can be filled for P03 S2"
    ), "sem a chave o preenchimento caía num erro do cliente que não dizia o que faltava"
    assert listed.read_bytes() == before


def _without_titles(tmp_path: Path, *scene_ids: str) -> Path:
    listed = tmp_path / "ui-labels.pt.json"
    without_them = json.loads(PORTUGUESE_TITLES.read_text(encoding="utf-8"))
    for scene_id in scene_ids:
        del without_them["scenes"]["P03"][scene_id]
    listed.write_text(
        json.dumps(without_them, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return listed


def test_a_reply_that_drops_a_scene_is_refused_by_name_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    listed = _without_titles(tmp_path, "S2", "S3")
    before = listed.read_bytes()

    with pytest.raises(SystemExit) as refused:
        fill.fill(listed, translate=lambda todo: {"P03": {"S3": "O silêncio de Noemi"}})

    assert refused.value.code == "missing scene in translation: P03/S2", (
        "a resposta sem uma cena caía num KeyError que não dizia qual"
    )
    assert listed.read_bytes() == before, "a cena que voltou era escrita mesmo com outra faltando"


def test_a_reply_that_drops_a_whole_pericope_is_refused_by_name_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    listed = _without_titles(tmp_path, "S2")
    without_it = json.loads(listed.read_text(encoding="utf-8"))
    del without_it["scenes"]["P04"]
    listed.write_text(json.dumps(without_it, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    before = listed.read_bytes()

    with pytest.raises(SystemExit) as refused:
        fill.fill(listed, translate=lambda todo: {"P03": {"S2": "O voto de Rute"}})

    assert refused.value.code == "missing pericope in translation: P04", (
        "a resposta sem uma perícope caía num KeyError que não dizia qual"
    )
    assert listed.read_bytes() == before, "a perícope que voltou era escrita com outra faltando"


def test_the_scheduled_fill_starts_without_a_key_when_every_served_scene_has_a_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "")

    def no_client(**_: object) -> None:
        raise AssertionError("a client was built with nothing to translate")

    monkeypatch.setattr(fill.anthropic, "Anthropic", no_client)
    before = PORTUGUESE_TITLES.read_bytes()

    assert fill.fill() == 0, "o passo agendado caía sem a chave mesmo sem nada a preencher"
    assert PORTUGUESE_TITLES.read_bytes() == before
