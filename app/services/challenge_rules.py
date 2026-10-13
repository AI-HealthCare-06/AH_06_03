"""챌린지 판정 규칙. DB를 모르는 순수 함수만 둔다 (테스트하기 쉽게).

기준: modeling/handoff/생활습관_입력_가이드.md
- §2.1 나트륨 지수 · §2.2 사용자 분류 · §3 추천·대체 · §5 매일 기록 · §6.3 정상 체중 범위
"""
from dataclasses import dataclass, field
from datetime import date

from app.services.challenge_catalog import (
    CATEGORY_NAMES,
    CYCLE_WEEKS,
    MISSIONS,
    REPLACEMENT_ORDER,
)

NA_QUESTIONS = [f"N{i}" for i in range(11)]  # N0 짠맛 습관 + N1~N10 식행동


# ---------------------------------------------------------------- §2.1 나트륨 지수
def _age_group(age: int) -> int:
    if age <= 29:
        return 1
    if age <= 39:
        return 2
    if age <= 49:
        return 3
    if age <= 59:
        return 4
    return 5


def sodium_index(sex: str, age: int, bmi: float, scores: dict[str, float]) -> dict:
    """N0~N10 점수가 모두 있을 때만 계산. 결과: sodium_est_mg, sodium_index, sodium_grade."""
    sex_value = 1 if sex == "male" else 2
    taste = scores["N0"]
    behavior = sum(scores[q] for q in NA_QUESTIONS[1:])
    est = (-191.9 - 705.2 * sex_value + 189.6 * _age_group(age) + 130.6 * bmi
           + 24.2 * taste + 18.5 * behavior)
    index = round(est / 20, 1)
    if index < 75:
        grade = "careful_low"
    elif index <= 100:
        grade = "very_moderate"
    elif index <= 150:
        grade = "moderate"
    elif index <= 250:
        grade = "careful_high"
    else:
        grade = "severe"
    return {"sodium_est_mg": round(est), "sodium_index": index, "sodium_grade": grade}


def sodium_applicable(age: int, htn_status: str | None, diabetes: bool | None) -> bool:
    """계산식을 만든 대상(고혈압·당뇨 없는 19–69세) 안에 있는가."""
    return 19 <= age <= 69 and htn_status in (None, "none") and not diabetes


# ---------------------------------------------------------------- §2.2 사용자 분류
@dataclass
class UserFacts:
    """판정에 쓰는 값. 없는 값은 None."""
    age: int
    sex: str  # male / female
    smoking: str | None = None
    ecig: str | None = None
    drink_freq: str | None = None
    drink_amount: str | None = None
    sbp: float | None = None
    dbp: float | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    htn_status: str | None = None
    diabetes: bool | None = None
    # 설문: 질문 코드 → 보기 코드 / 나트륨 문항 점수 / P2 걸음 수
    answers: dict[str, str] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    baseline_steps: int | None = None

    @property
    def bmi(self) -> float | None:
        if not self.height_cm or not self.weight_kg:
            return None
        return self.weight_kg / (self.height_cm / 100) ** 2


def classify(f: UserFacts) -> dict:
    """분류 코드 → True/False. 판정에 필요한 값이 없으면 그 코드는 넣지 않는다 (가이드 §2.2 마지막 줄).
    "sodium" 키에는 나트륨 지수 계산 결과(또는 not_applicable)를 넣는다."""
    c: dict = {}

    if f.smoking is not None:
        c["smoker"] = f.smoking == "current"
    if f.drink_freq is not None:
        drinks = f.drink_freq not in ("never_lifetime", "none_past_year")
        c["drinker"] = drinks and f.drink_amount in ("3_4", "5_6", "7_9", "10plus")
    if f.sbp is not None and f.dbp is not None:
        c["bp_160_100"] = f.sbp >= 160 or f.dbp >= 100
    if f.bmi is not None:
        c["overweight"] = f.bmi >= 25

    # 나트륨: 적용 범위 밖이면 설문과 무관하게 high_sodium
    if not sodium_applicable(f.age, f.htn_status, f.diabetes):
        c["sodium"] = {"sodium_grade": "not_applicable"}
        c["high_sodium"] = True
    elif f.bmi is not None and all(q in f.scores for q in NA_QUESTIONS):
        c["sodium"] = sodium_index(f.sex, f.age, f.bmi, f.scores)
        c["high_sodium"] = c["sodium"]["sodium_grade"] in ("careful_high", "severe")

    a = f.answers
    if "P1" in a:
        c["low_activity"] = a["P1"] != "150plus"
    if "P1" in a or f.baseline_steps is not None:
        c["has_baseline_steps"] = f.baseline_steps is not None
    if "E1" in a and "high_sodium" in c:
        c["frequent_eatout"] = a["E1"] in ("5_6_week", "1_day", "2plus_day") and c["high_sodium"]
    if "B1" in a:
        c["breakfast_skip"] = a["B1"] in ("3_4", "1_2", "0")
    return c


