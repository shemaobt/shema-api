from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.mark.parametrize("relation", ["diverged", "behind", None])
def test_a_commit_that_is_not_on_the_main_line_is_refused_and_nothing_is_written(
    relation: str | None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.relation = relation
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 1
    assert "is not on the compiler's main line" in capsys.readouterr().err
    assert what_is_vendored(vendor) == {}
    assert not (vendor / "VENDOR_PIN").exists()
