"""챌린지 미션 목록과 카드 문구. 기준: modeling/handoff/생활습관_입력_가이드.md §3.1·§4·§4.1·§5.2

DB(challenge_categories·challenges·challenge_levels)에는 코드·이름·주간 목표·노출 여부·순서를 두고,
화면 문구(설명·근거·출처·안내)와 기록 선택지는 이 파일 하나에서만 관리한다.
"""

# 프로그램: 4주 사이클 × 3번 = 12주 (84일. 2차 멘토링 10/7, 팀 결정 10/8)
CYCLE_WEEKS = 4
CYCLE_DAYS = CYCLE_WEEKS * 7
PROGRAM_CYCLES = 3

# 사이클 종료 시 미션을 "완료"로 볼 4주 달성률 기준
MISSION_COMPLETE_RATE = 0.8

# 완료한 미션은 다음 사이클에서 빼지 않고 이어서 고를 수 있게 한다 (팀 결정 10/8, PRD REQ-CHAL-002 수정 예정)
# 근거: 습관 형성 중앙값 66일 (Lally 2010, 가이드 부록 B-21) > 사이클 28일
KEEP_GOING_MESSAGE = "지난 4주 목표를 달성했어요! 습관이 자리 잡는 데는 보통 두 달 정도 걸려요. 이어서 해 볼까요?"

# (코드, 이름, 화면 순서)
CATEGORIES = [
    ("SMOKING", "금연", 1),
    ("ALCOHOL", "절주", 2),
    ("SODIUM", "나트륨 줄이기", 3),
    ("ACTIVITY", "신체 활동", 4),
    ("EATOUT", "외식·배달 조절", 5),
    ("BREAKFAST", "아침 식사", 6),
    ("WEIGHT", "체중 관리", 7),
]
CATEGORY_NAMES = {code: name for code, name, _ in CATEGORIES}

# 고정 칸 대체 순서 (가이드 §3.3). 체중 관리는 선택 미션 전용
REPLACEMENT_ORDER = ["SODIUM", "ACTIVITY", "EATOUT", "BREAKFAST"]

# 선택 미션 영역 상단 안내 (가이드 §4.1)
SELECTABLE_NOTICE = "나트륨·신체 활동·외식·아침 미션은 위험도 계산에 쓰이지 않아요."

