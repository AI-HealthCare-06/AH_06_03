"""users.suspended_until (이용 정지)

Revision ID: a7d9e1f3c5b2
Revises: f6c8d0e2b4a1
Create Date: 2026-10-15 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d9e1f3c5b2'
down_revision: Union[str, Sequence[str], None] = 'f6c8d0e2b4a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('suspended_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'suspended_until')
