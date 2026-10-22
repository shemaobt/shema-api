from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


@pytest.fixture
def a_vendor_synced_with_no_clone_of_the_compiler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    canon.sync(pin=SHA)
    return vendor


def test_on_a_build_machine_a_missing_compiler_copy_fails_the_guard(
    a_vendor_synced_with_no_clone_of_the_compiler: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CI", "true")

    exit_code = canon.check()

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "TRIPOD_COMPILER_REPO" in err
    assert err.endswith("never edit vendored files (or the manifest) by hand.\n")


def test_on_a_developers_machine_a_missing_compiler_copy_leaves_the_integrity_check(
    a_vendor_synced_with_no_clone_of_the_compiler: Path,
) -> None:
    assert canon.check() == 0