# ---------------------------------------------------------------- §3 추천·대체
def _category_ok(category: str, c: dict) -> bool | None:
    """카테고리 후보 조건. 설문을 안 해서 판정할 수 없으면 None."""
    key = {"SODIUM": "high_sodium", "ACTIVITY": "low_activity", "EATOUT": "frequent_eatout",
           "BREAKFAST": "breakfast_skip", "WEIGHT": "overweight"}[category]
    return c.get(key)


def _activity_main(c: dict) -> str:
    return "ACT-1" if c.get("has_baseline_steps") else "ACT-2"


REPRESENTATIVE = {"SODIUM": "NA-1", "EATOUT": "OUT-1", "BREAKFAST": "BRK-1"}


# 추천에서 빠진 사유의 종류 (화면에서 말투를 나눠 보여 줌)
KIND_DOING_WELL = "doing_well"    # 이미 잘하고 있어서 (대상이 아님)
KIND_NEED_INFO = "need_info"      # 정보를 더 입력하면 추천됨
KIND_NOT_ADVISED = "not_advised"  # 지금은 권하지 않음 (안전)


def _mission_excluded(code: str, c: dict) -> tuple[str, str] | None:
    """카테고리 조건은 맞지만 이 미션만 빠지는 경우의 (종류, 사유)."""
    if code == "ACT-1" and not c.get("has_baseline_steps"):
        return KIND_NEED_INFO, "평소 걸음 수를 입력하면 추천돼요"
    if code == "ACT-3" and c.get("bp_160_100"):
        return KIND_NOT_ADVISED, "혈압이 160/100 이상이면 버티기 운동은 권하지 않아요"
    return None


def _category_reason(category: str, c: dict, answers: dict) -> str:
    """카테고리가 후보에서 빠질 때 화면 문구 (가이드 §3.4 표)."""
    if category == "SODIUM":
        return "추정 나트륨 섭취가 많지 않아요"
    if category == "ACTIVITY":
        return "운동 권장량(주 150분)을 이미 채우고 있어요"
    if category == "EATOUT":
        if answers.get("E1") not in ("5_6_week", "1_day", "2plus_day"):
            return "외식·배달 횟수가 많지 않아요"
        return "추정 나트륨 섭취가 많지 않아요"
    if category == "BREAKFAST":
        return "아침 식사를 잘 챙기고 있어요"
    return "지금 체중은 관리 미션 대상이 아니에요"


@dataclass
class Recommendation:
    fixed: list[dict]  # [{"slot": 1, "code": "SMK-1" | None, "selection_type": "fixed"|"replacement", "from": "흡연"}]
    candidates: list[str]  # 선택 가능한 미션 코드
    completed: list[str]  # 이전 사이클에서 완료한 미션 (후보에 그대로 두고 "이어서 하기" 표시)
    excluded: list[dict]  # [{"code" | "category", "reason"}]
    survey_needed: list[str]  # 설문 미응답으로 판정 못 한 카테고리
    all_good: bool  # 후보 조건을 만족하는 미션이 없어 전체 목록을 보여주는 경우


def recommend(c: dict, answers: dict, completed_codes: set[str]) -> Recommendation:
    used: set[str] = set()
    used_categories: set[str] = set()

    def first_replacement() -> str | None:
        for category in REPLACEMENT_ORDER:
            if category in used_categories or not _category_ok(category, c):
                continue
            code = _activity_main(c) if category == "ACTIVITY" else REPRESENTATIVE[category]
            return code
        return None

    fixed = []
    for slot, (base, key, label) in enumerate(
        [("SMK-1", "smoker", "흡연"), ("ALC-1", "drinker", "음주")], start=1
    ):
        if c.get(key):
            code, selection = base, "fixed"
        else:
            code, selection = first_replacement(), "replacement"
        if code:
            used.add(code)
            used_categories.add(MISSIONS[code]["category"])
        fixed.append({"slot": slot, "code": code, "selection_type": selection, "from": label})

    candidates, excluded, survey_needed = [], [], []
    for category in ["SODIUM", "ACTIVITY", "EATOUT", "BREAKFAST", "WEIGHT"]:
        codes = [k for k, m in MISSIONS.items() if m["category"] == category and k not in used]
        ok = _category_ok(category, c)
        if ok is None:
            survey_needed.append(category)
            continue
        if not ok:
            if codes:
                excluded.append({"category": category, "kind": KIND_DOING_WELL,
                                 "reason": _category_reason(category, c, answers)})
            continue
        for code in codes:
            why = _mission_excluded(code, c)
            if why:
                excluded.append({"code": code, "kind": why[0], "reason": why[1]})
            else:
                candidates.append(code)

    all_good = False
    if not candidates:
        all_good = True
        fallback = ["NA-1", "NA-2", "ACT-1", "ACT-2", "ACT-3", "OUT-1", "BRK-1"]
        candidates = [
            code for code in fallback
            if code not in used and not _mission_excluded(code, c)
        ]

    shown = set(candidates) | {s["code"] for s in fixed if s["code"]}
    completed = [code for code in completed_codes if code in shown]
    return Recommendation(fixed, candidates, sorted(completed), excluded, survey_needed, all_good)


