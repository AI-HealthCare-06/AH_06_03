"""seed lifestyle survey v2 and close v1

Revision ID: 021521eb83c3
Revises: c9429b68803a
Create Date: 2026-10-08 12:24:43.056040

"""
from datetime import datetime
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "021521eb83c3"
down_revision: Union[str, Sequence[str], None] = "c9429b68803a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

V1_ID = "01a0f900-0000-7000-8000-000000000001"
VERSIONS = [  # (번호, 종류, 4주용인가)
    ("01a0f900-0000-7002-8000-000000000002", "initial_lifestyle", False),
    ("01a0f900-0000-7003-8000-000000000003", "interim_lifestyle", True),
]

AGREE = ["never", "slightly", "moderate", "much", "very"]
AGREE_TEXT = ["전혀 그렇지 않다", "약간 그렇다", "보통이다", "많이 그렇다", "매우 그렇다"]
FREQ = ["le3_month", "1_2_week", "3_6_week", "1_day", "2_3_day"]
FREQ_TEXT = ["월 3회 이하", "주 1–2회", "주 3–6회", "하루 1회", "하루 2–3회"]
UP, DOWN = [2, 4, 6, 8, 10], [10, 8, 6, 4, 2]


def _opts(codes, texts, scores=None):
    return [(c, t, (scores[i] if scores else None)) for i, (c, t) in enumerate(zip(codes, texts))]


# (질문 코드, 질문 문장, 숫자 질문 범위 or None, 보기 목록, 4주용에도 넣나)
QUESTIONS = [
    ("N0", "평소 음식을 어떻게 드시나요?", None,
     _opts(["bland", "slightly_bland", "normal", "slightly_salty", "salty"],
           ["싱겁게", "약간 싱겁게", "보통", "약간 짜게", "짜게"], [10, 20, 30, 40, 50]), True),
    ("N1", "국수·라면의 국물을 다 마신다", None, _opts(AGREE, AGREE_TEXT, UP), True),
    ("N2", "음식에 소금이나 간장을 습관적으로 더 넣는다", None, _opts(AGREE, AGREE_TEXT, UP), True),
    ("N3", "회·전·튀김에 간장이나 고추장을 많이 찍어 먹는다", None, _opts(AGREE, AGREE_TEXT, UP), True),
    ("N4", "가공식품을 살 때 나트륨 함량을 확인한다", None, _opts(AGREE, AGREE_TEXT, DOWN), True),
    ("N5", "외식할 때 싱겁게 해달라고 요청한다", None, _opts(AGREE, AGREE_TEXT, DOWN), True),
    ("N6", "국이나 찌개를 얼마나 자주 드시나요?", None, _opts(FREQ, FREQ_TEXT, UP), True),
    ("N7", "김치를 얼마나 자주 드시나요?", None, _opts(FREQ, FREQ_TEXT, UP), True),
    ("N8", "자반(소금에 절인 생선)을 반찬으로 얼마나 자주 드시나요?", None, _opts(FREQ, FREQ_TEXT, UP), True),
    ("N9", "견과류를 간식으로 얼마나 자주 드시나요?", None, _opts(FREQ, FREQ_TEXT, DOWN), True),
    ("N10", "과일을 얼마나 자주 드시나요?", None, _opts(FREQ, FREQ_TEXT, DOWN), True),
    ("P1", "평소 일주일 동안 숨이 조금 찰 정도의 운동을 모두 합쳐 얼마나 하시나요? "
           "(빠르게 걷기, 자전거, 수영, 등산, 헬스 등. 출퇴근·장보기 때 10분 이상 계속 걷는 것도 포함) "
           "(달리기처럼 숨이 많이 차는 운동은 시간을 2배로 쳐서 합쳐 주세요)", None,
     _opts(["none", "lt60", "60_149", "150plus"],
           ["거의 안 함", "1시간 미만", "1시간 이상 ~ 2시간 30분 미만", "2시간 30분 이상"]), True),
    ("P2", "휴대폰 건강 앱(아이폰 '건강', 갤럭시 '삼성 헬스')에 나온 최근 7일 하루 평균 걸음 수를 입력해 주세요.",
     (0, 50000), [], True),
    ("E1", "평소 일주일에 집에서 만든 음식이 아닌 식사(식당·배달·포장·구내식당 등)를 몇 번 하시나요?", None,
     _opts(["rare", "1_2_week", "3_4_week", "5_6_week", "1_day", "2plus_day"],
           ["거의 안 함", "주 1–2회", "주 3–4회", "주 5–6회", "하루 1회", "하루 2회 이상"]), True),
    ("B1", "평소 일주일에 아침 식사를 몇 번 하시나요? (밥·빵·시리얼·떡 등 식사로 먹은 것. 커피·음료만 마신 경우는 제외)", None,
     _opts(["5_7", "3_4", "1_2", "0"], ["주 5–7회", "주 3–4회", "주 1–2회", "거의 안 함"]), True),
    ("BP_MEASURE_METHOD", "혈압을 주 1회 재실 수 있나요?", None,
     _opts(["home_monitor", "pharmacy_health_center", "difficult"],
           ["집에 혈압계가 있다", "약국·보건소를 이용할 수 있다", "어렵다"]), False),
]


