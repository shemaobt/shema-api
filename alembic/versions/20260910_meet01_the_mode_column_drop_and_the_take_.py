"""the mode column drop and the take ordinal meet

Revision ID: 20260910_meet01
Revises: 20260909_mode01, 20260910_take01
Create Date: 2026-09-10 12:42:31.792563

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260910_meet01"
down_revision: tuple[str, str] = ("20260909_mode01", "20260910_take01")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
