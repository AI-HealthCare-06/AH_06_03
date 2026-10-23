"""community_fame (사람에게 누르는 좋아요 = 인기도)

Revision ID: d4e8a1c7b923
Revises: cf92c31e0691
Create Date: 2026-10-23 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8a1c7b923'
down_revision: Union[str, Sequence[str], None] = 'cf92c31e0691'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('community_fame',
    sa.Column('fame_id', sa.CHAR(length=36), nullable=False),
    sa.Column('giver_id', sa.CHAR(length=36), nullable=False),
    sa.Column('target_id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['giver_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('fame_id'),
    sa.UniqueConstraint('giver_id', 'target_id')
    )
    op.create_index(op.f('ix_community_fame_giver_id'), 'community_fame', ['giver_id'], unique=False)
    op.create_index(op.f('ix_community_fame_target_id'), 'community_fame', ['target_id'], unique=False)


def downgrade() -> None:
    op.drop_table('community_fame')
