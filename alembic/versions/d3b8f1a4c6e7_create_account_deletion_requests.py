"""create account_deletion_requests

Revision ID: d3b8f1a4c6e7
Revises: c1a7e5d2b940
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3b8f1a4c6e7'
down_revision: Union[str, Sequence[str], None] = 'c1a7e5d2b940'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('account_deletion_requests',
    sa.Column('deletion_request_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('reauthenticated_at', sa.DateTime(), nullable=False),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('status', sa.Enum('requested', 'processing', 'completed', 'failed', name='deletion_status'), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('result_summary', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
    sa.PrimaryKeyConstraint('deletion_request_id')
    )
    op.create_index(op.f('ix_account_deletion_requests_user_id'), 'account_deletion_requests', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('account_deletion_requests')
