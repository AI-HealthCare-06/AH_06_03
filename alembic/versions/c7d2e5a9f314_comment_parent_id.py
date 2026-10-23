"""community comment parent_id (대댓글)

Revision ID: c7d2e5a9f314
Revises: 1a9a51da1d1a
Create Date: 2026-10-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2e5a9f314'
down_revision: Union[str, Sequence[str], None] = '1a9a51da1d1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('community_comments', sa.Column('parent_id', sa.CHAR(length=36), nullable=True))
    op.create_index(op.f('ix_community_comments_parent_id'), 'community_comments', ['parent_id'], unique=False)
    op.create_foreign_key('fk_community_comments_parent', 'community_comments', 'community_comments',
                          ['parent_id'], ['comment_id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_community_comments_parent', 'community_comments', type_='foreignkey')
    op.drop_index(op.f('ix_community_comments_parent_id'), table_name='community_comments')
    op.drop_column('community_comments', 'parent_id')
