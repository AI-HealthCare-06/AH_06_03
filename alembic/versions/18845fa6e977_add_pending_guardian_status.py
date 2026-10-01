"""add pending_guardian status

Revision ID: 18845fa6e977
Revises: 97a98068364a
Create Date: 2026-10-01 18:29:28.056921

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18845fa6e977'
down_revision: Union[str, Sequence[str], None] = '97a98068364a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "status",
        existing_type=sa.Enum("active", "deleted", name="user_status"),
        type_=sa.Enum("active", "deleted", "pending_guardian", name="user_status"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "status",
        existing_type=sa.Enum("active", "deleted", "pending_guardian", name="user_status"),
        type_=sa.Enum("active", "deleted", name="user_status"),
        existing_nullable=False,
    )
