"""drop ir_prompts, its enum type, and the seeder nothing ever called

The room's prompt fallback was `get_prompt_text`: a stored row if one existed, otherwise
the committed markdown file next to the service. No writer for that row was ever built —
the one insert path, `seed_room_prompts`, has zero callers in this tree — so the table sat
empty in every environment reachable, and DEV's own copy of the database did not even have
the relation (`UndefinedTableError`). The fallback was the only path ever exercised:
nobody could tell which prompt the room was actually running on, because the answer was
always the file, silently.

`get_prompt_text` now reads the file directly, with no database round trip to fall through
from. This migration follows that change by removing what it made unreachable: `ir_prompts`,
its `ir_prompt_key_enum` type, and the eight rows `seed_room_prompts` would have written had
anything ever called it.

Revision ID: 20260902_room09
Revises: 20260831_lang01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260902_room09"
down_revision = "20260831_lang01"
branch_labels = None
depends_on = None


_PROMPT_KEY_ENUM = sa.Enum(
    "guide",
    "validator",
    "coverage_classifier",
    "book_panorama",
    "draft_self_check",
    "bt_analyst",
    "bt_verdict_speaker",
    "comprehension_assessor",
    name="ir_prompt_key_enum",
)


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ir_prompts")
    _PROMPT_KEY_ENUM.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.create_table(
        "ir_prompts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key", _PROMPT_KEY_ENUM, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ir_prompts_key", "ir_prompts", ["key"], unique=True)
