"""consent policy health_data v4 (철회 시 삭제 범위)

Revision ID: 729ceb6de7e2
Revises: 980618918c12
Create Date: 2026-10-13 13:07:59.398543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '729ceb6de7e2'
down_revision: Union[str, Sequence[str], None] = '980618918c12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PURPOSE = "혈압 위험 분석과 생활습관 챌린지 추천·기록·4주 재평가에만 사용합니다. 건강정보는 개인정보 보호법상 민감정보이므로 다른 동의와 따로 받습니다."
ITEMS = "성별, 혈압(수축기·이완기), 키, 몸무게, 허리둘레, 흡연(일반·전자담배)·음주, 당뇨·고혈압 진단·치료 여부, 총콜레스테롤, 공복혈당(선택), 부모 고혈압 가족력, 대상 확인 답(나이대, 심장 혈관 질환(협심증·심근경색 등) 진단 여부, 응급 증상 여부), 생활습관 설문(나트륨 섭취 습관, 신체 활동·걸음 수, 외식·배달, 아침 식사), 챌린지 수행 기록, 캘린더 일기·사진·건강 할 일."
RETENTION = "회원 탈퇴 시 모두 삭제합니다. 동의를 철회하면 건강기록·설문·분석·챌린지·캘린더·대상 확인·성별이 삭제됩니다. 서버 백업 사본에는 최대 일주일 더 남을 수 있습니다."
WITHDRAWAL = '마이페이지의 "건강정보 처리 동의 철회"에서 언제든지 철회할 수 있습니다. 철회해도 계정은 유지되며, 다시 동의하면 처음부터 다시 입력해 이용할 수 있습니다. 동의를 거부할 수 있으나, 거부하면 위험 분석과 챌린지 기능을 이용할 수 없습니다.'
THIRD = "입력하신 건강정보는 위험 분석과 챌린지 추천에만 쓰며, 목적 외 이용이나 제3자 제공을 하지 않습니다. 분석 결과는 의료적 진단이 아닙니다."


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text(
        "SELECT 1 FROM consent_policies WHERE policy_type = 'health_data' AND version = 'v4'")).first():
        return
    conn.execute(sa.text("""
        INSERT INTO consent_policies
            (policy_id, policy_type, version, purpose_text, collection_items,
             retention_policy, withdrawal_method, third_party_notice, published_at)
        VALUES (UUID(), 'health_data', 'v4', :purpose, :items, :retention, :withdrawal, :third, NOW())
    """), {"purpose": PURPOSE, "items": ITEMS, "retention": RETENTION,
           "withdrawal": WITHDRAWAL, "third": THIRD})


def downgrade() -> None:
    op.execute("DELETE FROM consent_policies WHERE policy_type = 'health_data' AND version = 'v4'")