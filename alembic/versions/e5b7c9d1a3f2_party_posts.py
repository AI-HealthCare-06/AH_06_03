"""community_posts에 party_id 칸 추가 (파티 피드)

Revision ID: e5b7c9d1a3f2
Revises: 337350f8b7c9
Create Date: 2026-10-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5b7c9d1a3f2'
down_revision: Union[str, Sequence[str], None] = '337350f8b7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('community_posts', sa.Column('party_id', sa.CHAR(length=36), nullable=True))
    op.create_index('ix_community_posts_party_id', 'community_posts', ['party_id'])
    op.create_foreign_key('fk_community_posts_party', 'community_posts', 'parties', ['party_id'], ['party_id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_community_posts_party', 'community_posts', type_='foreignkey')
    op.drop_index('ix_community_posts_party_id', table_name='community_posts')
    op.drop_column('community_posts', 'party_id')
