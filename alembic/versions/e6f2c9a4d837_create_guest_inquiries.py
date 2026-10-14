"""create guest_inquiries (비회원 문의)

Revision ID: e6f2c9a4d837
Revises: d5e1b8a3c726
Create Date: 2026-10-14 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f2c9a4d837'
down_revision: Union[str, Sequence[str], None] = 'd5e1b8a3c726'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('guest_inquiries',
    sa.Column('guest_inquiry_id', sa.CHAR(length=36), nullable=False),
    sa.Column('code_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('ip_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=True),
    sa.Column('answered_by', sa.String(length=255), nullable=True),
    sa.Column('answered_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('guest_inquiry_id'),
    sa.UniqueConstraint('code_hash')
    )
    op.create_index(op.f('ix_guest_inquiries_ip_hash'), 'guest_inquiries', ['ip_hash'], unique=False)
    op.create_index(op.f('ix_guest_inquiries_created_at'), 'guest_inquiries', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_guest_inquiries_created_at'), table_name='guest_inquiries')
    op.drop_index(op.f('ix_guest_inquiries_ip_hash'), table_name='guest_inquiries')
    op.drop_table('guest_inquiries')
