"""merge sound_necklace main head into obt-250

Revision ID: 00d369476436
Revises: 20260710_0001, 20260717_0003
Create Date: 2026-07-17 17:37:53.488698

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00d369476436'
down_revision: Union[str, None] = ('20260710_0001', '20260717_0003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
