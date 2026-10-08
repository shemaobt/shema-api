from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from app.core.canon_pin import pinned_commit
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored

NEXT = "c" * 40
FIRST_LABELS = '{"P01": "labelled for the first canon"}'


@pytest.fixture
def a_vendor_synced_once_beside_its_labels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    (tmp_path / "element-labels").mkdir()
    (tmp_path / "element-labels" / "ruth.json").write_text(FIRST_LABELS)
    assert canon.sync(pin=SHA) == 0
    return compiler


def test_a_re_pin_keeps_the_canon_it_replaces_under_its_pin_beside_the_labels_it_was_read_with(
    a_vendor_synced_once_beside_its_labels: Compiler, tmp_path: Path
) -> None:
    compiler = a_vendor_synced_once_beside_its_labels
    compiler.sha = NEXT
    compiler.files["fixtures/meaning-map/P01-Ruth-1-1-5.md"] = b"map P01 revised"

    assert canon.sync(pin=NEXT) == 0

    kept = tmp_path / "kept" / SHA
    assert what_is_vendored(kept / "vendor") == {
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md": b"log P01-Ruth-1-1-5",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md": b"coordinates P01-Ruth-1-1-5",
        "meaning-map/P01-Ruth-1-1-5.md": b"map P01-Ruth-1-1-5",
        "registry/ruth.aliases.json": b"aliases ruth",
    }, "o re-pin apagou o canon que as sessões abertas ainda leem"
    assert pinned_commit((kept / "vendor" / "VENDOR_PIN").read_text()) == SHA
    assert (kept / "element-labels" / "ruth.json").read_text() == FIRST_LABELS
    assert what_is_vendored(tmp_path / "vendor")["meaning-map/P01-Ruth-1-1-5.md"] == (
        b"map P01 revised"
    )
