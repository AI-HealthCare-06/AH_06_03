"""기존 화면(W01~W12) 캡처용 가짜 데이터. 모두 예시이며 실제 사용자 정보는 쓰지 않는다.
기준 시각 2026-10-25 12:00(한국) 일요일. 4주 챌린지는 10/12 시작 → 14일째(2주차)."""
import json

TODAY = "2026-10-25"
START = "2026-10-12"

# ---------------------------------------------------------------- localStorage 씨앗
PROFILE = {"birth": "1982-04-12", "email": "demo@paeon.example"}
ELIG = {"ageBand": "in", "chd": False}
HEALTH = {"sex": "female", "height_cm": 168, "weight_kg": 62, "waist_cm": 81, "sbp": 128, "dbp": 84, "smoking": "never",
          "drink_freq": "lt_monthly", "diabetes": False, "htn_status": "none", "parent_htn": "no", "total_chol": 190,
          "recorded_at": "2026-10-12"}
SURVEY = {"answers": {"P1": "60_149", "E1": "1_2_week", "B1": "3_4"}, "sodium": {"status": "ok", "grade": "careful_high"}, "baseline_steps": 6200}


def f(code, label, c, direction, modifiable, rank, ok=True):
    return {"code": code, "label": label, "value": None, "value_label": None, "contribution": c, "direction": direction,
            "modifiable": modifiable, "direction_matches_expectation": ok, "display_rank": rank}


A_FACTORS = [f("sbp", "수축기혈압", 18.6, "risk_increase", True, 1), f("age", "나이", 7.9, "risk_increase", False, 2),
             f("chol", "총콜레스테롤", -5.9, "protective", True, 3)]
B_FACTORS = [f("parent_htn", "부모 고혈압 가족력", 32.1, "risk_increase", False, 1), f("bmi", "BMI", 24.7, "risk_increase", True, 2),
             f("waist", "허리둘레", 17.1, "risk_increase", True, 3)]
PRED = {
    "bp_stage": "prehypertension",
    "model_a": {"model_code": "MODEL_A", "model_version": "0.2.0", "status": "completed", "skip_reason": None, "probability": 0.033,
                "risk_level": "borderline", "percentile": 51, "vascular_age": 53.8, "similarity_level": None, "factors": A_FACTORS,
                "top_risk_factor": A_FACTORS[0], "top_modifiable_factor": A_FACTORS[0], "missing_features": []},
    "model_b": {"model_code": "MODEL_B", "model_version": "0.2.0", "status": "completed", "skip_reason": None, "probability": None,
                "risk_level": None, "percentile": None, "vascular_age": None, "similarity_level": "slightly_different",
                "factors": B_FACTORS, "top_risk_factor": B_FACTORS[0], "top_modifiable_factor": B_FACTORS[1], "missing_features": []},
    "disclaimer": "이 결과는 진단이 아닌 선별 정보입니다. 정확한 판단은 의료기관에서 확인하세요",
}
CYCLE_LS = {"cycleId": "cy1", "cycleNo": 1, "status": "active", "startedOn": START,
            "missions": [{"id": "SMK-1", "t": "금연 유지", "lv": "중", "cat": "smoking"}, {"id": "ALC-1", "t": "표준잔 지키기", "lv": "중", "cat": "alcohol"},
                         {"id": "NA-1", "t": "국물 남기기", "lv": "하", "cat": "sodium"}]}
DAYS = list(range(0, 13))
PROGRESS = {"days": DAYS, "missionLog": {str(i): ["SMK-1", "ALC-1", "NA-1"] for i in DAYS}, "logs": {},
            "bpLog": [{"date": "2026-10-12", "sbp": 128, "dbp": 84}, {"date": "2026-10-19", "sbp": 124, "dbp": 82}]}
CALENDAR = {"entries": {"2026-10-20": {"diary": "오늘은 30분 걸었다", "todos": [{"t": "혈압 재기", "done": False}], "events": [{"t": "건강검진 예약"}]}}}

