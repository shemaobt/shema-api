"""ir_takes.chunk_index holds a stretch's ordinal, so it is called ordinal

The column carries the persistent number of the stretch a take tells, written where a
stretch is captured. **Chunk** is something else: the numbered position a stretch takes in
the list the analyst receives in one reading, alive only for the length of that call. The
old name taught the retired meaning to everybody who read the schema next, the same way
``team_id`` carried a second word for the team until it was renamed.

Renamed rather than added beside. Every row already holds the right number under the wrong
name, and two columns for one number is exactly the thing this ends. The downgrade renames
it back, so nothing that was in the column can be lost by going backwards.

Revision ID: 20260910_take01
Revises: 20260908_arr02
"""

from alembic import op

revision = "20260910_take01"
down_revision = "20260908_arr02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ir_takes", "chunk_index", new_column_name="ordinal")


def downgrade() -> None:
    op.alter_column("ir_takes", "ordinal", new_column_name="chunk_index")
