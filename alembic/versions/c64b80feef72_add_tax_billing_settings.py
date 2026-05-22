"""add_tax_billing_settings

Revision ID: c64b80feef72
Revises: d12848bf5d4a
Create Date: 2026-05-20 15:43:28.358870

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'c64b80feef72'
down_revision: Union[str, Sequence[str], None] = 'd12848bf5d4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    tax_billing_settings already exists in DB with the correct schema.
    No DDL changes required — this migration only advances the revision pointer.
    """
    pass


def downgrade() -> None:
    pass
