"""consent policies v2 text (정식 문구 초안)

Revision ID: f1d3b7a9c2e4
Revises: e4c9a2b7d815
Create Date: 2026-10-08 22:00:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1d3b7a9c2e4'
down_revision: Union[str, Sequence[str], None] = 'e4c9a2b7d815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 개인정보 보호법의 고지 항목(수집·이용 목적, 수집 항목, 보유·이용 기간, 동의 거부 권리와 불이익, 제3자 제공)을 기준으로 쓴 초안.
# 건강정보는 민감정보라 다른 동의와 따로 받는다. 서비스 공개 전에 법률 검토를 받아 확정해야 한다.
POLICIES = [
    {
        'policy_type': 'terms_of_service',
        'purpose_text': '파이온(PAEON)은 입력하신 건강정보로 고혈압 위험을 예측하고, 생활습관 챌린지를 추천·기록하는 서비스입니다. '
                        '이 서비스는 의료 행위나 진단이 아니며, 예측 결과는 참고용 선별 정보입니다. 정확한 진단과 치료는 의사와 상담해 주세요. '
                        '만 19세 이상만 가입할 수 있습니다.',
        'collection_items': '가입·로그인에 필요한 이메일, 비밀번호(암호화해 저장), 생년월일',
        'retention_policy': '회원 탈퇴 시 계정과 서비스 이용 기록을 삭제하고, 계정 식별자는 익명 처리합니다.',
        'withdrawal_method': '마이페이지의 "회원 탈퇴"에서 비밀번호로 재인증한 뒤 언제든지 탈퇴할 수 있습니다.',
        'third_party_notice': '서비스 제공 목적 외로 이용하지 않으며, 법령에 근거가 없는 한 제3자에게 제공하지 않습니다.',
    },
    {
        'policy_type': 'privacy',
        'purpose_text': '회원 가입·로그인, 본인 확인, 계정 관리, 서비스 이용 중 알림과 문의 응대를 위해 개인정보를 수집·이용합니다.',
        'collection_items': '이메일, 비밀번호(암호화), 생년월일, 성별(건강정보 입력 때 선택). 이름과 전화번호는 수집하지 않습니다.',
        'retention_policy': '회원 탈퇴 시까지 보유하고 탈퇴 즉시 삭제합니다. 법령에 따라 보관해야 하는 정보가 있으면 그 기간 동안만 분리해 보관합니다.',
        'withdrawal_method': '동의를 거부할 수 있으나, 필수 항목에 동의하지 않으면 회원 가입과 서비스 이용이 제한됩니다. 마이페이지에서 탈퇴할 수 있습니다.',
        'third_party_notice': '수집한 개인정보를 목적 외로 이용하거나 제3자에게 제공하지 않습니다. 서버 운영을 위한 인프라 이용 외에 처리를 맡기는 곳은 없습니다.',
    },
    {
        'policy_type': 'health_data',
        'purpose_text': '혈압 위험 예측과 생활습관 챌린지 추천·기록·4주 재평가에만 사용합니다. 건강정보는 개인정보 보호법상 민감정보이므로 다른 동의와 따로 받습니다.',
        'collection_items': '혈압(수축기·이완기), 키, 몸무게, 허리둘레, 흡연(일반·전자담배)·음주, 당뇨·고혈압 진단·치료 여부, 총콜레스테롤, HDL, 공복혈당(선택), '
                            '부모 고혈압 가족력, 생활습관 설문(나트륨 섭취 습관, 신체 활동·걸음 수, 외식·배달, 아침 식사, 혈압 측정 방법), '
                            '챌린지 수행 기록, 주간 혈압 기록, 캘린더 일기·사진·건강 할 일. '
                            '검진 결과지 사진 자동 입력 기능을 쓰는 경우에만 검진 결과지 사진(값을 읽는 데만 쓰고 저장하지 않습니다)',
        'retention_policy': '회원 탈퇴 시 모두 삭제합니다. 검진 결과지 사진은 숫자를 읽어 낸 즉시 폐기하며 서버에 저장하지 않습니다. 동의를 철회하면 새로운 입력과 예측이 중단되고, 이미 저장된 정보는 탈퇴 전까지 보관하며 "내 데이터 내려받기"로 받을 수 있습니다.',
        'withdrawal_method': '마이페이지의 "건강정보 처리 동의 철회"에서 언제든지 철회할 수 있습니다. 철회해도 계정은 유지되고, 다시 동의하면 이어서 이용할 수 있습니다. '
                             '동의를 거부할 수 있으나, 거부하면 위험 예측과 챌린지 기능을 이용할 수 없습니다.',
        'third_party_notice': '입력하신 건강정보는 위험 예측과 챌린지 추천에만 쓰며, 목적 외 이용이나 제3자 제공을 하지 않습니다. 예측 결과는 의료적 진단이 아닙니다. '
                            '검진 결과지 사진 자동 입력을 쓰면, 사진은 글자를 읽기 위해 외부 글자 인식·AI 서비스(네이버클라우드 Clova OCR, OpenAI)로 전송되며 사진 자체는 저장하지 않습니다. 사용하지 않으면 전송되지 않습니다.',
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.utcnow()
    for p in POLICIES:
        conn.execute(
            sa.text(
                "INSERT INTO consent_policies (policy_id, policy_type, version, purpose_text, collection_items, "
                "retention_policy, withdrawal_method, third_party_notice, published_at) "
                "VALUES (:id, :t, 'v2', :purpose, :items, :keep, :how, :third, :now)"
            ),
            {'id': str(uuid.uuid4()), 't': p['policy_type'], 'purpose': p['purpose_text'], 'items': p['collection_items'],
             'keep': p['retention_policy'], 'how': p['withdrawal_method'], 'third': p['third_party_notice'], 'now': now},
        )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM consent_policies WHERE version = 'v2'"))
