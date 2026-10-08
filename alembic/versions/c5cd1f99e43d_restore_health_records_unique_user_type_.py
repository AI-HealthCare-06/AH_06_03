"""restore health_records unique (user, type, date)

Revision ID: c5cd1f99e43d
Revises: f1d3b7a9c2e4
Create Date: 2026-10-08 14:08:42.472546

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5cd1f99e43d'
down_revision: Union[str, Sequence[str], None] = "f1d3b7a9c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_health_records_user_type_date",
        "health_records",
        ["user_id", "input_type", "examination_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_health_records_user_type_date", "health_records", type_="unique")