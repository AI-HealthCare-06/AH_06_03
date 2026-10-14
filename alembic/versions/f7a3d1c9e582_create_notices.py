"""create notices

Revision ID: f7a3d1c9e582
Revises: e6f2c9a4d837
Create Date: 2026-10-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a3d1c9e582'
down_revision: Union[str, Sequence[str], None] = 'e6f2c9a4d837'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notices',
    sa.Column('notice_id', sa.CHAR(length=36), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=False),
    sa.Column('ends_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('notice_id')
    )
    op.create_index(op.f('ix_notices_starts_at'), 'notices', ['starts_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notices_starts_at'), table_name='notices')
    op.drop_table('notices')
