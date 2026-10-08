"""create calendar tables

Revision ID: c1a7e5d2b940
Revises: 021521eb83c3
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'c1a7e5d2b940'
down_revision: Union[str, Sequence[str], None] = '021521eb83c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('calendar_entries',
    sa.Column('entry_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('diary', sa.Text(), nullable=True),
    sa.Column('photo_data', sa.Text().with_variant(mysql.LONGTEXT(), 'mysql'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('entry_id'),
    sa.UniqueConstraint('user_id', 'entry_date')
    )
    op.create_index(op.f('ix_calendar_entries_user_id'), 'calendar_entries', ['user_id'], unique=False)
    op.create_table('health_todos',
    sa.Column('todo_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('todo_date', sa.Date(), nullable=False),
    sa.Column('text', sa.String(length=200), nullable=False),
    sa.Column('done', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('todo_id')
    )
    op.create_index(op.f('ix_health_todos_user_id'), 'health_todos', ['user_id'], unique=False)
    op.create_index('ix_health_todos_user_date', 'health_todos', ['user_id', 'todo_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('health_todos')      # 인덱스는 테이블과 함께 사라진다 (FK가 쓰는 인덱스는 따로 못 지움)
    op.drop_table('calendar_entries')
