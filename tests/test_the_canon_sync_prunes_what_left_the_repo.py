"""`--sync` never deleted. The docstring said it overwrote the vendored directory wholesale,
but the code only `write_bytes` per name from the upstream listing: a file that left her repo
survived in ours silently, and `--check` did not see it either, since it iterated the upstream
listing only (ENG-926).

Never runs against the real vendor: the compiler is `tests/canon_sync_harness.Compiler`, answered
through `_get`, and `VENDOR`/`PIN_FILE` are redirected into `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


@pytest.fixture
def a_compiler_holding_one_whole_passage_of_ruth() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    return compiler


@pytest.fixture
def vendor_with_a_file_upstream_no_longer_has(
    a_compiler_holding_one_whole_passage_of_ruth: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_holding_one_whole_passage_of_ruth, tmp_path
    )
    (vendor / "meaning-map").mkdir(parents=True)
    (vendor / "meaning-map" / "P15-Ruth-Gone.md").write_bytes(b"stale")
    (vendor / "meaning-map" / "P01-Ruth-1-1-5.md").write_bytes(b"kept-locally-stale-bytes")
    return vendor


def test_sync_deletes_a_vendored_file_the_upstream_listing_no_longer_has(
    vendor_with_a_file_upstream_no_longer_has: Path,
) -> None:
    canon.sync(pin=SHA)

    meaning_map = vendor_with_a_file_upstream_no_longer_has / "meaning-map"
    remaining = sorted(p.name for p in meaning_map.iterdir())
    assert remaining == ["P01-Ruth-1-1-5.md"]


@pytest.fixture
def pinned_vendor_with_a_file_upstream_no_longer_has(
    a_compiler_holding_one_whole_passage_of_ruth: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_holding_one_whole_passage_of_ruth, tmp_path
    )
    canon.sync(pin=SHA)
    (vendor / "meaning-map" / "P15-Ruth-Gone.md").write_bytes(b"stale")
    return vendor


def test_check_reports_a_vendored_file_the_upstream_listing_no_longer_has(
    pinned_vendor_with_a_file_upstream_no_longer_has: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = canon.check()

    assert exit_code == 1
    assert "extra: meaning-map/P15-Ruth-Gone.md" in capsys.readouterr().err
