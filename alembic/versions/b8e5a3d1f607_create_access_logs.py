"""create access_logs (서비스 접속 기록)

Revision ID: b8e5a3d1f607
Revises: f3c8a1d5b7e2
Create Date: 2026-10-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e5a3d1f607'
down_revision: Union[str, Sequence[str], None] = 'f3c8a1d5b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('access_logs',
    sa.Column('access_id', sa.CHAR(length=36), nullable=False),
    sa.Column('account_id', sa.CHAR(length=36), nullable=False),
    sa.Column('event', sa.String(length=20), nullable=False),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('access_id')
    )
    op.create_index(op.f('ix_access_logs_account_id'), 'access_logs', ['account_id'], unique=False)
    op.create_index(op.f('ix_access_logs_created_at'), 'access_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_access_logs_created_at'), table_name='access_logs')
    op.drop_index(op.f('ix_access_logs_account_id'), table_name='access_logs')
    op.drop_table('access_logs')
