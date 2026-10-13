"""이용약관 v3: 예측 → 분석 용어, 체험 기간 삭제 일정

이용약관 v2 문구에서 필요한 부분만 바꿔 v3로 새로 넣는다. 예전 버전(v1·v2)은 그대로 둔다
(예전에 동의한 사람의 기록이 그대로 남아야 한다).

Revision ID: f3c8a1d5b7e2
Revises: c5a1d7e3b902
Create Date: 2026-10-13 15:30:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f3c8a1d5b7e2'
down_revision: Union[str, Sequence[str], None] = 'c5a1d7e3b902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRIAL = ' 체험 버전에서는 체험이 끝나는 날부터 일주일 안에 탈퇴하지 않은 분의 정보도 삭제하며, 서버 백업 사본은 최대 일주일 더 보관한 뒤 지웁니다.'
EDITS = {
    'purpose_text': [('고혈압 위험을 예측하고', '고혈압 위험 신호를 분석하고'), ('예측 결과는 참고용', '분석 결과는 참고용')],
    'retention_policy': [('계정 식별자는 익명 처리합니다.', '계정 식별자는 익명 처리합니다.' + TRIAL)],
}
SQL_GET = ("SELECT purpose_text, collection_items, retention_policy, withdrawal_method, third_party_notice "
           "FROM consent_policies WHERE policy_type = 'terms_of_service' AND version = 'v2'")


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM consent_policies WHERE policy_type = 'terms_of_service' AND version = 'v3'")).first():
        return    # 두 번 실행돼도 안전하게
    row = conn.execute(sa.text(SQL_GET)).mappings().first()
    if row is None:
        raise RuntimeError('이용약관 v2 문구를 찾지 못했습니다')
    cols = dict(row)
    for col, pairs in EDITS.items():
        for old, new in pairs:
            if old not in cols[col]:
                raise RuntimeError(f'이용약관 v2.{col} 에서 찾지 못했습니다: {old}')
            cols[col] = cols[col].replace(old, new)
    conn.execute(sa.text(
        "INSERT INTO consent_policies (policy_id, policy_type, version, purpose_text, collection_items, "
        "retention_policy, withdrawal_method, third_party_notice, published_at) "
        "VALUES (:id, 'terms_of_service', 'v3', :p, :c, :r, :w, :t, :now)"),
        {'id': str(uuid.uuid4()), 'p': cols['purpose_text'], 'c': cols['collection_items'], 'r': cols['retention_policy'],
         'w': cols['withdrawal_method'], 't': cols['third_party_notice'], 'now': datetime.utcnow()})


def downgrade() -> None:
    op.execute("DELETE FROM consent_policies WHERE policy_type = 'terms_of_service' AND version = 'v3'")
