from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


def _no_network(url: str) -> bytes:
    raise AssertionError(f"the drift check reached for the network: {url}")


@pytest.fixture
def a_vendor_synced_and_then_cut_off_from_the_compiler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    canon.sync(pin=SHA)
    monkeypatch.setattr(canon, "_get", _no_network)
    return vendor


def test_a_copy_that_matches_its_record_passes_with_no_network(
    a_vendor_synced_and_then_cut_off_from_the_compiler: Path,
) -> None:
    assert canon.check() == 0


def test_one_character_edited_in_one_map_fails_offline_and_the_message_ends_in_her_words(
    a_vendor_synced_and_then_cut_off_from_the_compiler: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    edited = a_vendor_synced_and_then_cut_off_from_the_compiler / "meaning-map/P01-Ruth-1-1-5.md"
    edited.write_bytes(b"map P01-Ruth-1-1-6")

    exit_code = canon.check()

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "changed: meaning-map/P01-Ruth-1-1-5.md" in err
    assert "scripts/sync_internalization_canon.py --sync" in err
    assert err.endswith("never edit vendored files (or the manifest) by hand.\n")
