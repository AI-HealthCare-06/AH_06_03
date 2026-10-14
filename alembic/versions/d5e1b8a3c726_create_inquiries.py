"""create inquiries (1:1 문의)

Revision ID: d5e1b8a3c726
Revises: c4d9e2a7b315
Create Date: 2026-10-14 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e1b8a3c726'
down_revision: Union[str, Sequence[str], None] = 'c4d9e2a7b315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('inquiries',
    sa.Column('inquiry_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=True),
    sa.Column('answered_by', sa.String(length=255), nullable=True),
    sa.Column('answered_at', sa.DateTime(), nullable=True),
    sa.Column('user_read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('inquiry_id')
    )
    op.create_index(op.f('ix_inquiries_user_id'), 'inquiries', ['user_id'], unique=False)
    op.create_index(op.f('ix_inquiries_created_at'), 'inquiries', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inquiries_created_at'), table_name='inquiries')
    op.drop_index(op.f('ix_inquiries_user_id'), table_name='inquiries')
    op.drop_table('inquiries')
