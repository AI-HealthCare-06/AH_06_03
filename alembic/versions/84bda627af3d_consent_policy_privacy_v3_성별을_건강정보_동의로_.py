"""consent policy privacy v3 (성별을 건강정보 동의로 이동)

Revision ID: 84bda627af3d
Revises: 729ceb6de7e2
Create Date: 2026-10-13 13:28:29.886506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84bda627af3d'
down_revision: Union[str, Sequence[str], None] = '729ceb6de7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text(
        "SELECT 1 FROM consent_policies WHERE policy_type = 'privacy' AND version = 'v3'")).first():
        return
    conn.execute(sa.text("""
        INSERT INTO consent_policies
            (policy_id, policy_type, version, purpose_text, collection_items,
             retention_policy, withdrawal_method, third_party_notice, published_at)
        SELECT UUID(), policy_type, 'v3', purpose_text,
               REPLACE(collection_items, ', 성별(건강정보 입력 때 선택)', ''),
               retention_policy, withdrawal_method, third_party_notice, NOW()
        FROM consent_policies
        WHERE policy_type = 'privacy' AND version = 'v2'
    """))


def downgrade() -> None:
    op.execute("DELETE FROM consent_policies WHERE policy_type = 'privacy' AND version = 'v3'")
