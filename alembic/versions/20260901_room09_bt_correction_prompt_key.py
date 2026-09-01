"""register the back-translation correction prompt key

A correction of one stretch is verified against the finding it answers, by a second
analyst prompt that never sees the other stretches. Its key is a value of the room's
prompt-key enum, and Postgres refuses a value the type does not carry — so without this
the first `terminei` after a correction fails on the insert, in production only. The
tests run on SQLite, where the type is a check constraint the schema is rebuilt from,
and would never say so.

No table changes: `ir_prompts` already holds the row, and the room seeds a default for
any key that has none.

Revision ID: 20260901_room09
Revises: 20260831_lang01
"""

from alembic import op

revision = "20260901_room09"
down_revision = "20260831_lang01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE ir_prompt_key_enum ADD VALUE IF NOT EXISTS 'bt_correction'")


def downgrade() -> None:
    """Left standing on purpose.

    Postgres cannot drop one value from an enum type, and rebuilding the type to remove it
    would have to rewrite every row of `ir_prompts` that names it. A value nothing reads is
    inert; the rewrite is not.
    """
