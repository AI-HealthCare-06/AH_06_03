"""이용약관 v4 · 개인정보 v4: 조항 형식 약관 전문(terms.html·privacy.html)에 맞춘 동의 요약

v3 문구에서 필요한 부분만 바꿔 v4로 새로 넣는다. 예전 버전은 그대로 둔다
(예전에 동의한 사람의 기록이 그대로 남아야 한다).
- 이용약관: 용어(분석), 게시물 삭제, 전문 안내
- 개인정보: 서비스 접속 기록(3개월)·관리자 기록(2년), 문의 메일·커뮤니티 항목, 구글(Gmail) 처리 안내

Revision ID: c4d9e2a7b315
Revises: b8e5a3d1f607
Create Date: 2026-10-14 15:00:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4d9e2a7b315'
down_revision: Union[str, Sequence[str], None] = 'b8e5a3d1f607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 정책 종류 → (이전 버전 v3 문구에서 바꿀 부분들). 화면의 assets/policies.js 내장 문구도 같은 규칙으로 맞춘다.
EDITS = {
    'terms_of_service': {
        'purpose_text': [
            ('입력하신 건강정보로 고혈압 위험 신호를 분석하고', '입력하신 건강정보를 바탕으로 10년 내 심장 혈관 건강 신호와 혈압 상태를 분석하고'),
            ('참고용 선별 정보입니다', '참고용 정보입니다'),
            ('의사와 상담해 주세요.', '의료기관과 상담해 주세요.'),
            ('가입할 수 있습니다.', '가입할 수 있습니다. 이용약관 전문은 이용약관 화면에서 볼 수 있습니다.'),
        ],
        'retention_policy': [('계정과 서비스 이용 기록을 삭제', '계정과 서비스 이용 기록, 게시물을 삭제')],
    },
    'privacy': {
        'purpose_text': [('서비스 이용 중 알림과 문의 응대를 위해', '서비스 이용 중 알림, 부정 이용 방지, 문의 응대와 커뮤니티 운영을 위해')],
        'collection_items': [('이름과 전화번호는 수집하지 않습니다.',
                              '서비스 접속 기록(로그인 시각·IP), 문의할 때 보내는 이메일 주소와 내용, 커뮤니티에 올린 게시글·댓글. 이름과 전화번호는 수집하지 않습니다.')],
        'retention_policy': [('분리해 보관합니다.', '분리해 보관합니다. 서비스 접속 기록은 3개월, 관리자 행위 기록은 2년 보관합니다. 문의 메일은 답변이 끝나면 삭제합니다.')],
        'third_party_notice': [('서버 운영을 위한 인프라 이용 외에 처리를 맡기는 곳은 없습니다.',
                                '서버 운영은 AWS 서울 리전에 맡기고, 문의 메일은 구글(Gmail)이 처리합니다(국외 이전, 개인정보 처리방침 제5·6조).')],
    },
}
COLS = ('purpose_text', 'collection_items', 'retention_policy', 'withdrawal_method', 'third_party_notice')


def upgrade() -> None:
    conn = op.get_bind()
    for ptype, edits in EDITS.items():
        if conn.execute(sa.text("SELECT 1 FROM consent_policies WHERE policy_type = :t AND version = 'v4'"), {'t': ptype}).first():
            continue    # 두 번 실행돼도 안전하게
        row = conn.execute(sa.text(
            "SELECT purpose_text, collection_items, retention_policy, withdrawal_method, third_party_notice "
            "FROM consent_policies WHERE policy_type = :t AND version = 'v3'"), {'t': ptype}).mappings().first()
        if row is None:
            raise RuntimeError(f'{ptype} v3 문구를 찾지 못했습니다')
        cols = dict(row)
        for col, pairs in edits.items():
            for old, new in pairs:
                if old not in cols[col]:
                    raise RuntimeError(f'{ptype} v3.{col} 에서 찾지 못했습니다: {old}')
                cols[col] = cols[col].replace(old, new)
        conn.execute(sa.text(
            "INSERT INTO consent_policies (policy_id, policy_type, version, purpose_text, collection_items, "
            "retention_policy, withdrawal_method, third_party_notice, published_at) "
            "VALUES (:id, :t, 'v4', :p, :c, :r, :w, :th, :now)"),
            {'id': str(uuid.uuid4()), 't': ptype, 'p': cols['purpose_text'], 'c': cols['collection_items'],
             'r': cols['retention_policy'], 'w': cols['withdrawal_method'], 'th': cols['third_party_notice'],
             'now': datetime.utcnow()})


def downgrade() -> None:
    op.execute("DELETE FROM consent_policies WHERE policy_type IN ('terms_of_service', 'privacy') AND version = 'v4'")
