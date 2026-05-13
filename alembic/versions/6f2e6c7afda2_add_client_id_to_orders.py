"""add client_id to orders

Revision ID: 6f2e6c7afda2
Revises: eb8ce872e199
Create Date: 2026-05-04 12:07:17.045486

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6f2e6c7afda2'
down_revision: Union[str, Sequence[str], None] = 'eb8ce872e199'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('orders', sa.Column('client_id', sa.Integer(), nullable=True))

    op.create_foreign_key(
        'fk_orders_client',
        'orders',
        'clients',
        ['client_id'],
        ['id']
    )

    op.create_index('ix_orders_client_id', 'orders', ['client_id'])


def downgrade():
    op.drop_index('ix_orders_client_id', table_name='orders')

    op.drop_constraint('fk_orders_client', 'orders', type_='foreignkey')

    op.drop_column('orders', 'client_id')