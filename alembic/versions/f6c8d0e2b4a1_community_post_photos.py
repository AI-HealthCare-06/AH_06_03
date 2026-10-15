"""글 사진 표 (community_post_photos)

Revision ID: f6c8d0e2b4a1
Revises: e5b7c9d1a3f2
Create Date: 2026-10-15 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = 'f6c8d0e2b4a1'
down_revision: Union[str, Sequence[str], None] = 'e5b7c9d1a3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'community_post_photos',
        sa.Column('photo_id', sa.CHAR(length=36), nullable=False),
        sa.Column('post_id', sa.CHAR(length=36), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('data', sa.LargeBinary().with_variant(mysql.MEDIUMBLOB(), 'mysql'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.post_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('photo_id'),
        sa.UniqueConstraint('post_id', 'position'),
    )
    op.create_index('ix_community_post_photos_post_id', 'community_post_photos', ['post_id'])


def downgrade() -> None:
    op.drop_index('ix_community_post_photos_post_id', table_name='community_post_photos')
    op.drop_table('community_post_photos')
