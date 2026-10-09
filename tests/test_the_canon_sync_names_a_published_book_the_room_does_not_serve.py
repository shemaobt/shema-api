from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_publishing_ruth_and_jonah_in_full() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.book("jonah")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("J01-Jonah-1-1-3")
    return compiler


def test_a_book_the_compiler_publishes_and_the_room_does_not_serve_is_left_out_and_named(
    a_compiler_publishing_ruth_and_jonah_in_full: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_publishing_ruth_and_jonah_in_full, tmp_path
    )

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 0
    assert [name for name in what_is_vendored(vendor) if "Jonah" in name or "jonah" in name] == []
    assert "skipped book Jonah: not served in this release" in capsys.readouterr().err
