"""create consent tables and seed draft policies

Revision ID: e4c9a2b7d815
Revises: d3b8f1a4c6e7
Create Date: 2026-10-08 20:00:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4c9a2b7d815'
down_revision: Union[str, Sequence[str], None] = 'd3b8f1a4c6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 초안 문구: 가입 화면 체크박스 문구 기준. 정식 약관 문구는 팀에서 확정해 새 버전(v2)으로 넣는다.
POLICIES = [
    ('terms_of_service', '서비스 이용약관 동의', '이름·전화번호는 받지 않고 이메일·생년월일·성별만 수집합니다.', '회원 탈퇴 시 삭제', '마이페이지에서 회원 탈퇴', '목적 외 이용·제3자 제공 없음'),
    ('privacy', '개인정보 수집·이용 동의 (서비스 제공, 계정 관리)', '이메일, 생년월일, 성별', '회원 탈퇴 시 삭제 (익명화된 계정 기록 제외)', '마이페이지에서 회원 탈퇴', '목적 외 이용·제3자 제공 없음'),
    ('health_data', '건강정보 수집·이용 동의 (혈압 위험 예측, 챌린지 추천)', '혈압, 키, 몸무게, 허리둘레, 흡연·음주, 질환 이력, 콜레스테롤, 생활습관 설문', '회원 탈퇴 시 삭제', '마이페이지에서 동의 철회 (계정은 유지, 건강정보 기능은 중단)', '입력한 건강정보는 예측과 챌린지 추천에만 쓰고 제3자에게 제공하지 않습니다.'),
]


def upgrade() -> None:
    policies = op.create_table('consent_policies',
    sa.Column('policy_id', sa.CHAR(length=36), nullable=False),
    sa.Column('policy_type', sa.Enum('terms_of_service', 'privacy', 'health_data', 'guardian', name='policy_type'), nullable=False),
    sa.Column('version', sa.String(length=30), nullable=False),
    sa.Column('purpose_text', sa.Text(), nullable=False),
    sa.Column('collection_items', sa.Text(), nullable=False),
    sa.Column('retention_policy', sa.Text(), nullable=False),
    sa.Column('withdrawal_method', sa.Text(), nullable=False),
    sa.Column('third_party_notice', sa.Text(), nullable=False),
    sa.Column('published_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('policy_id'),
    sa.UniqueConstraint('policy_type', 'version')
    )
    op.create_table('user_consents',
    sa.Column('user_consent_id', sa.CHAR(length=36), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('policy_id', sa.CHAR(length=36), nullable=False),
    sa.Column('status', sa.Enum('agreed', 'withdrawn', name='consent_status'), nullable=False),
    sa.Column('consented_at', sa.DateTime(), nullable=False),
    sa.Column('withdrawn_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['policy_id'], ['consent_policies.policy_id']),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_consent_id')
    )
    op.create_index(op.f('ix_user_consents_user_id'), 'user_consents', ['user_id'], unique=False)
    now = datetime.utcnow()
    op.bulk_insert(policies, [
        {'policy_id': str(uuid.uuid4()), 'policy_type': t, 'version': 'v1', 'purpose_text': purpose, 'collection_items': items,
         'retention_policy': keep, 'withdrawal_method': how, 'third_party_notice': third, 'published_at': now}
        for t, purpose, items, keep, how, third in POLICIES])


def downgrade() -> None:
    op.drop_table('user_consents')
    op.drop_table('consent_policies')
