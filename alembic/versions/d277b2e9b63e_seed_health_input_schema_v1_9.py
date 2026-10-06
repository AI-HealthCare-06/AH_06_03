"""seed health input schema v1.9

Revision ID: d277b2e9b63e
Revises: 998b0ee91444
Create Date: 2026-10-02 11:10:15.899449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = 'd277b2e9b63e'
down_revision: Union[str, Sequence[str], None] = '998b0ee91444'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schemas = sa.table(
        "health_input_schemas",
        sa.column("health_schema_id", sa.CHAR(36)),
        sa.column("schema_version", sa.String),
        sa.column("model_scope", sa.String),
        sa.column("active_from", sa.DateTime),
    )
    op.bulk_insert(
        schemas,
        [
            {
                "health_schema_id": "01a0f800-0000-7000-8000-000000000001",
                "schema_version": "v1.9",
                "model_scope": "BOTH",
                "active_from": datetime(2026, 9, 29),
            }
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM health_input_schemas WHERE schema_version = 'v1.9'")
