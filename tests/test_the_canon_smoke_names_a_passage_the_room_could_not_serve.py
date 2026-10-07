from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.smoke_internalization_canon as smoke
from app.models.internalization_room import LabelledElement
from app.services.internalization_room.canon.parse_map import MeaningMap


def _p01_labels_with(label: str, monkeypatch: pytest.MonkeyPatch) -> None:
    real = smoke.labelled_elements

    def labelled(pericope_num: str, *, book: str) -> list[LabelledElement]:
        labels = real(pericope_num, book=book)
        if pericope_num == "P01":
            labels[0] = labels[0].model_copy(update={"label_en": label})
        return labels

    monkeypatch.setattr(smoke, "labelled_elements", labelled)


def test_the_canon_at_her_pin_passes_the_smoke() -> None:
    assert smoke.problems() == []


@pytest.mark.parametrize("label", ["[[x]]", "", "   ", "B2", "PL1", "O13"])
def test_a_coverage_label_that_leaks_a_link_is_empty_or_is_a_bare_code_fails_and_is_named(
    label: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _p01_labels_with(label, monkeypatch)

    found = smoke.problems()

    assert len(found) == 1
    assert found[0].startswith("P01: ")
    assert repr(label) in found[0]


def test_a_scene_with_no_title_fails_and_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    real = smoke.load_book

    def load_book(book: str) -> tuple[MeaningMap, ...]:
        maps = list(real(book))
        first = maps[0]
        scenes = [first.scenes[0].model_copy(update={"title": " "}), *first.scenes[1:]]
        maps[0] = first.model_copy(update={"scenes": scenes})
        return tuple(maps)

    monkeypatch.setattr(smoke, "load_book", load_book)

    assert smoke.problems() == ["P01: scene 1 has no title"]


@pytest.mark.parametrize(
    ("update", "named"),
    [
        ({"arc_prose": " "}, "P01: the digest has no arc"),
        ({"reference": ""}, "P01: the digest has no reference line"),
    ],
)
def test_a_digest_without_its_reference_line_or_its_arc_fails_and_is_named(
    update: dict[str, str], named: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = smoke.load_book

    def load_book(book: str) -> tuple[MeaningMap, ...]:
        maps = list(real(book))
        maps[0] = maps[0].model_copy(update=update)
        return tuple(maps)

    monkeypatch.setattr(smoke, "load_book", load_book)

    assert smoke.problems() == [named]


def test_a_menu_that_offers_fewer_passages_than_the_record_holds_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    record = json.loads(smoke.MANIFEST.read_text())
    record["passages"].append("P15")
    (tmp_path / "VENDOR_MANIFEST.json").write_text(json.dumps(record))
    monkeypatch.setattr(smoke, "MANIFEST", tmp_path / "VENDOR_MANIFEST.json")

    assert smoke.problems() == [
        "the menu offers 14 passages in en but the record holds 15",
        "the menu offers 14 passages in pt but the record holds 15",
    ]