SEEDS = {"paeon-profile": PROFILE, "paeon-eligibility": ELIG, "paeon-health": HEALTH, "paeon-survey": SURVEY,
         "paeon-prediction": PRED, "paeon-cycle": CYCLE_LS, "paeon-progress": PROGRESS, "paeon-calendar": CALENDAR}


def seed_js(keys):
    """localStorage에 넣는 JS. keys가 None이면 전부."""
    items = {k: json.dumps(v, ensure_ascii=False) for k, v in SEEDS.items() if keys is None or k in keys}
    return "(items) => { for (const [k, v] of Object.entries(items)) localStorage.setItem(k, v); }", items


# ---------------------------------------------------------------- API
def card(code, cat, cat_name, name, diff, desc, q, answers):
    return {"code": code, "category": cat, "category_name": cat_name, "name": name, "difficulty": diff, "weekly_target": 5,
            "description": desc, "evidence": "", "source": "", "notice": None, "question": q,
            "answers": [{"code": a[0], "label": a[1]} for a in answers], "completed_before": False}


YN = [("done", "했어요"), ("not_done", "못 했어요")]
C_SMK = card("SMK-1", "smoking", "흡연", "금연 유지 (전자담배 포함)", "medium", "오늘 담배(전자담배 포함)를 피우지 않았나요", "오늘 담배를 피우지 않았나요?", [("not_smoked", "안 피웠어요"), ("smoked", "피웠어요")])
C_ALC = card("ALC-1", "alcohol", "음주", "표준잔 지키기 · 남 2 / 여 1", "medium", "마신 날도 표준잔 이하로", "오늘 술을 마셨나요?", [("none", "안 마셨어요"), ("within", "한도 안에서 마셨어요"), ("over", "넘게 마셨어요")])
C_NA = card("NA-1", "sodium", "나트륨", "국물 남기기", "low", "국·찌개 국물은 건더기 위주로", "오늘 국물을 남겼나요?", YN)


def logs(code, upto, start=START):
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    return [{"log_date": (d0 + timedelta(days=i)).isoformat(), "status": "completed", "answer": "x", "quantity": None, "limit_exceeded": False, "warning": None} for i in range(upto)]


def weeks(w1, w2):
    return [{"week": 1, "completed": w1, "target": 5, "rate": w1 / 5}, {"week": 2, "completed": w2, "target": 5, "rate": w2 / 5},
            {"week": 3, "completed": 0, "target": 5, "rate": 0}, {"week": 4, "completed": 0, "target": 5, "rate": 0}]


def mission(i, sel, c, upto, w2):
    ls = logs(c["code"], upto)
    return {"cycle_challenge_id": f"cm{i}", "selection_type": sel, "status": "active", "card": c, "weekly_target": 5, "target_config": None,
            "weeks": weeks(5, w2), "cycle_rate": 0.4, "streak": 4, "today_log": None, "logs": ls}


CYCLE = {"cycle_id": "cy1", "cycle_number": 1, "total_cycles": 3, "status": "active", "started_on": START, "ended_on": "2026-11-08", "today": TODAY,
         "day_number": 14, "week_number": 2, "demo": None,
         "missions": [mission(1, "fixed", C_SMK, 13, 5), mission(2, "fixed", C_ALC, 13, 5), mission(3, "selected", C_NA, 13, 5)]}

RECO = {"cycle_number": 1, "total_cycles": 3, "keep_going_message": None, "all_good": False, "selectable_notice": "이 중 1개를 골라 주세요", "sodium": None, "survey_needed": [],
        "fixed": [{"slot": 1, "slot_label": "흡연", "selection_type": "fixed", "mission": C_SMK},
                  {"slot": 2, "slot_label": "음주", "selection_type": "fixed", "mission": C_ALC}],
        "candidates": [card("NA-1", "sodium", "나트륨", "국물 남기기", "low", "국·찌개 국물은 건더기 위주로", "?", YN),
                       card("DIET-1", "diet", "식단", "집밥·저염식", "medium", "집에서 싱겁게 먹기", "?", YN),
                       card("BF-1", "breakfast", "아침 식사", "아침 식사", "medium", "아침을 거르지 않기", "?", YN),
                       card("EAT-1", "eatout", "외식", "저염 외식 요령", "low", "외식 때 국물·소스 줄이기", "?", YN)],
        "excluded": [{"code": "ACT-2", "category": "activity", "name": "하루 30분 걷기", "kind": "doing_well", "reason": "권고 150분을 이미 넘겼어요"},
                     {"code": "WT-1", "category": "weight", "name": "4주 −1kg", "kind": "doing_well", "reason": "BMI가 권고 범위예요"}]}