MISSIONS = {
    "SMK-1": {
        "category": "SMOKING", "name": "금연 유지 (일반담배·전자담배 모두)", "difficulty": "high",
        "weekly_target": 7, "proof_type": "self_record", "role": "fixed",
        "description": "4주 동안 일반담배를 피우지 않아요 (전자담배로 바꾸지 않아요)",
        "evidence": "하루 1개비만 피워도 관상동맥질환 위험이 크게 높아져요. 줄이기보다 끊는 것이 목표예요",
        "source": "BMJ 2018",
        "notice": "금연상담전화 1544-9030 · 가까운 보건소 금연클리닉에서 무료로 도움받을 수 있어요",
        "question": "오늘 일반담배나 전자담배를 피우셨나요?",
        "answers": [("not_smoked", "아니오"), ("smoked", "예")],
    },
    "ALC-1": {
        "category": "ALCOHOL", "name": "절주: 마신 날도 남 2잔 · 여 1잔 이하", "difficulty": "medium",
        "weekly_target": 7, "proof_type": "self_record", "role": "fixed",
        "target_config": {"male_max": 2, "female_max": 1},
        "description": "술을 마신 날에도 남성 2잔, 여성 1잔까지만 마셔요",
        "evidence": "한 번에 많이 마시던 분이 양을 줄이면 혈압이 내려간다는 연구가 있어요",
        "source": "Lancet Public Health 2017",
        "notice": "건강을 위해서는 마시지 않는 것이 가장 좋아요",
        "question": "오늘 술을 드셨나요?",
        "answers": [],  # 잔 수(quantity)로 기록. 남 0·1·2·3잔 이상 / 여 0·1·2잔 이상
    },
    "NA-1": {
        "category": "SODIUM", "name": "국물 남기기", "difficulty": "low",
        "weekly_target": 5, "proof_type": "self_record", "role": "selectable",
        "description": "국·찌개·탕·라면의 국물을 남겨요",
        "evidence": "소금을 하루 4–5g 줄이면 수축기 혈압이 평균 약 4mmHg 내려가요",
        "source": "Cochrane Database Syst Rev 2013",
        "notice": None,
        "question": "오늘 국·찌개·탕·라면의 국물을 남기셨나요?",
        "answers": [("left", "남겼어요"), ("no_soup", "국물 요리를 먹지 않았어요"), ("finished", "다 먹었어요")],
    },
    "NA-2": {
        "category": "SODIUM", "name": "음식에 소금·간장 더 넣지 않기", "difficulty": "medium",
        "weekly_target": 5, "proof_type": "self_record", "role": "selectable",
        "description": "식탁에서 소금이나 간장을 더 넣지 않아요",
        "evidence": "소금을 하루 4–5g 줄이면 수축기 혈압이 평균 약 4mmHg 내려가요",
        "source": "Cochrane Database Syst Rev 2013",
        "notice": None,
        "question": "오늘 음식에 소금이나 간장을 더 넣지 않으셨나요?",
        "answers": [("not_added", "넣지 않았어요"), ("added", "넣었어요")],
    },
    "ACT-1": {
        "category": "ACTIVITY", "name": "하루 걸음 수: 평소 + 2,000보", "difficulty": "low",
        "weekly_target": 5, "proof_type": "self_record", "role": "selectable",
        "description": "하루 걸음 수를 평소보다 2,000보 늘려요",
        "evidence": "하루 2,000보를 더 걸으면 수축기 혈압이 약 4mmHg 내려간다는 연구가 있어요",
        "source": "J Hum Hypertens 2018",
        "notice": "걸음 수는 휴대폰 건강 앱에 나온 숫자를 입력해요",
        "question": "오늘 걸음 수를 입력해 주세요",
        "answers": [],  # 걸음 수(quantity)로 기록
    },
    "ACT-2": {
        "category": "ACTIVITY", "name": "빠르게 걷기 30분", "difficulty": "medium",
        "weekly_target": 5, "proof_type": "self_record", "role": "selectable",
        "target_config": {"min_minutes": 30},
        "description": "숨이 조금 찰 정도로 30분 이상 빠르게 걸어요",
        "evidence": "빠르게 걷기를 꾸준히 하면 수축기 혈압이 평균 약 4mmHg 내려가요",
        "source": "Cochrane Database Syst Rev 2021",
        "notice": None,
        "question": "오늘 숨이 조금 찰 정도로 빠르게 걸은 시간은?",
        "answers": [("none", "안 걸었어요"), ("lt30", "30분 미만"), ("30plus", "30분 이상")],
    },
    "ACT-3": {
        "category": "ACTIVITY", "name": "벽 스쿼트 (2분 버티기 × 4번)", "difficulty": "high",
        "weekly_target": 3, "proof_type": "self_record", "role": "selectable",
        "target_config": {"sets": 4, "seconds_per_set": 120},
        "description": "벽에 등을 대고 무릎을 굽힌 자세로 2분 버티기를 4번 해요 (사이 2분 휴식)",
        "evidence": "벽 스쿼트 같은 버티기 운동은 혈압을 낮추는 효과가 큰 운동으로 알려져 있어요",
        "source": "Br J Sports Med 2023",
        "notice": "운동 중 숨을 참지 마세요. 어지럽거나 가슴이 아프면 바로 멈추세요. 처음에는 무릎을 조금만 굽혀요",
        "question": "오늘 벽 스쿼트를 하셨나요?",
        "answers": [("all", "4번 모두 했어요"), ("partial", "일부만 했어요"), ("none", "안 했어요")],
    },
    "OUT-1": {
        "category": "EATOUT", "name": '외식·배달 때 "싱겁게" 요청하기', "difficulty": "medium",
        "weekly_target": 3, "proof_type": "self_record", "role": "selectable",
        "description": '외식·배달 주문 때 "싱겁게 해 주세요"라고 요청해요',
        "evidence": "외식 음식의 소금을 줄이는 방법이에요. 소금을 하루 4–5g 줄이면 수축기 혈압이 평균 약 4mmHg 내려가요",
        "source": "Cochrane Database Syst Rev 2013",
        "notice": "배달 앱 요청사항 칸에 적어도 돼요",
        "question": '오늘 외식·배달 때 "싱겁게" 요청하셨나요?',
        "answers": [("requested", "요청했어요"), ("no_eatout", "외식·배달을 하지 않았어요"),
                    ("not_requested", "요청하지 않았어요")],
    },
    "BRK-1": {
        "category": "BREAKFAST", "name": "아침 식사 하기", "difficulty": "low",
        "weekly_target": 5, "proof_type": "self_record", "role": "selectable",
        "description": "아침 식사를 해요",
        "evidence": "아침을 거르는 사람은 고혈압이 있을 가능성이 약 1.2배 높다는 연구가 있어요. 정부 식생활지침도 아침 식사를 권장해요",
        "source": "Int J Hypertens 2022 · 「한국인을 위한 식생활지침」 2021",
        "notice": "커피·음료만 마신 경우는 제외해요",
        "question": "오늘 아침 식사를 하셨나요?",
        "answers": [("ate", "했어요"), ("skipped", "안 했어요")],
    },
    "WT-1": {
        "category": "WEIGHT", "name": "끼니마다 밥 2/3공기", "difficulty": "medium",
        "weekly_target": 5, "proof_type": "self_record", "role": "selectable",
        "description": "끼니마다 밥을 2/3공기만 먹어요. 4주마다 몸무게·허리둘레를 다시 재요",
        "evidence": "체중을 1kg 줄일 때마다 수축기 혈압이 약 1mmHg 내려가요",
        "source": "Hypertension 2003",
        "notice": "줄인 밥 대신 다른 음식을 더 먹지 않아요",
        "question": "오늘 끼니마다 밥을 2/3공기 이하로 드셨나요?",
        "answers": [("yes", "네"), ("no", "아니요")],
    },
}
