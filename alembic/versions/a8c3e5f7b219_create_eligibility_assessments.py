"""create eligibility_assessments

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
    op.create_table('eligibility_assessments',
    sa.Column('assessment_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('result_code', sa.Enum('eligible', 'age_out', 'diagnosed', 'emergency', name='eligibility_result'), nullable=False),
    sa.Column('age_eligible', sa.Boolean(), nullable=False),
    sa.Column('diagnosed_cad', sa.Boolean(), nullable=False),
    sa.Column('emergency_flag', sa.Boolean(), nullable=False),
    sa.Column('emergency_acknowledged_at', sa.DateTime(), nullable=True),
    sa.Column('assessed_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('assessment_id')
    )
    op.create_index('ix_eligibility_assessments_user_assessed', 'eligibility_assessments', ['user_id', 'assessed_at'], unique=False)


def downgrade() -> None:
    op.drop_table('eligibility_assessments')
