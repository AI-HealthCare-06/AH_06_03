"""user_characters.eye (눈 색)

Revision ID: e1b7c4d92a58
Revises: d4e8a1c7b923
Create Date: 2026-10-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1b7c4d92a58'
down_revision: Union[str, Sequence[str], None] = 'd4e8a1c7b923'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_characters', sa.Column('eye', sa.String(length=20), nullable=False, server_default='#243749'))


def downgrade() -> None:
    op.drop_column('user_characters', 'eye')
