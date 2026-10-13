"""consent policy health_data v4 (철회 시 삭제 범위)

Revision ID: 729ceb6de7e2
Revises: 980618918c12
Create Date: 2026-10-13 13:07:59.398543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

NEW_SENTENCE = " 동의를 철회하면 건강기록·설문·분석·챌린지·캘린더·대상 확인·성별이 삭제됩니다."

# revision identifiers, used by Alembic.
revision: str = '729ceb6de7e2'
down_revision: Union[str, Sequence[str], None] = '980618918c12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # 이미 v4가 있으면 건너뜀 (두 번 실행돼도 안전하게)
    has_v4 = conn.execute(sa.text(
        "SELECT 1 FROM consent_policies WHERE policy_type = 'health_data' AND version = 'v4'")).first()
    if has_v4:
        return
    # v3을 그대로 복사하되, 보유·이용 기간 문구 뒤에 새 문장을 붙이고 오늘 날짜로 공개
    conn.execute(sa.text("""
        INSERT INTO consent_policies
            (policy_id, policy_type, version, purpose_text, collection_items,
             retention_policy, withdrawal_method, third_party_notice, published_at)
        SELECT UUID(), policy_type, 'v4', purpose_text, collection_items,
               CONCAT(retention_policy, :sentence), withdrawal_method, third_party_notice, NOW()
        FROM consent_policies
        WHERE policy_type = 'health_data' AND version = 'v3'
    """), {"sentence": NEW_SENTENCE})


def downgrade() -> None:
    op.execute("DELETE FROM consent_policies WHERE policy_type = 'health_data' AND version = 'v4'")