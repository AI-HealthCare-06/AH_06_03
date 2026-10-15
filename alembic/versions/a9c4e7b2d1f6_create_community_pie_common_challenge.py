"""create community, pie ledger, common challenges

Revision ID: a9c4e7b2d1f6
Revises: f7a3d1c9e582
Create Date: 2026-10-14 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c4e7b2d1f6'
down_revision: Union[str, Sequence[str], None] = 'f7a3d1c9e582'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 커뮤니티
    op.create_table('community_profiles',
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('nickname', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('nickname')
    )
    op.create_table('community_posts',
    sa.Column('post_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('post_id')
    )
    op.create_index(op.f('ix_community_posts_user_id'), 'community_posts', ['user_id'], unique=False)
    op.create_index(op.f('ix_community_posts_category'), 'community_posts', ['category'], unique=False)
    op.create_index(op.f('ix_community_posts_created_at'), 'community_posts', ['created_at'], unique=False)
    op.create_table('community_comments',
    sa.Column('comment_id', sa.CHAR(length=36), nullable=False),
    sa.Column('post_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('body', sa.String(length=300), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['community_posts.post_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('comment_id')
    )
    op.create_index(op.f('ix_community_comments_post_id'), 'community_comments', ['post_id'], unique=False)
    op.create_index(op.f('ix_community_comments_user_id'), 'community_comments', ['user_id'], unique=False)
    op.create_table('community_likes',
    sa.Column('like_id', sa.CHAR(length=36), nullable=False),
    sa.Column('post_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['community_posts.post_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('like_id'),
    sa.UniqueConstraint('post_id', 'user_id')
    )
    op.create_index(op.f('ix_community_likes_post_id'), 'community_likes', ['post_id'], unique=False)
    op.create_index(op.f('ix_community_likes_user_id'), 'community_likes', ['user_id'], unique=False)
    op.create_table('community_reports',
    sa.Column('report_id', sa.CHAR(length=36), nullable=False),
    sa.Column('post_id', sa.CHAR(length=36), nullable=True),
    sa.Column('comment_id', sa.CHAR(length=36), nullable=True),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('target_key', sa.String(length=50), nullable=False),
    sa.Column('reason', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('action', sa.String(length=10), nullable=True),
    sa.Column('handled_by', sa.String(length=255), nullable=True),
    sa.Column('handled_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['post_id'], ['community_posts.post_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['comment_id'], ['community_comments.comment_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('report_id'),
    sa.UniqueConstraint('user_id', 'target_key')
    )
    op.create_index(op.f('ix_community_reports_post_id'), 'community_reports', ['post_id'], unique=False)
    op.create_index(op.f('ix_community_reports_comment_id'), 'community_reports', ['comment_id'], unique=False)
    op.create_index(op.f('ix_community_reports_user_id'), 'community_reports', ['user_id'], unique=False)

    # ---- 파이 장부
    op.create_table('pie_ledger',
    sa.Column('entry_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('delta', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=40), nullable=False),
    sa.Column('ref_key', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('entry_id'),
    sa.UniqueConstraint('user_id', 'reason', 'ref_key')
    )
    op.create_index(op.f('ix_pie_ledger_user_id'), 'pie_ledger', ['user_id'], unique=False)
    op.create_index(op.f('ix_pie_ledger_created_at'), 'pie_ledger', ['created_at'], unique=False)

    # ---- 공통 챌린지
    op.create_table('common_challenges',
    sa.Column('challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('title', sa.String(length=60), nullable=False),
    sa.Column('proof_type', sa.String(length=10), nullable=False),
    sa.Column('target_steps', sa.Integer(), nullable=True),
    sa.Column('starts_on', sa.Date(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=False),
    sa.Column('complete_min_days', sa.Integer(), nullable=False),
    sa.Column('reward_first', sa.Integer(), nullable=False),
    sa.Column('reward_second', sa.Integer(), nullable=False),
    sa.Column('reward_third', sa.Integer(), nullable=False),
    sa.Column('reward_complete', sa.Integer(), nullable=False),
    sa.Column('finalized_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('challenge_id')
    )
    op.create_index(op.f('ix_common_challenges_starts_on'), 'common_challenges', ['starts_on'], unique=False)
    op.create_table('common_challenge_participants',
    sa.Column('participant_id', sa.CHAR(length=36), nullable=False),
    sa.Column('challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('joined_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['common_challenges.challenge_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('participant_id'),
    sa.UniqueConstraint('challenge_id', 'user_id')
    )
    op.create_index(op.f('ix_common_challenge_participants_challenge_id'), 'common_challenge_participants', ['challenge_id'], unique=False)
    op.create_index(op.f('ix_common_challenge_participants_user_id'), 'common_challenge_participants', ['user_id'], unique=False)
    op.create_table('common_challenge_certs',
    sa.Column('cert_id', sa.CHAR(length=36), nullable=False),
    sa.Column('challenge_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('cert_date', sa.Date(), nullable=False),
    sa.Column('steps', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['common_challenges.challenge_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('cert_id'),
    sa.UniqueConstraint('challenge_id', 'user_id', 'cert_date')
    )
    op.create_index(op.f('ix_common_challenge_certs_challenge_id'), 'common_challenge_certs', ['challenge_id'], unique=False)
    op.create_index(op.f('ix_common_challenge_certs_user_id'), 'common_challenge_certs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('common_challenge_certs')
    op.drop_table('common_challenge_participants')
    op.drop_table('common_challenges')
    op.drop_table('pie_ledger')
    op.drop_table('community_reports')
    op.drop_table('community_likes')
    op.drop_table('community_comments')
    op.drop_table('community_posts')
    op.drop_table('community_profiles')
