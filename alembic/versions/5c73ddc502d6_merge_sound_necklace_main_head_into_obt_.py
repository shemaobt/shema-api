"""merge sound_necklace main head into obt-198

Revision ID: 5c73ddc502d6
Revises: 20260704_0002, 20260717_0003
Create Date: 2026-07-17 17:23:42.573212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c73ddc502d6'
down_revision: Union[str, None] = ('20260704_0002', '20260717_0003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
