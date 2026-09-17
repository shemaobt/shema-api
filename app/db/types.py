"""Column types this schema needs and SQLAlchemy does not ship.

``UtcDateTime`` exists because ``DateTime(timezone=True)`` is a promise the drivers keep
differently: **Postgres reads back an aware value and SQLite reads back a naive one**, off
one schema and one writer. Everything above the column then has to know which engine it is
talking to, and under test it silently measures the wrong contract.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from app.utils.stored_time import as_utc


class UtcDateTime(TypeDecorator[datetime]):
    """A stored moment that reads back knowing which clock it is on, whatever the engine.

    **In production this is a no-op, and that was measured rather than assumed.** It acts only
    where ``tzinfo is None``, and a Postgres ``timestamptz`` never hands one back — so what it
    changes is SQLite behaving the way Postgres already does. What it buys is that the suite
    stops measuring a wire format production does not produce.

    Stamping UTC is a claim about what the value *means*, so it is only honest because two
    things were checked across the whole repository rather than supposed: every ``datetime``
    column is declared ``timezone=True`` — there is no column holding a bare local time — and
    everything the application writes is UTC, sixty ``datetime.now(UTC)`` and one ``utcnow``
    seam, with no ``ZoneInfo``, no ``pytz`` and no named zone in any migration. **If a column
    is ever added that stores something else, this type is a lie with the face of a fix**, and
    that is the sentence to re-read before widening it.

    It is a column type and not a rule each route remembers, which is the whole point:
    ``app/utils/stored_time.as_utc`` says the same thing one layer up and had to be called at
    every serialising site, so a route that forgot was open by default. This cannot be
    forgotten by a route that has not been written yet.

    **The rule itself is not written here**: this delegates to ``as_utc``, which is the one
    place naive-to-UTC lives and which ``test_stored_time`` refuses to see duplicated. The
    split is deliberate — the column type decides *where* the rule applies and the normaliser
    decides *what* it is. Reimplementing the one line reddened that test, correctly, and an
    allowlist entry would have been a dispensation for a real duplicate.

    ``as_utc`` also stays where it is already called. It guards a value crossing a boundary
    this type does not reach — one the transport hands us — and those call sites keep working
    unchanged.
    """

    impl = DateTime
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return as_utc(value) if value is not None else None

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        """Untouched on the way in: what is written is already the instant it claims to be."""
        return value
