"""PAEON 모델 A·B 추론 모듈 (전처리 포함, 외부 라이브러리 없음).

사용법
    from paeon_models import predict_model_a, predict_model_b
    predict_model_a(user_input)   # dict → dict
    predict_model_b(user_input)

- 계수는 artifacts/*.json 에서 읽음 (로지스틱회귀, 원래 단위: p = σ(intercept + Σ coef·(x − mean)))
- 기여도 = coef·(x − baseline) (로그 오즈 단위). baseline = 있다/없다 요인은 0(없음), 숫자·단계 요인은 학습 데이터 평균
  → 비흡연자에게 "흡연"이 위험 요인으로 붙지 않음. 확률 계산은 기준점과 무관(학습 식 그대로)
- 같은 입력이면 항상 같은 결과 (NFR-ML-005)
- 입력 필드·선택지 정의는 handoff/모델_연결_명세.md
"""
from __future__ import annotations
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
SPEC_A = BASE / "model_a" / "artifacts" / "model_a_v0.1.0.json"
SPEC_B = BASE / "model_b" / "artifacts" / "model_b_v0.1.0.json"

# ── 선택지 → 모델 값 변환표 (학습 데이터 코드와 1:1) ─────────────────────
SMOKING = {"current": "current", "former": "former", "never": "never"}  # BS3_1 1·2 / 3 / 8
DRINK_FREQ = {  # BD1_11 → 0~6 (클수록 자주). 8(평생 비음주)=0
    "never_lifetime": 0, "none_past_year": 1, "lt_monthly": 2, "monthly": 3,
    "2_4_per_month": 4, "2_3_per_week": 5, "4plus_per_week": 6,
}
DRINK_AMOUNT = {"1_2": 1, "3_4": 2, "5_6": 3, "7_9": 4, "10plus": 5}  # BD2_1, 안 마시면 0
BREAKFAST = {"5_7": 1, "3_4": 2, "1_2": 3, "0": 4}  # L_BR_FQ (클수록 결식)
EATOUT = {  # L_OUT_FQ 1~7 → 7~1 (클수록 외식·배달 잦음)
    "2plus_per_day": 7, "1_per_day": 6, "5_6_per_week": 5, "3_4_per_week": 4,
    "1_2_per_week": 3, "1_3_per_month": 2, "lt_monthly": 1,
}
PARENT_HTN = {"yes": 1, "no": 0, "unknown": None}
HTN_STATUS = ("none", "diagnosed_untreated", "treated")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _bmi(inp):
    h, w = inp.get("height_cm"), inp.get("weight_kg")
    return None if not h or not w else w / (h / 100) ** 2


def _num(v):
    return None if v is None else float(v)


def aerobic_from_minutes(moderate_min: float | None, vigorous_min: float | None):
    """주당 중강도·고강도 분 → pa_aerobic(0/1). 기준: 중강도 150분 이상 또는 고강도 75분 이상 또는
    중강도 + 고강도×2 ≥ 150 (지침서 pa_aerobic 정의의 조합 기준을 분 단위로 단순화)."""
    if moderate_min is None and vigorous_min is None:
        return None
    m, v = moderate_min or 0, vigorous_min or 0
    return int(m >= 150 or v >= 75 or m + 2 * v >= 150)


def features_a(inp: dict) -> dict:
    htn = inp.get("htn_status")
    sm = inp.get("smoking")
    return {
        "age": _num(inp.get("age")),
        "male": None if inp.get("sex") is None else int(inp["sex"] == "M"),
        "sysBP": _num(inp.get("sbp")),
        "totChol": _num(inp.get("total_chol")),
        "currentSmoker": None if sm is None else int(SMOKING[sm] == "current"),
        "diabetes": None if inp.get("diabetes") is None else int(bool(inp["diabetes"])),
        "BPMeds": None if htn is None else int(htn == "treated"),
        "prevalentHyp": None if htn is None else int(htn != "none"),
        "BMI": _bmi(inp),
    }