def _interim_text(code: str, text: str) -> str:
    """4주용 문구 (명세 §6.1): 질문 앞에 '최근 4주 동안'. N1~N5는 문장형이라 '최근 4주 동안,'으로."""
    if code in {"N1", "N2", "N3", "N4", "N5"}:
        return "최근 4주 동안, " + text
    return "최근 4주 동안 " + text


def upgrade() -> None:
    versions = sa.table("survey_versions",
        sa.column("survey_version_id", sa.CHAR(36)), sa.column("survey_type", sa.String),
        sa.column("version", sa.String), sa.column("active_from", sa.DateTime))
    questions = sa.table("survey_questions",
        sa.column("question_id", sa.CHAR(36)), sa.column("survey_version_id", sa.CHAR(36)),
        sa.column("question_code", sa.String), sa.column("question_text", sa.Text),
        sa.column("display_order", sa.Integer), sa.column("required", sa.Boolean),
        sa.column("answer_type", sa.String), sa.column("num_min", sa.Integer), sa.column("num_max", sa.Integer))
    options = sa.table("survey_options",
        sa.column("option_id", sa.CHAR(36)), sa.column("question_id", sa.CHAR(36)),
        sa.column("option_code", sa.String), sa.column("option_text", sa.String),
        sa.column("numeric_score", sa.Numeric), sa.column("model_value_code", sa.String),
        sa.column("display_order", sa.Integer))

    # 1. v1 닫기 (지금 쓰는 설문지가 v2가 되게)
    op.execute(f"UPDATE survey_versions SET active_to = '2026-10-08 00:00:00' WHERE survey_version_id = '{V1_ID}'")

    v_rows, q_rows, o_rows = [], [], []
    for v_no, (v_id, s_type, is_interim) in enumerate(VERSIONS, start=2):
        v_rows.append({"survey_version_id": v_id, "survey_type": s_type, "version": "v2",
                       "active_from": datetime(2026, 10, 8)})
        order = 0
        for q_code, q_text, num_range, opts, in_interim in QUESTIONS:
            if is_interim and not in_interim:
                continue
            order += 1
            q_id = f"01a0f900-0000-7{v_no:03d}-8001-{order:012d}"
            q_rows.append({
                "question_id": q_id, "survey_version_id": v_id, "question_code": q_code,
                "question_text": _interim_text(q_code, q_text) if is_interim else q_text,
                "display_order": order, "required": False,
                "answer_type": "number" if num_range else "single_select",
                "num_min": num_range[0] if num_range else None,
                "num_max": num_range[1] if num_range else None,
            })
            for o_no, (o_code, o_text, score) in enumerate(opts, start=1):
                o_rows.append({
                    "option_id": f"01a0f900-0000-7{v_no:03d}-8002-{order:04d}{o_no:08d}",
                    "question_id": q_id, "option_code": o_code, "option_text": o_text,
                    "numeric_score": score, "model_value_code": None, "display_order": o_no,
                })

    op.bulk_insert(versions, v_rows)
    op.bulk_insert(questions, q_rows)
    op.bulk_insert(options, o_rows)


def downgrade() -> None:
    for v_id, _, _ in VERSIONS:
        op.execute(f"DELETE FROM survey_versions WHERE survey_version_id = '{v_id}'")
    op.execute(f"UPDATE survey_versions SET active_to = NULL WHERE survey_version_id = '{V1_ID}'")
