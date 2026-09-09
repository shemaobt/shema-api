"""merge sound_necklace main head into obt-204

Revision ID: 4d03da4c47a7
Revises: 20260704_0001, 20260717_0003
Create Date: 2026-07-17 17:24:33.559762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d03da4c47a7'
down_revision: Union[str, None] = ('20260704_0001', '20260717_0003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
