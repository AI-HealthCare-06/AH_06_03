"""건강정보 동의 문구 v3 (HDL·혈압 측정 방법·주간 혈압 기록 제외) + 설문의 혈압 측정 방법 문항 삭제

HDL은 두 모델 모두 쓰지 않고, 혈압 측정 방법 문항은 설문에서 없애기로 했다(테스트 점검 #2·#4).
이제 수집하지 않는 항목이므로 동의 문구에서도 뺀다.

Revision ID: b7e2d4f6a891
Revises: a8c3e5f7b219
Create Date: 2026-10-09 09:00:00.000000

"""
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2d4f6a891'
down_revision: Union[str, Sequence[str], None] = 'a8c3e5f7b219'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 건강정보 수집 항목 문구에서 뺄 부분 (v2 문구 기준)
ITEM_EDITS = [
    ('총콜레스테롤, HDL, 공복혈당', '총콜레스테롤, 공복혈당'),
    ('아침 식사, 혈압 측정 방법)', '아침 식사)'),
    ('챌린지 수행 기록, 주간 혈압 기록, ', '챌린지 수행 기록, '),   # 혈압은 4주마다 측정으로 바뀌어 주간 기록은 받지 않는다
]

BP_CODE = 'BP_MEASURE_METHOD'
BP_TEXT = '혈압을 주 1회 재실 수 있나요?'
BP_OPTIONS = [('home_monitor', '집에 혈압계가 있다'), ('pharmacy_health_center', '약국·보건소를 이용할 수 있다'), ('difficult', '어렵다')]

SQL_BP_QUESTION_IDS = "SELECT question_id FROM survey_questions WHERE question_code = :code"
SQL_DEL_RESPONSES = "DELETE FROM survey_responses WHERE question_id IN (SELECT question_id FROM survey_questions WHERE question_code = :code)"
SQL_DEL_OPTIONS = "DELETE FROM survey_options WHERE question_id IN (SELECT question_id FROM survey_questions WHERE question_code = :code)"
SQL_DEL_QUESTIONS = "DELETE FROM survey_questions WHERE question_code = :code"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 건강정보 동의 문구 v3: v2에서 HDL·혈압 측정 방법만 뺀다 (이미 v3가 있으면 건너뜀)
    has_v3 = conn.execute(sa.text(
        "SELECT 1 FROM consent_policies WHERE policy_type = 'health_data' AND version = 'v3'")).first()
    v2 = conn.execute(sa.text(
        "SELECT purpose_text, collection_items, retention_policy, withdrawal_method, third_party_notice "
        "FROM consent_policies WHERE policy_type = 'health_data' AND version = 'v2'")).mappings().first()
    if v2 is not None and not has_v3:
        items = v2['collection_items']
        for old, new in ITEM_EDITS:
            if old not in items:
                raise RuntimeError(f"v2 수집 항목 문구에서 찾지 못했습니다: {old}")
            items = items.replace(old, new)
        conn.execute(
            sa.text(
                "INSERT INTO consent_policies (policy_id, policy_type, version, purpose_text, collection_items, "
                "retention_policy, withdrawal_method, third_party_notice, published_at) "
                "VALUES (:id, 'health_data', 'v3', :purpose, :items, :keep, :how, :third, :now)"
            ),
            {'id': str(uuid.uuid4()), 'purpose': v2['purpose_text'], 'items': items, 'keep': v2['retention_policy'],
             'how': v2['withdrawal_method'], 'third': v2['third_party_notice'], 'now': datetime.utcnow()},
        )

    # 2. 설문에서 혈압 측정 방법 문항 삭제. 답(응답)이 보기·문항을 가리키므로 응답 → 보기 → 문항 순서로 지운다.
    for sql in (SQL_DEL_RESPONSES, SQL_DEL_OPTIONS, SQL_DEL_QUESTIONS):
        conn.execute(sa.text(sql), {'code': BP_CODE})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM consent_policies WHERE policy_type = 'health_data' AND version = 'v3'"))

    # 문항만 되살린다 (지운 응답은 복구할 수 없다). 처음 설문 v2에만 있던 문항이다.
    versions = conn.execute(sa.text(
        "SELECT survey_version_id FROM survey_versions WHERE survey_type = 'initial_lifestyle' AND version = 'v2'")).all()
    for (version_id,) in versions:
        exists = conn.execute(sa.text(
            "SELECT 1 FROM survey_questions WHERE survey_version_id = :v AND question_code = :code"),
            {'v': version_id, 'code': BP_CODE}).first()
        if exists:
            continue
        order = conn.execute(sa.text(
            "SELECT COALESCE(MAX(display_order), 0) + 1 FROM survey_questions WHERE survey_version_id = :v"),
            {'v': version_id}).scalar()
        qid = str(uuid.uuid4())
        conn.execute(sa.text(
            "INSERT INTO survey_questions (question_id, survey_version_id, question_code, question_text, "
            "display_order, required, answer_type) VALUES (:q, :v, :code, :text, :o, 0, 'single_select')"),
            {'q': qid, 'v': version_id, 'code': BP_CODE, 'text': BP_TEXT, 'o': order})
        for i, (code, text) in enumerate(BP_OPTIONS, start=1):
            conn.execute(sa.text(
                "INSERT INTO survey_options (option_id, question_id, option_code, option_text, display_order) "
                "VALUES (:id, :q, :code, :text, :o)"),
                {'id': str(uuid.uuid4()), 'q': qid, 'code': code, 'text': text, 'o': i})
