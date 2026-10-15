"""community_posts에 붙인 챌린지 카드 칸 추가

Revision ID: d2f9a6c3e714
Revises: c1e8b4a7d392
Create Date: 2026-10-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2f9a6c3e714'
down_revision: Union[str, Sequence[str], None] = 'c1e8b4a7d392'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('community_posts', sa.Column('attach_kind', sa.String(length=10), nullable=True))
    op.add_column('community_posts', sa.Column('attach_label', sa.String(length=150), nullable=True))
    op.add_column('community_posts', sa.Column('attach_days', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('community_posts', 'attach_days')
    op.drop_column('community_posts', 'attach_label')
    op.drop_column('community_posts', 'attach_kind')