# ---------------------------------------------------------------- §5.2 매일 기록
def evaluate_log(code: str, answer: str | None, quantity: float | None, sex: str, target_config: dict | None) -> dict:
    """화면 응답 → 저장값 {status, quantity, limit_exceeded}. 잘못된 응답이면 ValueError."""
    cfg = target_config or {}

    if code == "ALC-1":
        if quantity is None or quantity < 0 or quantity != int(quantity):
            raise ValueError("마신 잔 수를 골라 주세요.")
        limit = cfg.get("male_max", 2) if sex == "male" else cfg.get("female_max", 1)
        q = min(int(quantity), limit + 1)  # 선택지는 "남 3잔 이상 / 여 2잔 이상"까지
        over = q > limit
        return {"status": "failed" if over else "completed", "quantity": q, "limit_exceeded": over}

    if code == "ACT-1":
        if quantity is None or quantity < 0 or quantity > 100_000:
            raise ValueError("걸음 수를 입력해 주세요.")
        ok = quantity >= cfg.get("steps_target", 0)
        return {"status": "completed" if ok else "failed", "quantity": int(quantity), "limit_exceeded": False}

    table = {
        "SMK-1": {"not_smoked": ("completed", None), "smoked": ("failed", "optional")},
        "NA-1": {"left": ("completed", None), "no_soup": ("completed", None), "finished": ("failed", None)},
        "NA-2": {"not_added": ("completed", None), "added": ("failed", None)},
        "ACT-2": {"none": ("failed", 0), "lt30": ("failed", 15), "30plus": ("completed", 30)},
        "ACT-3": {"all": ("completed", 4), "partial": ("failed", "1_3"), "none": ("failed", 0)},
        "OUT-1": {"requested": ("completed", None), "no_eatout": ("skipped", None), "not_requested": ("failed", None)},
        "BRK-1": {"ate": ("completed", None), "skipped": ("failed", None)},
        "WT-1": {"yes": ("completed", None), "no": ("failed", None)},
    }[code]
    if answer not in table:
        raise ValueError("선택지 중 하나를 골라 주세요.")
    status, q_rule = table[answer]

    if q_rule == "optional":  # 흡연: 몇 개비(선택)
        q = int(quantity) if quantity is not None and quantity >= 0 else None
    elif q_rule == "1_3":  # 벽 스쿼트 일부: 1~3번
        if quantity is None or int(quantity) not in (1, 2, 3):
            raise ValueError("몇 번 하셨는지 골라 주세요 (1–3번).")
        q = int(quantity)
    else:
        q = q_rule
    return {"status": status, "quantity": q, "limit_exceeded": False}


# ---------------------------------------------------------------- §5.1 달성률
def week_of(started_on: date, day: date) -> int:
    """사이클 시작일부터 7일 단위 주차 (1~4)."""
    return (day - started_on).days // 7 + 1


def progress(started_on: date, weekly_target: int, logs: list[tuple[date, str]]) -> dict:
    """주간 달성률 = 그 주 completed ÷ weekly_target (100% 상한). 사이클 달성률은 4주 평균."""
    done = [0] * CYCLE_WEEKS
    for log_date, status in logs:
        w = week_of(started_on, log_date)
        if status == "completed" and 1 <= w <= CYCLE_WEEKS:
            done[w - 1] += 1
    weeks = [
        {"week": i + 1, "completed": d, "target": weekly_target, "rate": min(d, weekly_target) / weekly_target}
        for i, d in enumerate(done)
    ]
    return {"weeks": weeks, "cycle_rate": sum(w["rate"] for w in weeks) / CYCLE_WEEKS}


def streak(logs: list[tuple[date, str]], today: date) -> int:
    """오늘(또는 어제)까지 completed가 이어진 날 수 (REQ-DASH-009)."""
    days = {d for d, s in logs if s == "completed"}
    cur = today if today in days else date.fromordinal(today.toordinal() - 1)
    n = 0
    while cur in days:
        n += 1
        cur = date.fromordinal(cur.toordinal() - 1)
    return n


# ---------------------------------------------------------------- §6.3 정상 범위
def normal_weight_range(height_cm: float) -> tuple[int, int]:
    """키 기준 정상 체중 = BMI 18.5~22.9 (kg, 정수 반올림)."""
    h = height_cm / 100
    return round(18.5 * h * h), round(22.9 * h * h)


def waist_limit(sex: str) -> int:
    """복부비만 기준 미만 (남 90 · 여 85cm)."""
    return 90 if sex == "male" else 85


def category_name(code: str) -> str:
    return CATEGORY_NAMES[MISSIONS[code]["category"]]
