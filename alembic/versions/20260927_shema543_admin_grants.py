"""the Admin grants: invites that carry regions, and a trail of every region scope change

Revision ID: 20260927_shema543
Revises: 20260927_shema524
Create Date: 2026-09-27

The parent was `20260927_shema08` when this file was written (27/sep/2026); on 28/sep, when
OBT-524 merged first, it was re-pointed to `20260927_shema524`, the head `alembic heads` read
then — a measurement, not a value to remember (`docs/shema.md` §7.1). The id carries the
issue number, as `20260927_shema531` does, so two siblings cannot mint the same `shema09`.

Three changes, one issue (OBT-543, the Admin's access surface):

`access_invites.region_keys` is the region scope a regional Shemá role arrives with: the
Admin invites a `coordinator` *and* the regions it reaches, and acceptance writes both in one
commit. JSON, NULL for every role that is not regional. **The downgrade drops it**, and an
invite still pending then grants a regional role with no region — which reaches nothing
(`docs/shema.md` §6.1), so it fails closed.

`shema_user_regions.granted_by` gains `ON DELETE SET NULL`. `20260911_shema01` declared the
foreign key inline with no action, so PostgreSQL named it `shema_user_regions_granted_by_fkey`
and would refuse to delete an account it points at. Nothing wrote a person there until this
issue; the Admin's surface does, and deleting that Admin's account would then fail. `SET NULL`
is what the model's docstring always said the column does.

`shema_scope_changes` is the trail: one row per region entering or leaving an account's
scope, by whom and when. Append-only by the trigger the module's other trails use, re-issuing
`shema_reject_write()` with `CREATE OR REPLACE` as `20260911_shema02` does. **No foreign key on
its two account columns**: `SET NULL` is an UPDATE and `CASCADE` a DELETE, and the trigger
refuses both, so either would make deleting an account raise. The region column reuses
`shema_region_key_enum` through `postgresql.ENUM(create_type=False)` — `sa.Enum` drops that
keyword on the floor (`20260724_0001` records why) — and the downgrade leaves the type and the
function alone, because other tables own them.

Written by hand like every revision here: `alembic/env.py` sees no metadata, so
`--autogenerate` would propose dropping every table (`docs/resource_requests.md` §8.1). Plain
PostgreSQL, because no migration in this repository runs under SQLite (`docs/shema.md` §7.2).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260927_shema543"
down_revision = "20260927_shema524"
branch_labels = None
depends_on = None

REGION_KEY = postgresql.ENUM(
    "south-america",
    "north-america",
    "africa",
    "asia",
    "oceania",
    "europe",
    "other",
    name="shema_region_key_enum",
    create_type=False,
)

GRANTED_BY_FK = "shema_user_regions_granted_by_fkey"

APPEND_ONLY_FUNCTION = (
    "CREATE OR REPLACE FUNCTION shema_reject_write() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql"
)


def upgrade() -> None:
    op.add_column("access_invites", sa.Column("region_keys", sa.JSON(), nullable=True))

    op.drop_constraint(GRANTED_BY_FK, "shema_user_regions", type_="foreignkey")
    op.create_foreign_key(
        GRANTED_BY_FK,
        "shema_user_regions",
        "users",
        ["granted_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "shema_scope_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("region_key", REGION_KEY, nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.String(36), nullable=True),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shema_scope_changes_changed_at", "shema_scope_changes", ["changed_at"])

    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER shema_scope_changes_append_only "
        "BEFORE UPDATE OR DELETE ON shema_scope_changes "
        "FOR EACH ROW EXECUTE FUNCTION shema_reject_write()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS shema_scope_changes_append_only ON shema_scope_changes")
    op.drop_index("ix_shema_scope_changes_changed_at", table_name="shema_scope_changes")
    op.drop_table("shema_scope_changes")

    op.drop_constraint(GRANTED_BY_FK, "shema_user_regions", type_="foreignkey")
    op.create_foreign_key(GRANTED_BY_FK, "shema_user_regions", "users", ["granted_by"], ["id"])

    op.drop_column("access_invites", "region_keys")
