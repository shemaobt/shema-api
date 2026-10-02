"""every Shemá project id becomes an opaque UUID — the export's slugs named the place

Revision ID: 20261001_shema552
Revises: 20260930_rr13
Create Date: 2026-10-01

OBT-552, found by the INT-12 privacy pass (OBT-417). The 127 imported records kept the Notion
export's slug as their primary key, ``<language>-<place>``, and the id leaves the server
unredacted on every shape: for a project in a sensitive country the address handed back the place
the redaction had just withheld. OBT-551 already makes every new record take a minted UUID; this
gives the existing ones one too, so no project id names a place — including a project flagged
sensitive later, which is why every slug moves and not only today's sensitive ones.

A primary key with a dozen ``ON UPDATE NO ACTION`` foreign keys behind it cannot be updated in
place, so each record is **copied, its children repointed, and the original deleted**:

1. the row is copied under the new id, with the columns a unique index guards left empty — the
   original still holds those values, and the index would refuse a second;
2. every column that references ``shema_projects.id`` is repointed — found by inspecting the
   database rather than listed here, so a table added later cannot be missed;
3. the original is deleted and the guarded values are put back on the copy;
4. the notification preferences' ``custom_project_ids`` (JSON, no foreign key) are mapped too.

Two of the children are append-only by trigger — ``shema_progress_history`` and
``shema_record_edits`` (``append_only_ddl``) — and both hold a ``RESTRICT`` foreign key to the
project, so the original cannot be deleted while they point at it. Their trigger is lifted for the
one statement that repoints them and put back straight after: what moves is the reference, never
the history. ``shema_exports.project_ids`` and the recorded ETEN reports' ``content`` are **not**
rewritten: they record what left the server, and what left carried the slugs —
``shema_project_rekeys`` maps them to today's ids. Neither is served back.

Written by hand and importing nothing from ``app.``, like the other revisions.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op

revision: str = "20261001_shema552"
down_revision: str | None = "20260930_rr13"
branch_labels = None
depends_on = None

PROJECTS = "shema_projects"
REKEYS = "shema_project_rekeys"
PREFS = "shema_notification_prefs"
PREFS_IDS = "custom_project_ids"


def _is_minted(project_id: str) -> bool:
    try:
        return str(uuid.UUID(project_id)) == project_id
    except ValueError:
        return False


def _referencing(bind: sa.engine.Connection) -> list[tuple[str, str]]:
    inspector = sa.inspect(bind)
    found = []
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] == PROJECTS and fk["referred_columns"] == ["id"]:
                found.append((table, fk["constrained_columns"][0]))
    return found


def _guarded(bind: sa.engine.Connection) -> list[str]:
    columns: list[str] = []
    for index in sa.inspect(bind).get_indexes(PROJECTS):
        if index.get("unique"):
            columns.extend(c for c in index["column_names"] if c and c != "id")
    return sorted(set(columns))


def _without_append_only(
    bind: sa.engine.Connection, table: str, statement: sa.TextClause, params: dict
) -> None:
    """Run one UPDATE on ``table`` with its append-only trigger lifted, then put it back."""
    if bind.dialect.name == "postgresql":
        trigger = f"{table}_append_only"
        exists = bind.execute(
            sa.text("SELECT 1 FROM pg_trigger WHERE tgname = :name AND NOT tgisinternal"),
            {"name": trigger},
        ).first()
        if exists:
            bind.execute(sa.text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}"))
        bind.execute(statement, params)
        if exists:
            bind.execute(sa.text(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}"))
        return
    trigger = f"{table}_no_update"
    ddl = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = :name"),
        {"name": trigger},
    ).scalar_one_or_none()
    if ddl:
        bind.execute(sa.text(f"DROP TRIGGER {trigger}"))
    bind.execute(statement, params)
    if ddl:
        bind.execute(sa.text(ddl))


def _move(
    bind: sa.engine.Connection,
    pairs: Iterable[tuple[str, str]],
) -> None:
    quote = bind.dialect.identifier_preparer.quote
    columns = [c["name"] for c in sa.inspect(bind).get_columns(PROJECTS) if c["name"] != "id"]
    guarded = _guarded(bind)
    references = _referencing(bind)
    target = ", ".join(quote(c) for c in columns)
    source = ", ".join("NULL" if c in guarded else quote(c) for c in columns)

    for old, new in pairs:
        keep = {"old": old, "new": new}
        saved = (
            bind.execute(
                sa.text(
                    f"SELECT {', '.join(quote(c) for c in guarded) or '1'} "
                    f"FROM {PROJECTS} WHERE id = :old"
                ),
                keep,
            )
            .mappings()
            .one()
        )
        bind.execute(
            sa.text(
                f"INSERT INTO {PROJECTS} (id, {target}) "
                f"SELECT :new, {source} FROM {PROJECTS} WHERE id = :old"
            ),
            keep,
        )
        for table, column in references:
            _without_append_only(
                bind,
                table,
                sa.text(
                    f"UPDATE {quote(table)} SET {quote(column)} = :new WHERE {quote(column)} = :old"
                ),
                keep,
            )
        bind.execute(sa.text(f"DELETE FROM {PROJECTS} WHERE id = :old"), keep)
        if guarded:
            bind.execute(
                sa.text(
                    f"UPDATE {PROJECTS} SET "
                    + ", ".join(f"{quote(c)} = :{c}" for c in guarded)
                    + " WHERE id = :new"
                ),
                {**{c: saved[c] for c in guarded}, "new": new},
            )


def _map_preferences(bind: sa.engine.Connection, mapping: dict[str, str]) -> None:
    prefs = sa.table(PREFS, sa.column("user_id", sa.String), sa.column(PREFS_IDS, sa.JSON))
    for user_id, ids in bind.execute(sa.select(prefs.c.user_id, prefs.c[PREFS_IDS])).all():
        if not ids:
            continue
        moved = [mapping.get(project_id, project_id) for project_id in ids]
        if moved != ids:
            bind.execute(
                prefs.update().where(prefs.c.user_id == user_id).values({PREFS_IDS: moved})
            )


def upgrade() -> None:
    op.create_table(
        "shema_project_rekeys",
        sa.Column("old_id", sa.String(120), primary_key=True),
        sa.Column("new_id", sa.String(36), nullable=False, unique=True),
        sa.Column(
            "rekeyed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    bind = op.get_bind()
    slugs = [
        project_id
        for (project_id,) in bind.execute(sa.text(f"SELECT id FROM {PROJECTS}")).all()
        if not _is_minted(project_id)
    ]
    mapping = {slug: str(uuid.uuid4()) for slug in slugs}

    _move(bind, mapping.items())
    _map_preferences(bind, mapping)
    rekeys = sa.table(REKEYS, sa.column("old_id", sa.String), sa.column("new_id", sa.String))
    if mapping:
        bind.execute(
            rekeys.insert(), [{"old_id": old, "new_id": new} for old, new in mapping.items()]
        )


def downgrade() -> None:
    bind = op.get_bind()
    mapping = {
        new: old for old, new in bind.execute(sa.text(f"SELECT old_id, new_id FROM {REKEYS}")).all()
    }
    _move(bind, mapping.items())
    _map_preferences(bind, mapping)
    op.drop_table("shema_project_rekeys")
