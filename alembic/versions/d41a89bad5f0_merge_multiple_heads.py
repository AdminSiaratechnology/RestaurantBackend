"""merge multiple heads

Revision ID: d41a89bad5f0
Revises: c64b80feef72, dae6b2992946
Create Date: 2026-06-01 17:25:54.665429

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd41a89bad5f0'
down_revision: Union[str, Sequence[str], None] = ('c64b80feef72', 'dae6b2992946')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
