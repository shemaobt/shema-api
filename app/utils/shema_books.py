"""The 66 books the progress table is checked against — FE-44's ``BIBLE_BOOKS``, verbatim.

**This repository already has a book table and it is the wrong one.** ``bible_books``
(``app/db/models/meaning_map.py``) is the Meaning Map generator's: its primary key is a minted
uuid, its rows are seeded per deployment, its ``name`` is a single language and it carries an
``is_enabled`` flag that a different product turns off. A progress row names a book by
``"mat"`` — FE-44 §5.2's own key — so validating against that table would mean a join on a
name, in a product whose rows another product may disable, to answer a question that has one
correct answer everywhere and never changes. ``docs/shema.md`` §4 audits nine platform
capabilities and does not audit this one; the verdict this file records is the same shape as
§4.9's for geocoding — **available, and not what this needs**.

**So the table is here, in Python, and it is checked against the frontend's own file rather
than trusted.** FE-44 §5.2 states the property that makes that check possible: *"the chapter
counts sum to 1,189 and the New Testament's to 260, which are exactly the ``totalUnits``
values the export carries for Bíblia Completa and for NT"*, and it asks in the next sentence
that *a server that keeps its own book list must match it book for book*. So the two
sums are asserted here at import time, where a mistyped chapter count fails the boot check
rather than a progress save six weeks later — the one place a transcription error in 66 rows
is cheap to catch. ``tests/test_shema/test_books.py`` is the book-for-book half, read off
``src/constants/bible.ts`` the way ``docs/resource_requests.md`` §9's vocabulary mirror reads
a TypeScript source.

**In ``app/utils/`` and not in ``app/services/shema/``**, for ``app/utils/shema_derivations.py``'s
stated reason: the validation is a pure function of a payload, it is wanted by a request model
*and* by the write service, and ``app/models/`` may not import ``app/services/``. ``app/utils/``
is flat, so the file carries the module's prefix rather than forming a package its siblings do
not have (``docs/shema.md`` §3.1).

**What this file does not decide.** Whether a project's ``bookProgress`` may name a book
outside its ``objective`` — a *Novo Testamento* project with a row for Genesis — is not a
structural question and is not checked anywhere here. The objective drives which tables the
record *shows* (FE-44 §5.1) and a coordinator who typed a row has a reason; refusing it would
be this file inventing a rule the product does not have.
"""

from __future__ import annotations

from typing import Final, NamedTuple


class ShemaBibleBook(NamedTuple):
    """One book, as ``src/constants/bible.ts`` carries it.

    ``name`` is the Portuguese the record shows and ``en`` the English beside it; both travel
    because the console renders one and the Pulse the other, and a server that kept only one
    would be the reason a later issue adds a second list.
    """

    id: str
    name: str
    en: str
    chapters: int
    ot: bool