SUMMARY = {"today": TODAY, "today_total": 3, "today_done": 2, "streak": 4, "pie": 120, "week": [
    {"date": f"2026-10-{19 + i}", "done": i < 6} for i in range(7)]}
BADGES = {"earned_count": 3, "total": 12, "next": {"label": "7일 연속"}, "items": []}


def snap(d, sbp, dbp, w, waist, smoking="never", drink="lt_monthly"):
    return {"examination_date": d, "sbp": sbp, "dbp": dbp, "weight_kg": w, "waist_cm": waist, "smoking": smoking, "drink_freq": drink, "drink_amount": None}


def models(before_p, after_p, b_before, b_after):
    return [{"model_code": "MODEL_A", "before_status": "completed", "before_risk_level": "borderline", "before_probability": before_p,
             "after_status": "completed", "after_risk_level": "normal", "after_probability": after_p, "model_version": "0.2.0", "comparable": True,
             "reason": None, "before_similarity_level": None, "after_similarity_level": None, "before_percentile": 51, "after_percentile": 44},
            {"model_code": "MODEL_B", "before_status": "completed", "before_risk_level": None, "before_probability": None,
             "after_status": "completed", "after_risk_level": None, "after_probability": None, "model_version": "0.2.0", "comparable": True,
             "reason": None, "before_similarity_level": b_before, "after_similarity_level": b_after}]


REVIEW = {"cycle_id": "cy0", "cycle_number": 1, "total_cycles": 3, "cycle_status": "completed", "reassessed": True,
          "before": snap("2026-09-14", 135, 86, 63, 83), "after": snap("2026-10-12", 128, 84, 62, 81),
          "missions": [{"code": "SMK-1", "name": "금연 유지", "status": "completed", "cycle_rate": 0.9}],
          "normal_weight_range": [52, 64], "waist_limit": 85, "models": models(0.033, 0.018, "slightly_different", "similar"),
          "bp_note": "혈압 변화는 4주 사이 측정값 차이예요.", "demo_fill": None}
CYCLES = [{"cycle_id": "cy0", "cycle_number": 1, "status": "completed", "started_on": "2026-09-14", "ended_on": "2026-10-11", "cycle_rate": 0.82,
           "mission_codes": ["SMK-1", "ALC-1", "NA-1"], "reassessed": True}]
PROGRAM = {"weeks_done": 12, "before": snap("2026-09-14", 135, 86, 63, 83, "current", "2_3_per_week"), "after": snap("2026-12-07", 124, 80, 60, 78),
           "checkpoints": [dict(snap("2026-09-14", 135, 86, 63, 83), week=0), dict(snap("2026-10-12", 130, 84, 62, 81), week=4),
                           dict(snap("2026-11-09", 126, 82, 61, 79), week=8), dict(snap("2026-12-07", 124, 80, 60, 78), week=12)],
           "cycles": [{"cycle_number": 1, "status": "completed", "cycle_rate": 0.82}, {"cycle_number": 2, "status": "completed", "cycle_rate": 0.8},
                      {"cycle_number": 3, "status": "completed", "cycle_rate": 0.86}],
           "models": models(0.033, 0.018, "slightly_different", "similar"), "bp_note": "혈압은 시작과 4주마다 재입력할 때만 측정돼요."}
PRED_JOBS = {"items": []}
ME = {"user_id": "u-demo", "email": "demo@paeon.example", "birth_date": "1982-04-12", "sex": "female"}
CONSENTS = [{"policy_type": "health_data", "status": "agreed", "policy_id": "pol1"}]
