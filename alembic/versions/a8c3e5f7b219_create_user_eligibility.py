"""create user_eligibility

Revision ID: a8c3e5f7b219
Revises: 3d0c145a545a
Create Date: 2026-10-08 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8c3e5f7b219'
down_revision: Union[str, Sequence[str], None] = '3d0c145a545a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_eligibility',
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('age_band', sa.Enum('in', 'bOnly', 'under19', name='eligibility_age_band'), nullable=False),
    sa.Column('chd', sa.Boolean(), nullable=False),
    sa.Column('emergency', sa.Enum('no', 'yes', 'unsure', name='eligibility_emergency'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('user_eligibility')
