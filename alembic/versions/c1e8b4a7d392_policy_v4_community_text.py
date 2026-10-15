"""동의 문구 v4에 커뮤니티·파이·배지·파티·비회원 문의를 반영하고 이메일 문의(구글 Gmail) 안내를 뺀다

시행일 전이라 v4 문구를 제자리에서 고친다(새 버전을 만들지 않는다). 화면의 assets/policies.js 내장 문구도 같은 규칙으로 맞춘다.
이 문구를 이미 보고 동의한 사람의 동의 기록(정책 번호·버전)은 그대로 남는다.

Revision ID: c1e8b4a7d392
Revises: a9c4e7b2d1f6
Create Date: 2026-10-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c1e8b4a7d392'
down_revision: Union[str, Sequence[str], None] = 'a9c4e7b2d1f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (정책 종류, 칸) → [(바꿀 문구, 새 문구)]
EDITS = {
    ('terms_of_service', 'purpose_text'): [
        ('생활습관 챌린지를 추천·기록하는 서비스입니다.',
         '생활습관 챌린지를 추천·기록하는 서비스이며, 닉네임으로 참여하는 커뮤니티와 공통 챌린지, 파티, 파이·배지도 제공합니다.'),
    ],
    ('terms_of_service', 'retention_policy'): [
        ('계정과 서비스 이용 기록, 게시물을 삭제', '계정과 서비스 이용 기록, 게시물, 파이·배지·파티 기록을 삭제'),
    ],
    ('privacy', 'collection_items'): [
        ('커뮤니티에 올린 게시글·댓글.',
         '커뮤니티 닉네임·게시글·댓글·좋아요·신고·캐릭터 설정, 파이·배지, 공통 챌린지 참여·인증 기록, 파티 정보, '
         '비회원 문의(조회 번호와 IP는 해시 값으로만 저장).'),
    ],
    ('privacy', 'retention_policy'): [
        ('1:1 문의는 탈퇴 시 삭제합니다.',
         '1:1 문의와 닉네임·게시글·댓글·캐릭터는 탈퇴 시 삭제하고, 비회원 문의는 30일 뒤 삭제합니다. '
         '파이·배지·파티·공통 챌린지 기록은 탈퇴하거나 건강정보 동의를 철회하면 삭제합니다.'),
    ],
    ('privacy', 'third_party_notice'): [
        ('서버 운영은 AWS 서울 리전에 맡기고, 로그인·가입이 안 될 때 이메일로 보내는 문의는 구글(Gmail)이 처리합니다(국외 이전, 개인정보 처리방침 제5·6조).',
         '서버 운영은 AWS 서울 리전에 맡기며, 문의도 서비스 안에서만 처리해 국외로 이전하지 않습니다(개인정보 처리방침 제5·6조).'),
    ],
    ('health_data', 'collection_items'): [
        ('챌린지 수행 기록,', '챌린지 수행 기록(공통 챌린지 인증과 걸음 수 포함),'),
    ],
    ('health_data', 'retention_policy'): [
        ('동의를 철회하면 건강기록·설문·분석·챌린지·캘린더·대상 확인·성별이 삭제됩니다.',
         '동의를 철회하면 건강기록·설문·분석·챌린지·캘린더·대상 확인·성별과 파이·배지·파티·공통 챌린지 기록이 삭제됩니다'
         '(계정, 닉네임, 게시글, 댓글, 캐릭터는 유지됩니다).'),
    ],
    ('health_data', 'withdrawal_method'): [
        ('철회해도 계정은 유지되며,', '철회해도 계정과 닉네임·게시글·댓글·캐릭터는 유지되며,'),
    ],
}
COLUMNS = {'purpose_text', 'collection_items', 'retention_policy', 'withdrawal_method', 'third_party_notice'}


def _swap(pairs_by_direction) -> None:
    conn = op.get_bind()
    for (ptype, col), pairs in EDITS.items():
        assert col in COLUMNS
        row = conn.execute(sa.text(f"SELECT {col} FROM consent_policies WHERE policy_type = :t AND version = 'v4'"),
                           {'t': ptype}).first()
        if row is None:
            continue
        text = row[0]
        for old, new in pairs:
            a, b = pairs_by_direction(old, new)
            if a in text:                      # 이미 바뀐 문구면 건너뛴다 (두 번 실행돼도 안전)
                text = text.replace(a, b)
        conn.execute(sa.text(f"UPDATE consent_policies SET {col} = :v WHERE policy_type = :t AND version = 'v4'"),
                     {'v': text, 't': ptype})


def upgrade() -> None:
    _swap(lambda old, new: (old, new))


def downgrade() -> None:
    _swap(lambda old, new: (new, old))
