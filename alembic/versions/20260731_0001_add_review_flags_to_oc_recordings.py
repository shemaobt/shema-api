"""add review_flags to oc_recordings and backfill existing rows

Revision ID: 20260731_0001
Revises: 20260601_0001
Create Date: 2026-07-31

The server default is what lets existing rows read back as an empty list instead of NULL
without a table rewrite: Postgres stores it in the catalog as a fast default, and SQLite
applies it in place. But an empty flag list reads as "reviewed and clean" when in fact
nothing has ever looked at the row, so the same revision then computes the real flags for
every row that predates the feature.

The column add and the backfill are one revision rather than two because the newest
revision on a branch is the one `.github/workflows/migrations.yml` round-trips through
`downgrade -1`. A backfill whose `downgrade()` is a no-op — which is the honest downgrade
here, since the pre-backfill value carried no information and nothing recorded which rows
were rewritten — would sit on top of the column add and stop `drop_column` from ever being
exercised.

Written against the lesson of 20260518_0002: a migration that silently does nothing when a
precondition is missing hides that fact until someone notices the data is wrong months
later. So the preconditions here return an empty report rather than raising, and the row
counts are logged, so an operator reading the upgrade output can tell a table with nothing
to do apart from a backfill that never ran.

The three flag conditions are spelled out below rather than imported from
`app.services.oral_collector.review_flags`. Importing that module pulls in the whole
service layer and builds a database engine at import time, which would let an unrelated
import error fail the deploy's migration step before a single statement runs. Duplicating
the conditions is also the correct shape for a migration: it is a permanent record of what
ran on this date, and it should keep computing what it computed then even if the runtime
rule later changes.

Two things are imported rather than copied, and neither reaches application state.
`app.utils.description_rule` imports nothing but `unicodedata` and `regex`, and ENG-354
reasoned its trim set and grapheme-cluster counting against the Dart client character by
character, so a second copy of that would silently drift. `app.core.enums` is a stdlib
`enum` module with no imports of its own, and taking the code spellings from it is what
keeps a backfilled row indistinguishable from one the runtime wrote.
"""

import logging
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from app.core.enums import ReviewFlagCode, ReviewFlagOrigin
from app.utils.description_rule import is_sufficient_description

revision: str = "20260731_0001"
down_revision: str | None = "20260601_0001"
branch_labels = None
depends_on = None


TABLE_NAME = "oc_recordings"
FLAGS_COLUMN = "review_flags"
UNCLASSIFIED_GENRE_ID = "unclassified"

logger = logging.getLogger("alembic.runtime.migration")


recordings = sa.table(
    TABLE_NAME,
    sa.column("id", sa.String),
    sa.column("genre_id", sa.String),
    sa.column("register_id", sa.String),
    sa.column("description", sa.Text),
    sa.column("storyteller_id", sa.String),
    sa.column(FLAGS_COLUMN, sa.JSON),
)


@dataclass
class BackfillReport:
    scanned: int = 0
    changed: int = 0


def _flag(code: ReviewFlagCode) -> dict[str, Any]:
    return {"code": str(code), "origin": str(ReviewFlagOrigin.SYSTEM)}


def _flags_for(
    *,
    genre_id: str | None,
    register_id: str | None,
    description: str | None,
    storyteller_id: str | None,
) -> list[dict[str, Any]]:
    """The flags these four field values implied on the day this revision was written.

    The order matches what the runtime rule produces, because the caller compares the
    result against the stored list to decide whether a row needs rewriting.
    """
    flags: list[dict[str, Any]] = []

    if genre_id == UNCLASSIFIED_GENRE_ID or not register_id:
        flags.append(_flag(ReviewFlagCode.MISSING_CLASSIFICATION))
    if not is_sufficient_description(description):
        flags.append(_flag(ReviewFlagCode.INSUFFICIENT_DESCRIPTION))
    if storyteller_id is None:
        flags.append(_flag(ReviewFlagCode.MISSING_STORYTELLER))

    return flags


def backfill_review_flags(connection: Connection, *, batch_size: int = 1000) -> BackfillReport:
    """Recompute ``review_flags`` for every recording, writing only the rows that differ."""
    report = BackfillReport()

    inspector = sa.inspect(connection)
    if not inspector.has_table(TABLE_NAME):
        return report
    if FLAGS_COLUMN not in {column["name"] for column in inspector.get_columns(TABLE_NAME)}:
        return report

    # Keyset pagination rather than OFFSET: the cost of skipping rows grows with depth, and
    # a server-side cursor left open while the same connection writes is not a pattern with
    # documented behaviour inside a migration's transaction.
    last_id: str | None = None
    while True:
        page = sa.select(
            recordings.c.id,
            recordings.c.genre_id,
            recordings.c.register_id,
            recordings.c.description,
            recordings.c.storyteller_id,
            recordings.c[FLAGS_COLUMN],
        ).order_by(recordings.c.id)
        if last_id is not None:
            page = page.where(recordings.c.id > last_id)

        rows = connection.execute(page.limit(batch_size)).mappings().all()
        if not rows:
            break

        for row in rows:
            report.scanned += 1
            flags = _flags_for(
                genre_id=row["genre_id"],
                register_id=row["register_id"],
                description=row["description"],
                storyteller_id=row["storyteller_id"],
            )
            if flags == row[FLAGS_COLUMN]:
                continue
            connection.execute(
                recordings.update()
                .where(recordings.c.id == row["id"])
                .values(**{FLAGS_COLUMN: flags})
            )
            report.changed += 1

        last_id = rows[-1]["id"]

    return report


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column(
            FLAGS_COLUMN,
            sa.JSON(none_as_null=True),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    report = backfill_review_flags(op.get_bind())
    logger.info(
        "review_flags backfill: scanned %d recording(s), updated %d",
        report.scanned,
        report.changed,
    )


def downgrade() -> None:
    op.drop_column(TABLE_NAME, FLAGS_COLUMN)
