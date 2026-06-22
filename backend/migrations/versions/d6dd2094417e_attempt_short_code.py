"""attempt short code

Revision ID: d6dd2094417e
Revises: 0d3d05175ab7
Create Date: 2026-06-22 15:15:47.561033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd6dd2094417e'
down_revision: Union[str, Sequence[str], None] = '0d3d05175ab7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('attempt', sa.Column('code', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index(op.f('ix_attempt_code'), 'attempt', ['code'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_attempt_code'), table_name='attempt')
    op.drop_column('attempt', 'code')
