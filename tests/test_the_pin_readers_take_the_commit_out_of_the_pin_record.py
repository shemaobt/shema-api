from __future__ import annotations

from pathlib import Path

import pytest

import scripts.golden_runner as golden_runner
from app.services.internalization_room.canon import book_material

RECORD = (
    "source_repo:      MarciaSuzuki/tripod_compiler\n"
    "pin_commit:       cafef00dfacade00cafef00dfacade00cafef00d\n"
    "pin_ref:          main\n"
    "pin_committed:    2026-09-29\n"
    "vendored_on:      2026-09-30\n"
    "published_books:  Ruth (P01-P14) = 14 pericopes\n"
)


@pytest.fixture
def a_vendor_pinned_by_a_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "VENDOR_PIN").write_text(RECORD)
    monkeypatch.setattr(book_material, "VENDOR", tmp_path)


def test_the_release_stamps_the_commit_and_not_the_whole_record(
    a_vendor_pinned_by_a_record: None,
) -> None:
    assert book_material.vendor_pin() == "cafef00dfacade00cafef00dfacade00cafef00d"


def test_the_golden_report_names_the_canon_by_its_commit_and_not_by_the_records_first_line(
    a_vendor_pinned_by_a_record: None,
) -> None:
    assert golden_runner._pins().endswith("cânon `cafef00`")
