from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '9b44bd1d1bc8'
down_revision: Union[str, Sequence[str], None] = 'c3d286b9f1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ✅ add code column
    op.add_column(
        'clients',
        sa.Column(
            'code',
            sa.String(length=20),
            nullable=True
        )
    )

    # ✅ unique constraint
    op.create_unique_constraint(
        'uq_partner_client_code',
        'clients',
        ['partner_id', 'code']
    )


def downgrade() -> None:

    op.drop_constraint(
        'uq_partner_client_code',
        'clients',
        type_='unique'
    )

    op.drop_column('clients', 'code')