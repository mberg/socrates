"""guidance_session.revealed_at

Revision ID: e1a7c3f4b2d9
Revises: bc4b678c9d0e
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1a7c3f4b2d9'
down_revision: Union[str, Sequence[str], None] = 'bc4b678c9d0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('guidance_session', sa.Column('revealed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('guidance_session', 'revealed_at')
