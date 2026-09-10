"""merge sound_necklace main head into obt-256

Revision ID: d7691839f477
Revises: 20260715_0002, 20260717_0003
Create Date: 2026-07-17 17:41:19.620633

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7691839f477'
down_revision: Union[str, None] = ('20260715_0002', '20260717_0003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
