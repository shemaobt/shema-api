from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


def test_a_compiler_whose_main_line_is_still_the_pin_is_up_to_date_and_nothing_is_rewritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    canon.sync(pin=SHA)
    pin = vendor / "VENDOR_PIN"
    pin.write_text(pin.read_text().replace("vendored_on:      ", "vendored_on:      2026-09-30 #"))
    before = {path: path.read_bytes() for path in vendor.rglob("*") if path.is_file()}
    capsys.readouterr()
    compiler.requests.clear()

    exit_code = canon.sync()

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines()[-1] == "UP_TO_DATE"
    assert {path: path.read_bytes() for path in vendor.rglob("*") if path.is_file()} == before
    assert not [url for url in compiler.requests if "raw.githubusercontent.com" in url]
