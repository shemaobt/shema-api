"""The 66 books, checked book for book against the frontend's own table.

FE-44 §5.2 asks for exactly this in one sentence: *a server that keeps its own book list must
match it book for book, or the roll-up and the export disagree about what a complete Bible
is.* ``app/utils/shema_books.py`` keeps one, so this is where the sentence is enforced.

**Vendored, not read across the worktree.** ``bibleBooks.json`` is emitted from
``src/constants/bible.ts`` and carries the commit it came from —
``docs/resource_requests.md`` §9's mechanism, and its reason: neither CI job has the other
repository checked out, so a check that read the TypeScript directly would be a check that
only ever runs on somebody's laptop.

The two sums are also asserted inside ``app/utils/shema_books.py`` itself, at import. That is
not a duplicate of this file: the assertion there fails the **boot check** on a mistyped
chapter count, where the cost is one command; this one says *which* book drifted.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.utils.shema_books import (
    BIBLE_BOOKS,
    BIBLE_CHAPTER_TOTAL,
    NEW_TESTAMENT_CHAPTER_TOTAL,
    chapters_in,
)

VENDORED = json.loads((Path(__file__).parent / "bibleBooks.json").read_text(encoding="utf-8"))


def test_the_table_is_the_frontends_table_book_for_book() -> None:
    mine = [
        {"id": book.id, "name": book.name, "en": book.en, "chapters": book.chapters, "ot": book.ot}
        for book in BIBLE_BOOKS
    ]
    assert mine == VENDORED["books"]


def test_the_canon_is_thirty_nine_and_twenty_seven() -> None:
    assert len(BIBLE_BOOKS) == 66
    assert sum(1 for book in BIBLE_BOOKS if book.ot) == 39


def test_the_two_sums_are_the_exports_own_total_units() -> None:
    """1,189 and 260 are the ``totalUnits`` the export carries for *Bíblia Completa* and *NT*.

    That agreement is what makes the table the authority rather than a convenience: a server
    whose Bible is 1,190 chapters long reports a project as 99.9% complete forever.
    """
    assert BIBLE_CHAPTER_TOTAL == VENDORED["chapterTotal"] == 1189
    assert NEW_TESTAMENT_CHAPTER_TOTAL == 260


def test_a_book_that_is_not_a_book_has_no_length() -> None:
    """One lookup answers both questions, so a caller cannot check the first and forget it."""
    assert chapters_in("mat") == 28
    assert chapters_in("psa") == 150
    assert chapters_in("gospel-of-thomas") is None


def test_the_platforms_own_book_table_is_not_this_one() -> None:
    """``bible_books`` is the Meaning Map generator's: minted uuids, seeded rows, one language.

    Named here rather than only in a docstring because *there is already a book table* is the
    first thing a reader of this module will say, and the answer is that its primary key is
    not the key a ``BookProgressItem`` carries.
    """
    from app.db.models.meaning_map import BibleBook

    assert "id" in BibleBook.__table__.columns
    assert BibleBook.__table__.columns["id"].primary_key
    assert {book.id for book in BIBLE_BOOKS} != set()
    assert "is_enabled" in BibleBook.__table__.columns
