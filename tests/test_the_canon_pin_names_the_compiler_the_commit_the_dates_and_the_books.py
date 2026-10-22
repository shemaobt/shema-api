from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


def test_the_pin_record_names_the_compiler_the_commit_its_date_the_day_it_came_and_the_books(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("P05-Ruth-2-1-7")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)

    canon.sync(pin=SHA)

    today = datetime.now(UTC).date().isoformat()
    assert (vendor / "VENDOR_PIN").read_text() == (
        "source_repo:      MarciaSuzuki/tripod_compiler\n"
        "pin_commit:       5b5c8d2b3ae7632279c07017224f861ae369b0d7\n"
        "pin_ref:          main\n"
        "pin_committed:    2026-09-29\n"
        f"vendored_on:      {today}\n"
        "published_books:  Ruth (P01-P05) = 2 pericopes\n"
    )
