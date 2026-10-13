"""챌린지 판정 규칙 테스트. 기준: modeling/handoff/생활습관_입력_가이드.md §2·§3·§5"""
from datetime import date, timedelta

import pytest

from app.services import challenge_rules as r

LOW_NA = {q: 2.0 for q in r.NA_QUESTIONS} | {"N0": 10.0}   # 싱겁게, 식행동 최저
LOW = dict(sex="female", age=30)  # LOW_NA가 "적정"으로 나오는 사람 (남성 40대는 최저 응답도 "많음")
HIGH_NA = {q: 10.0 for q in r.NA_QUESTIONS} | {"N0": 50.0}  # 짜게, 식행동 최고


def facts(**kw):
    base = dict(age=45, sex="male", smoking="never", drink_freq="never_lifetime", drink_amount=None,
                sbp=125, dbp=80, height_cm=175, weight_kg=70, htn_status="none", diabetes=False)
    return r.UserFacts(**(base | kw))


# ---------------------------------------------------------------- §2.1 나트륨 지수
def test_sodium_index_formula():
    # 남(1), 45세(3), BMI 25, 짠맛 30, 식행동합 60
    scores = {"N0": 30.0} | {f"N{i}": 6.0 for i in range(1, 11)}
    out = r.sodium_index("male", 45, 25.0, scores)
    est = -191.9 - 705.2 * 1 + 189.6 * 3 + 130.6 * 25 + 24.2 * 30 + 18.5 * 60
    assert out["sodium_est_mg"] == round(est)
    assert out["sodium_index"] == round(est / 20, 1)
    assert out["sodium_grade"] == "careful_high"  # 4,839mg → 지수 242


@pytest.mark.parametrize("age,htn,dm,ok", [
    (45, "none", False, True), (70, "none", False, False), (45, "treated", False, False), (45, "none", True, False),
])
def test_sodium_applicable_range(age, htn, dm, ok):
    assert r.sodium_applicable(age, htn, dm) is ok


def test_out_of_range_user_is_high_sodium_without_survey():
    c = r.classify(facts(age=72))
    assert c["high_sodium"] is True and c["sodium"]["sodium_grade"] == "not_applicable"


# ---------------------------------------------------------------- §2.2 분류
def test_drinker_needs_3_or_more_per_occasion():
    assert r.classify(facts(drink_freq="2_3_per_week", drink_amount="1_2"))["drinker"] is False
    assert r.classify(facts(drink_freq="2_3_per_week", drink_amount="3_4"))["drinker"] is True
    assert r.classify(facts(drink_freq="none_past_year", drink_amount="5_6"))["drinker"] is False


def test_smoker_is_cigarette_only():
    assert r.classify(facts(smoking="current"))["smoker"] is True
    assert r.classify(facts(smoking="never", ecig="daily"))["smoker"] is False


def test_overweight_from_height_weight():
    assert r.classify(facts(height_cm=170, weight_kg=72.3))["overweight"] is True   # 25.0
    assert r.classify(facts(height_cm=170, weight_kg=72.0))["overweight"] is False  # 24.9


def test_frequent_eatout_needs_high_sodium():
    c = r.classify(facts(scores=HIGH_NA, answers={"E1": "5_6_week"}))
    assert c["frequent_eatout"] is True
    c = r.classify(facts(**LOW, scores=LOW_NA, answers={"E1": "5_6_week"}))
    assert c["frequent_eatout"] is False


def test_skipped_questions_leave_classification_out():
    c = r.classify(facts())
    for key in ("high_sodium", "low_activity", "frequent_eatout", "breakfast_skip"):
        assert key not in c


# ---------------------------------------------------------------- §3 추천·대체
def test_smoker_and_drinker_get_fixed_missions():
    f = facts(smoking="current", drink_freq="2_3_per_week", drink_amount="5_6",
              scores=HIGH_NA, answers={"P1": "none", "E1": "rare", "B1": "5_7"})
    rec = r.recommend(r.classify(f), f.answers, set())
    assert [(s["code"], s["selection_type"]) for s in rec.fixed] == [("SMK-1", "fixed"), ("ALC-1", "fixed")]
    assert "NA-1" in rec.candidates and "ACT-2" in rec.candidates
    assert "SMK-1" not in rec.candidates


def test_replacement_order_and_different_categories():
    f = facts(scores=HIGH_NA, answers={"P1": "none", "E1": "1_day", "B1": "0"})
    rec = r.recommend(r.classify(f), f.answers, set())
    # 나트륨 → 신체 활동 순, 두 칸은 다른 카테고리
    assert [s["code"] for s in rec.fixed] == ["NA-1", "ACT-2"]
    assert all(s["selection_type"] == "replacement" for s in rec.fixed)
    # 고정 칸과 같은 미션만 빠지고 같은 카테고리의 다른 미션은 후보
    assert "NA-2" in rec.candidates and "NA-1" not in rec.candidates


def test_act1_only_with_baseline_steps():
    f = facts(**LOW, scores=LOW_NA, answers={"P1": "lt60"}, baseline_steps=5000)
    rec = r.recommend(r.classify(f), f.answers, set())
    assert rec.fixed[0]["code"] == "ACT-1"
    f = facts(**LOW, scores=LOW_NA, answers={"P1": "lt60"})
    rec = r.recommend(r.classify(f), f.answers, set())
    assert rec.fixed[0]["code"] == "ACT-2"


def test_act3_excluded_when_bp_160_100():
    f = facts(**LOW, sbp=165, scores=LOW_NA, answers={"P1": "none", "E1": "rare", "B1": "5_7"})
    rec = r.recommend(r.classify(f), f.answers, set())
    assert "ACT-3" not in rec.candidates
    assert any(e.get("code") == "ACT-3" for e in rec.excluded)


