"""동의 문구 개정: 예측→분석, 검진 결과지 사진(OCR) 문장 삭제, 체험 기간 삭제 일정 반영

- 건강정보 v3 → v4, 이용약관 v2 → v3, 개인정보 v2 → v3 (각각 이전 버전 문구에서 필요한 부분만 바꾼다)
- 이번 체험 버전에는 검진 결과지 사진 자동 입력이 없으므로 전송 문장을 뺀다.

Revision ID: d8f2a4c6e019
Revises: b7e2d4f6a891
Create Date: 2026-10-13 10:00:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd8f2a4c6e019'
down_revision: Union[str, Sequence[str], None] = 'b7e2d4f6a891'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRIAL = ' 체험 버전에서는 체험이 끝나는 날부터 일주일 안에 탈퇴하지 않은 분의 정보도 삭제하며, 서버 백업 사본은 최대 일주일 더 보관한 뒤 지웁니다.'

# (policy_type, 이전 버전, 새 버전, {컬럼: [(찾을 문구, 바꿀 문구), ...]})
PLANS = [
    ('health_data', 'v3', 'v4', {
        'purpose_text': [('혈압 위험 예측과', '혈압 위험 신호 분석과')],
        'collection_items': [
            ('. 검진 결과지 사진 자동 입력 기능을 쓰는 경우에만 검진 결과지 사진(값을 읽는 데만 쓰고 저장하지 않습니다)', ''),
        ],
        'withdrawal_method': [('위험 예측과 챌린지 기능', '위험 신호 분석과 챌린지 기능')],
        'retention_policy': [
            ('새로운 입력과 예측이 중단되고', '새로운 입력과 분석이 중단되고'),
            ('회원 탈퇴 시 모두 삭제합니다. 검진 결과지 사진은 숫자를 읽어 낸 즉시 폐기하며 서버에 저장하지 않습니다. ',
             '회원 탈퇴 시 모두 삭제합니다.' + TRIAL + ' '),
        ],
        'third_party_notice': [
            ('위험 예측과 챌린지 추천에만', '위험 신호 분석과 챌린지 추천에만'),
            ('예측 결과는 의료적 진단이 아닙니다.', '분석 결과는 의료적 진단이 아닙니다.'),
            (' 검진 결과지 사진 자동 입력을 쓰면, 사진은 글자를 읽기 위해 외부 글자 인식·AI 서비스(네이버클라우드 Clova OCR, OpenAI)로 전송되며 사진 자체는 저장하지 않습니다. 사용하지 않으면 전송되지 않습니다.', ''),
        ],
    }),
    ('terms_of_service', 'v2', 'v3', {
        'purpose_text': [('고혈압 위험을 예측하고', '고혈압 위험 신호를 분석하고'), ('예측 결과는 참고용', '분석 결과는 참고용')],
        'retention_policy': [('계정 식별자는 익명 처리합니다.', '계정 식별자는 익명 처리합니다.' + TRIAL)],
    }),
    ('privacy', 'v2', 'v3', {
        'retention_policy': [('탈퇴 즉시 삭제합니다.', '탈퇴 즉시 삭제합니다.' + TRIAL)],
    }),
]
SQL_GET = ("SELECT purpose_text, collection_items, retention_policy, withdrawal_method, third_party_notice "
           "FROM consent_policies WHERE policy_type = :t AND version = :v")


def upgrade() -> None:
    conn = op.get_bind()
    for ptype, old_v, new_v, edits in PLANS:
        if conn.execute(sa.text("SELECT 1 FROM consent_policies WHERE policy_type = :t AND version = :v"),
                        {'t': ptype, 'v': new_v}).first():
            continue
        row = conn.execute(sa.text(SQL_GET), {'t': ptype, 'v': old_v}).mappings().first()
        if row is None:
            raise RuntimeError(f'{ptype} {old_v} 문구를 찾지 못했습니다')
        cols = dict(row)
        for col, pairs in edits.items():
            for old, new in pairs:
                if old not in cols[col]:
                    raise RuntimeError(f'{ptype} {old_v}.{col} 에서 찾지 못했습니다: {old}')
                cols[col] = cols[col].replace(old, new)
        conn.execute(sa.text(
            "INSERT INTO consent_policies (policy_id, policy_type, version, purpose_text, collection_items, "
            "retention_policy, withdrawal_method, third_party_notice, published_at) "
            "VALUES (:id, :t, :v, :p, :c, :r, :w, :th, :now)"),
            {'id': str(uuid.uuid4()), 't': ptype, 'v': new_v, 'p': cols['purpose_text'], 'c': cols['collection_items'],
             'r': cols['retention_policy'], 'w': cols['withdrawal_method'], 'th': cols['third_party_notice'],
             'now': datetime.utcnow()})


def downgrade() -> None:
    conn = op.get_bind()
    for ptype, _old, new_v, _edits in PLANS:
        conn.execute(sa.text("DELETE FROM consent_policies WHERE policy_type = :t AND version = :v"), {'t': ptype, 'v': new_v})
