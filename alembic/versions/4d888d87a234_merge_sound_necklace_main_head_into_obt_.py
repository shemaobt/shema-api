"""merge sound_necklace main head into obt-262

Revision ID: 4d888d87a234
Revises: 20260716_0002, 20260717_0003
Create Date: 2026-07-17 17:16:08.758588

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d888d87a234'
down_revision: Union[str, None] = ('20260716_0002', '20260717_0003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