def features_b(inp: dict) -> dict:
    sm = inp.get("smoking")
    df = inp.get("drink_freq")
    dfv = None if df is None else DRINK_FREQ[df]
    if dfv is not None and dfv <= 1:          # 최근 1년 안 마심·평생 안 마심 → 음주량 0 (BD2_1=8)
        amt = 0
    else:
        amt = None if inp.get("drink_amount") is None else DRINK_AMOUNT[inp["drink_amount"]]
    br, eo = inp.get("breakfast"), inp.get("eatout")
    aer = inp.get("aerobic")
    if aer is None:
        aer = aerobic_from_minutes(inp.get("moderate_min_per_week"), inp.get("vigorous_min_per_week"))
    return {
        "age": None if inp.get("age") is None else float(min(inp["age"], 80)),
        "male": None if inp.get("sex") is None else int(inp["sex"] == "M"),
        "bmi": _bmi(inp),
        "waist": _num(inp.get("waist_cm")),
        "parent_htn": None if inp.get("parent_htn") is None else PARENT_HTN[inp["parent_htn"]],
        "smoke_current": None if sm is None else int(SMOKING[sm] == "current"),
        "smoke_former": None if sm is None else int(SMOKING[sm] == "former"),
        "drink_freq": dfv,
        "drink_amount": amt,
        "aerobic": None if aer is None else int(aer),
        "breakfast_skip": None if br is None else BREAKFAST[br],
        "eatout": None if eo is None else EATOUT[eo],
    }


def _score(spec: dict, x: dict) -> dict:
    logit, factors, missing = spec["intercept"], [], []
    for f in spec["feats"]:
        v = x.get(f["k"])
        if v is None:
            missing.append(f["k"])
            v = f["impute"]
        logit += f["coef"] * (v - f["mean"])            # 확률 계산 (학습 식 그대로)
        c = f["coef"] * (v - f.get("baseline", f["mean"])) + 0.0  # 기여도: 있다/없다 요인은 "없음" 기준 (+0.0: -0.0 방지)
        if round(c, 6) == 0:
            continue  # 기준점과 같음 = 해당 없음 → 요인 목록에서 뺌 (비어서 채운 값은 missing_features 에 남음)
        vl = f.get("value_labels", {}).get(str(int(v))) if f.get("value_labels") and float(v).is_integer() else None
        factors.append({"code": f["k"], "label": f["label"], "value": v, "value_label": vl, "contribution": round(c, 6) + 0.0,
                        "direction": "risk_increase" if c > 0 else "protective", "modifiable": f["modifiable"],
                        "direction_matches_expectation": f.get("direction_matches_expectation", True)})
    p = 1 / (1 + math.exp(-logit))
    factors.sort(key=lambda r: -r["contribution"])  # 기여도 0(해당 없음)은 강조 후보가 아님
    for i, r in enumerate(factors, 1):
        r["display_rank"] = i
    # 강조 후보 = 위험을 높인 방향(+) 요인, 기여도 순 그대로 (REQ-PRED-003).
    # 학습 방향이 상식과 반대인 요인도 거르지 않음 → direction_matches_expectation 로 알림만
    pos = [r for r in factors if r["contribution"] > 0]
    return {"probability": round(p, 6), "factors": factors,
            "top_risk_factor": pos[0] if pos else None,
            "top_modifiable_factor": next((r for r in pos if r["modifiable"]), None),
            "missing_features": missing}


def _skip(spec, reason):
    return {"model_code": spec["model_code"], "model_version": spec["version"], "status": "skipped",
            "skip_reason": reason}


def predict_model_a(inp: dict, spec: dict | None = None) -> dict:
    spec = spec or _load(SPEC_A)
    lo, hi = spec["age_range"]
    if inp.get("age") is None or not (lo <= inp["age"] <= hi):
        return _skip(spec, "age_out_of_range")
    out = _score(spec, features_a(inp))
    p = out["probability"]
    out["risk_level"] = "normal" if p < 0.10 else ("borderline" if p <= 0.20 else "high")
    out["percentile"] = None  # 1사이클 미제공 (한국인 기준 상대 위치는 보정 사이클에서)
    return {"model_code": spec["model_code"], "model_version": spec["version"], "status": "completed",
            "skip_reason": None, **out}


def predict_model_b(inp: dict, spec: dict | None = None) -> dict:
    spec = spec or _load(SPEC_B)
    if inp.get("age") is None or inp["age"] < spec["age_min"]:
        return _skip(spec, "age_out_of_range")
    if inp.get("htn_status") in ("diagnosed_untreated", "treated"):
        return _skip(spec, "htn_diagnosed")
    out = _score(spec, features_b(inp))
    out["risk_level"] = None   # 모델 B는 판정하지 않음 (판정 = 입력 혈압 규칙)
    out["percentile"] = None
    return {"model_code": spec["model_code"], "model_version": spec["version"], "status": "completed",
            "skip_reason": None, **out}
