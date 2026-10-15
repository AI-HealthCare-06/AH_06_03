"""merge migration heads

Revision ID: 337350f8b7c9
Revises: 329f655646e6, d2f9a6c3e714
Create Date: 2026-10-15 13:15:04.252734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '337350f8b7c9'
down_revision: Union[str, Sequence[str], None] = ('329f655646e6', 'd2f9a6c3e714')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
