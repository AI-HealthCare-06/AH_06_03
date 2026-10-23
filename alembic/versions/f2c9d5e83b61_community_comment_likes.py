"""community_comment_likes (댓글 좋아요)

Revision ID: f2c9d5e83b61
Revises: e1b7c4d92a58
Create Date: 2026-10-23 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c9d5e83b61'
down_revision: Union[str, Sequence[str], None] = 'e1b7c4d92a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('community_comment_likes',
    sa.Column('like_id', sa.CHAR(length=36), nullable=False),
    sa.Column('comment_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['community_comments.comment_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('like_id'),
    sa.UniqueConstraint('comment_id', 'user_id')
    )
    op.create_index(op.f('ix_community_comment_likes_comment_id'), 'community_comment_likes', ['comment_id'], unique=False)
    op.create_index(op.f('ix_community_comment_likes_user_id'), 'community_comment_likes', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('community_comment_likes')
