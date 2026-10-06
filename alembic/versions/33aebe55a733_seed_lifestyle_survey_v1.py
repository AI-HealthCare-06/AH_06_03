"""seed lifestyle survey v1

Revision ID: 33aebe55a733
Revises: 5768d368f630
Create Date: 2026-10-02 14:38:19.291881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime

VERSION_ID = "01a0f900-0000-7000-8000-000000000001"

# (질문 코드, 질문 문장, 보기 목록[(보기 코드, 보기 문장, 모델 값)])
QUESTIONS = [
    ("BREAKFAST", "최근 1년 동안 아침 식사를 일주일에 몇 번 하셨나요?", [
        ("5_7", "주 5~7회", "5_7"),
        ("3_4", "주 3~4회", "3_4"),
        ("1_2", "주 1~2회", "1_2"),
        ("0", "거의 안 함 (주 0회)", "0"),
    ]),
    ("EATOUT", "최근 1년 동안 외식이나 배달·포장 음식을 평균 얼마나 자주 드셨나요?", [
        ("2plus_per_day", "하루 2회 이상", "2plus_per_day"),
        ("1_per_day", "하루 1회", "1_per_day"),
        ("5_6_per_week", "주 5~6회", "5_6_per_week"),
        ("3_4_per_week", "주 3~4회", "3_4_per_week"),
        ("1_2_per_week", "주 1~2회", "1_2_per_week"),
        ("1_3_per_month", "월 1~3회", "1_3_per_month"),
        ("lt_monthly", "거의 안 함 (월 1회 미만)", "lt_monthly"),
    ]),
    ("AEROBIC", "숨이 찰 정도의 운동을 일주일에 150분 이상(또는 아주 힘든 운동을 75분 이상) 하시나요?", [
        ("yes", "예", "1"),
        ("no", "아니요", "0"),
    ]),
]


# revision identifiers, used by Alembic.
revision: str = '33aebe55a733'
down_revision: Union[str, Sequence[str], None] = '5768d368f630'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    versions = sa.table("survey_versions",
        sa.column("survey_version_id", sa.CHAR(36)), sa.column("survey_type", sa.String),
        sa.column("version", sa.String), sa.column("active_from", sa.DateTime))
    questions = sa.table("survey_questions",
        sa.column("question_id", sa.CHAR(36)), sa.column("survey_version_id", sa.CHAR(36)),
        sa.column("question_code", sa.String), sa.column("question_text", sa.Text),
        sa.column("display_order", sa.Integer), sa.column("required", sa.Boolean))
    options = sa.table("survey_options",
        sa.column("option_id", sa.CHAR(36)), sa.column("question_id", sa.CHAR(36)),
        sa.column("option_code", sa.String), sa.column("option_text", sa.String),
        sa.column("model_value_code", sa.String), sa.column("display_order", sa.Integer))

    op.bulk_insert(versions, [{
        "survey_version_id": VERSION_ID,
        "survey_type": "initial_lifestyle",
        "version": "v1",
        "active_from": datetime(2026, 10, 1),
    }])

    q_rows, o_rows = [], []
    for q_no, (q_code, q_text, opts) in enumerate(QUESTIONS, start=1):
        q_id = f"01a0f900-0000-7000-8001-{q_no:012d}"
        q_rows.append({"question_id": q_id, "survey_version_id": VERSION_ID, "question_code": q_code,
                       "question_text": q_text, "display_order": q_no, "required": True})
        for o_no, (o_code, o_text, model_value) in enumerate(opts, start=1):
            o_rows.append({"option_id": f"01a0f900-0000-7000-8002-{q_no:04d}{o_no:08d}", "question_id": q_id,
                           "option_code": o_code, "option_text": o_text,
                           "model_value_code": model_value, "display_order": o_no})
    op.bulk_insert(questions, q_rows)
    op.bulk_insert(options, o_rows)


def downgrade() -> None:
    # 설문지를 지우면 질문·보기도 같이 지워진다 (ondelete="CASCADE")
    op.execute(f"DELETE FROM survey_versions WHERE survey_version_id = '{VERSION_ID}'")
