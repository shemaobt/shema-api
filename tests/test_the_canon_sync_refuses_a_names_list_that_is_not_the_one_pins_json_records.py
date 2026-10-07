from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored

BEFORE_PIN = "pin_commit: cafef00dfacade00cafef00dfacade00cafef00d\n"
RECORDED_BY_THE_COMPILER = "ab" * 32


@pytest.fixture
def a_vendor_holding_ruth_and_a_compiler_whose_jonah_list_is_not_the_one_it_records(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.book("jonah")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("J01-Jonah-1-1-3")
    compiler.fingerprints["jonah"] = RECORDED_BY_THE_COMPILER
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    monkeypatch.setattr(canon, "SERVED_BOOKS", frozenset({"Ruth", "Jonah"}))
    (vendor / "meaning-map").mkdir(parents=True)
    (vendor / "meaning-map" / "P01-Ruth-1-1-5.md").write_bytes(b"the canon as it stood")
    (vendor / "VENDOR_PIN").write_text(BEFORE_PIN)
    return vendor


def test_a_names_list_that_is_not_the_one_pins_json_records_is_refused_and_named(
    a_vendor_holding_ruth_and_a_compiler_whose_jonah_list_is_not_the_one_it_records: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = a_vendor_holding_ruth_and_a_compiler_whose_jonah_list_is_not_the_one_it_records

    exit_code = canon.sync(pin=SHA)

    refusal = capsys.readouterr().err
    assert exit_code == 1
    assert "jonah" in refusal
    assert "ruth" not in refusal
    assert what_is_vendored(vendor) == {"meaning-map/P01-Ruth-1-1-5.md": b"the canon as it stood"}
    assert (vendor / "VENDOR_PIN").read_text() == BEFORE_PIN
