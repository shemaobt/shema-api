"""Reading back a moment the database wrote.

``DateTime(timezone=True)`` hands back a **naive** datetime on SQLite and an **aware** one on
Postgres. Comparing one against the other raises, so every path that measures a stored moment
against ``datetime.now(UTC)`` has to normalise first — and six of them wrote their own before
this module existed, one per product.

**A naive value reads as UTC because UTC is the only thing this codebase ever writes.** That
sentence is the whole of it, and it is worth having in one place rather than six, because the
other reading is the dangerous one: taking a naive value as *local* does not raise, does not
fail a test and does not look broken. It draws a time wrong by the machine's offset. Measured
on the Desk on 2026-08-20 — the server answered ``20:00:56`` with no offset and the panel drew
``05:00 PM`` on a UTC-3 machine, where local would have said ``08:00 PM``.

**Stored, and never off the wire.** The distinction is not decoration: a value a client sent
may legitimately carry any offset, and the right thing to do with an aware one there is to
*convert* it. Here an aware value is passed through untouched, because it is already the
instant the column holds. ``app/api/sound_necklace/audit.py`` owns the other conversion for
exactly this reason and is not a seventh caller of this one.
"""

from datetime import UTC, datetime


def as_utc(when: datetime) -> datetime:
    """Read a stored moment as the instant it is.

    Named for what two of the six already called it. Non-optional on purpose: only one column
    among them is nullable, and putting the null-handling here would spread it to five callers
    that cannot receive one — so ``lock_bcd`` guards at its own call, where its own nullable
    column is.
    """
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when
