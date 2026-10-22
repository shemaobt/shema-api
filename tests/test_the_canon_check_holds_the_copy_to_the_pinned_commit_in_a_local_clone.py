from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import Compiler, a_clone_of, point_the_sync_at


@pytest.fixture
def a_vendor_synced_beside_a_clone_of_its_compiler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    clone = tmp_path / "tripod_compiler"
    sha = a_clone_of(compiler, clone)
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    canon.sync(pin=sha)
    monkeypatch.setenv("TRIPOD_COMPILER_REPO", str(clone))
    return vendor


def _rerecord(vendor: Path, path: str, data: bytes | None) -> None:
    manifest = json.loads((vendor / "VENDOR_MANIFEST.json").read_text())
    files = [entry for entry in manifest["files"] if entry["path"] != path]
    if data is not None:
        (vendor / path).write_bytes(data)
        files.append({"path": path, "sha256": hashlib.sha256(data).hexdigest()})
    else:
        (vendor / path).unlink()
    manifest["files"] = files
    (vendor / "VENDOR_MANIFEST.json").write_text(json.dumps(manifest))


def test_a_copy_that_is_the_pinned_commit_passes_against_the_clone(
    a_vendor_synced_beside_a_clone_of_its_compiler: Path,
) -> None:
    assert canon.check() == 0


def test_a_map_edited_with_its_record_edited_to_match_is_caught_by_the_clone(
    a_vendor_synced_beside_a_clone_of_its_compiler: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _rerecord(
        a_vendor_synced_beside_a_clone_of_its_compiler,
        "meaning-map/P01-Ruth-1-1-5.md",
        b"a map she never published",
    )

    assert canon.check() == 1
    assert "changed: meaning-map/P01-Ruth-1-1-5.md" in capsys.readouterr().err


def test_a_file_the_pin_holds_and_the_copy_and_its_record_both_lost_is_caught_by_the_clone(
    a_vendor_synced_beside_a_clone_of_its_compiler: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _rerecord(
        a_vendor_synced_beside_a_clone_of_its_compiler,
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md",
        None,
    )

    assert canon.check() == 1
    assert "missing: compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md" in capsys.readouterr().err


def test_a_passage_the_pin_never_held_added_with_its_record_is_caught_by_the_clone(
    a_vendor_synced_beside_a_clone_of_its_compiler: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _rerecord(
        a_vendor_synced_beside_a_clone_of_its_compiler,
        "meaning-map/P02-Ruth-1-6-14.md",
        b"a map from a working branch",
    )

    assert canon.check() == 1
    assert "extra: meaning-map/P02-Ruth-1-6-14.md" in capsys.readouterr().err