#: The 66 books in canonical order — 39 Old Testament, 27 New. **Generated from FE-44's own
#: source**, not transcribed: the ids are the keys a ``BookProgressItem`` carries and the
#: chapter counts are what a progress row is measured against.
BIBLE_BOOKS: Final[tuple[ShemaBibleBook, ...]] = (
    ShemaBibleBook("gen", "Gênesis", "Genesis", 50, True),
    ShemaBibleBook("exo", "Êxodo", "Exodus", 40, True),
    ShemaBibleBook("lev", "Levítico", "Leviticus", 27, True),
    ShemaBibleBook("num", "Números", "Numbers", 36, True),
    ShemaBibleBook("deu", "Deuteronômio", "Deuteronomy", 34, True),
    ShemaBibleBook("jos", "Josué", "Joshua", 24, True),
    ShemaBibleBook("jdg", "Juízes", "Judges", 21, True),
    ShemaBibleBook("rut", "Rute", "Ruth", 4, True),
    ShemaBibleBook("1sa", "1 Samuel", "1 Samuel", 31, True),
    ShemaBibleBook("2sa", "2 Samuel", "2 Samuel", 24, True),
    ShemaBibleBook("1ki", "1 Reis", "1 Kings", 22, True),
    ShemaBibleBook("2ki", "2 Reis", "2 Kings", 25, True),
    ShemaBibleBook("1ch", "1 Crônicas", "1 Chronicles", 29, True),
    ShemaBibleBook("2ch", "2 Crônicas", "2 Chronicles", 36, True),
    ShemaBibleBook("ezr", "Esdras", "Ezra", 10, True),
    ShemaBibleBook("neh", "Neemias", "Nehemiah", 13, True),
    ShemaBibleBook("est", "Ester", "Esther", 10, True),
    ShemaBibleBook("job", "Jó", "Job", 42, True),
    ShemaBibleBook("psa", "Salmos", "Psalms", 150, True),
    ShemaBibleBook("pro", "Provérbios", "Proverbs", 31, True),
    ShemaBibleBook("ecc", "Eclesiastes", "Ecclesiastes", 12, True),
    ShemaBibleBook("sng", "Cantares", "Song of Solomon", 8, True),
    ShemaBibleBook("isa", "Isaías", "Isaiah", 66, True),
    ShemaBibleBook("jer", "Jeremias", "Jeremiah", 52, True),
    ShemaBibleBook("lam", "Lamentações", "Lamentations", 5, True),
    ShemaBibleBook("ezk", "Ezequiel", "Ezekiel", 48, True),
    ShemaBibleBook("dan", "Daniel", "Daniel", 12, True),
    ShemaBibleBook("hos", "Oseias", "Hosea", 14, True),
    ShemaBibleBook("jol", "Joel", "Joel", 3, True),
    ShemaBibleBook("amo", "Amós", "Amos", 9, True),
    ShemaBibleBook("oba", "Obadias", "Obadiah", 1, True),
    ShemaBibleBook("jon", "Jonas", "Jonah", 4, True),
    ShemaBibleBook("mic", "Miqueias", "Micah", 7, True),
    ShemaBibleBook("nam", "Naum", "Nahum", 3, True),
    ShemaBibleBook("hab", "Habacuque", "Habakkuk", 3, True),
    ShemaBibleBook("zep", "Sofonias", "Zephaniah", 3, True),
    ShemaBibleBook("hag", "Ageu", "Haggai", 2, True),
    ShemaBibleBook("zec", "Zacarias", "Zechariah", 14, True),
    ShemaBibleBook("mal", "Malaquias", "Malachi", 4, True),
    ShemaBibleBook("mat", "Mateus", "Matthew", 28, False),
    ShemaBibleBook("mrk", "Marcos", "Mark", 16, False),
    ShemaBibleBook("luk", "Lucas", "Luke", 24, False),
    ShemaBibleBook("jhn", "João", "John", 21, False),
    ShemaBibleBook("act", "Atos", "Acts", 28, False),
    ShemaBibleBook("rom", "Romanos", "Romans", 16, False),
    ShemaBibleBook("1co", "1 Coríntios", "1 Corinthians", 16, False),
    ShemaBibleBook("2co", "2 Coríntios", "2 Corinthians", 13, False),
    ShemaBibleBook("gal", "Gálatas", "Galatians", 6, False),
    ShemaBibleBook("eph", "Efésios", "Ephesians", 6, False),
    ShemaBibleBook("php", "Filipenses", "Philippians", 4, False),
    ShemaBibleBook("col", "Colossenses", "Colossians", 4, False),
    ShemaBibleBook("1th", "1 Tessalonicenses", "1 Thessalonians", 5, False),
    ShemaBibleBook("2th", "2 Tessalonicenses", "2 Thessalonians", 3, False),
    ShemaBibleBook("1ti", "1 Timóteo", "1 Timothy", 6, False),
    ShemaBibleBook("2ti", "2 Timóteo", "2 Timothy", 4, False),
    ShemaBibleBook("tit", "Tito", "Titus", 3, False),
    ShemaBibleBook("phm", "Filemom", "Philemon", 1, False),
    ShemaBibleBook("heb", "Hebreus", "Hebrews", 13, False),
    ShemaBibleBook("jas", "Tiago", "James", 5, False),
    ShemaBibleBook("1pe", "1 Pedro", "1 Peter", 5, False),
    ShemaBibleBook("2pe", "2 Pedro", "2 Peter", 3, False),
    ShemaBibleBook("1jn", "1 João", "1 John", 5, False),
    ShemaBibleBook("2jn", "2 João", "2 John", 1, False),
    ShemaBibleBook("3jn", "3 João", "3 John", 1, False),
    ShemaBibleBook("jud", "Judas", "Jude", 1, False),
    ShemaBibleBook("rev", "Apocalipse", "Revelation", 22, False),
)

#: ``id`` → book, which is the lookup every check below makes.
BOOKS_BY_ID: Final[dict[str, ShemaBibleBook]] = {book.id: book for book in BIBLE_BOOKS}

#: What a complete Bible holds, and what a New Testament holds. They are **assertions about
#: this file**, not configuration: FE-44 §5.2 pins both against the export's own
#: ``totalUnits`` values, so a chapter count mistyped here stops the boot check.
BIBLE_CHAPTER_TOTAL: Final = 1189
NEW_TESTAMENT_CHAPTER_TOTAL: Final = 260

assert len(BIBLE_BOOKS) == 66, "the canon has 66 books"
assert sum(book.chapters for book in BIBLE_BOOKS) == BIBLE_CHAPTER_TOTAL
assert sum(book.chapters for book in BIBLE_BOOKS if not book.ot) == NEW_TESTAMENT_CHAPTER_TOTAL


def chapters_in(book_id: str) -> int | None:
    """How many chapters ``book_id`` really has, or ``None`` when it is not a book.

    The two answers are deliberately one call: *is this a book* and *how long is it* are the
    same lookup, and asking them separately is how a caller ends up checking the first and
    forgetting the second.
    """
    book = BOOKS_BY_ID.get(book_id)
    return None if book is None else book.chapters