def test_weight_mission_only_for_overweight_and_not_replacement():
    f = facts(**LOW, weight_kg=77, scores=LOW_NA, answers={"P1": "150plus", "E1": "rare", "B1": "5_7"})
    rec = r.recommend(r.classify(f), f.answers, set())
    assert [s["code"] for s in rec.fixed] == [None, None]  # 대체 순서에 체중 관리 없음
    assert rec.candidates == ["WT-1"] and rec.all_good is False


def test_all_good_shows_full_list_without_weight():
    f = facts(**LOW, scores=LOW_NA, answers={"P1": "150plus", "E1": "rare", "B1": "5_7"})
    rec = r.recommend(r.classify(f), f.answers, set())
    assert rec.all_good is True
    assert "WT-1" not in rec.candidates and "ACT-1" not in rec.candidates  # 걸음 수 없음
    assert {"NA-1", "NA-2", "ACT-2", "ACT-3", "OUT-1", "BRK-1"} == set(rec.candidates)


def test_survey_needed_categories():
    f = facts()
    rec = r.recommend(r.classify(f), f.answers, set())
    assert set(rec.survey_needed) == {"SODIUM", "ACTIVITY", "EATOUT", "BREAKFAST"}


def test_completed_missions_stay_selectable():
    # 완료한 미션도 다음 사이클에서 이어서 고를 수 있음 (팀 결정 10/8)
    f = facts(scores=HIGH_NA, answers={"P1": "none", "E1": "rare", "B1": "0"})
    rec = r.recommend(r.classify(f), f.answers, {"NA-2", "BRK-1", "OUT-1"})
    assert "NA-2" in rec.candidates and "BRK-1" in rec.candidates
    assert rec.completed == ["BRK-1", "NA-2"]  # 후보에 없는 OUT-1은 표시하지 않음


# ---------------------------------------------------------------- §5 매일 기록
@pytest.mark.parametrize("sex,qty,status,exceeded", [
    ("male", 0, "completed", False), ("male", 2, "completed", False), ("male", 3, "failed", True),
    ("female", 1, "completed", False), ("female", 2, "failed", True), ("female", 7, "failed", True),
])
def test_alcohol_limit(sex, qty, status, exceeded):
    out = r.evaluate_log("ALC-1", None, qty, sex, {"male_max": 2, "female_max": 1})
    assert (out["status"], out["limit_exceeded"]) == (status, exceeded)


def test_log_mappings():
    assert r.evaluate_log("NA-1", "no_soup", None, "male", None)["status"] == "completed"
    assert r.evaluate_log("OUT-1", "no_eatout", None, "male", None)["status"] == "skipped"
    assert r.evaluate_log("ACT-2", "lt30", None, "male", None) == {"status": "failed", "quantity": 15, "limit_exceeded": False}
    assert r.evaluate_log("ACT-3", "partial", 2, "male", None)["quantity"] == 2
    assert r.evaluate_log("ACT-1", None, 7000, "male", {"steps_target": 7000})["status"] == "completed"
    assert r.evaluate_log("ACT-1", None, 6999, "male", {"steps_target": 7000})["status"] == "failed"
    assert r.evaluate_log("WT-1", "yes", None, "female", None)["status"] == "completed"
    with pytest.raises(ValueError):
        r.evaluate_log("BRK-1", "maybe", None, "male", None)
    with pytest.raises(ValueError):
        r.evaluate_log("ACT-3", "partial", None, "male", None)


# ---------------------------------------------------------------- §5.1 달성률
def test_progress_caps_week_at_100_and_ignores_failed():
    start = date(2026, 10, 12)
    logs = [(start + timedelta(days=i), "completed") for i in range(7)]  # 1주차 7번
    logs += [(start + timedelta(days=7), "failed"), (start + timedelta(days=8), "skipped")]
    p = r.progress(start, 5, logs)
    assert p["weeks"][0]["rate"] == 1.0 and p["weeks"][0]["completed"] == 7
    assert p["weeks"][1]["rate"] == 0.0
    assert p["cycle_rate"] == 0.25


def test_streak():
    today = date(2026, 10, 20)
    logs = [(today - timedelta(days=i), "completed") for i in (1, 2, 3)] + [(today - timedelta(days=5), "completed")]
    assert r.streak(logs, today) == 3  # 오늘 미기록이어도 어제까지 이어진 날 수


def test_sodium_low_answers_by_person():
    # 같은 최저 응답이어도 남성 45세(BMI 22.9)는 "많음", 여성 30세는 "적정"
    assert r.classify(facts(scores=LOW_NA))["sodium"]["sodium_grade"] == "careful_high"
    assert r.classify(facts(**LOW, scores=LOW_NA))["sodium"]["sodium_grade"] == "moderate"


def test_normal_weight_range():
    assert r.normal_weight_range(170) == (53, 66)
    assert r.waist_limit("male") == 90 and r.waist_limit("female") == 85


def test_excluded_items_have_kind():
    # 추천에서 빠진 이유의 종류: 이미 잘함 / 정보를 입력하면 추천 / 지금은 권하지 않음 (화면 문구가 갈림)
    f = facts(**LOW, sbp=165, scores=LOW_NA, answers={"P1": "none", "E1": "rare", "B1": "5_7"})
    rec = r.recommend(r.classify(f), f.answers, set())
    kinds = {(e.get("code") or e["category"]): e["kind"] for e in rec.excluded}
    assert kinds["ACT-1"] == "need_info"        # 평소 걸음 수를 모름
    assert kinds["ACT-3"] == "not_advised"      # 혈압 160/100 이상
    assert kinds["BREAKFAST"] == "doing_well"   # 아침을 잘 챙김
    assert kinds["EATOUT"] == "doing_well"
