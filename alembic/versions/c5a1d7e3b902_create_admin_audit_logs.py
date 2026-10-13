"""create admin_audit_logs

Revision ID: c5a1d7e3b902
Revises: 84bda627af3d
Create Date: 2026-10-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5a1d7e3b902'
down_revision: Union[str, Sequence[str], None] = '84bda627af3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('admin_audit_logs',
    sa.Column('audit_id', sa.CHAR(length=36), nullable=False),
    sa.Column('actor_email', sa.String(length=255), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('target', sa.String(length=100), nullable=True),
    sa.Column('detail', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('audit_id')
    )
    op.create_index(op.f('ix_admin_audit_logs_created_at'), 'admin_audit_logs', ['created_at'], unique=False)
    op.create_index('ix_admin_audit_logs_actor_action_created', 'admin_audit_logs', ['actor_email', 'action', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_admin_audit_logs_actor_action_created', table_name='admin_audit_logs')
    op.drop_index(op.f('ix_admin_audit_logs_created_at'), table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
