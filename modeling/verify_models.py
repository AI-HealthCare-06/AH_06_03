"""모델 A·B 전달 전 검증 + 테스트 케이스 생성.

1) 변환표 일치: 학습 데이터 행을 서비스 입력 형식으로 바꿔 paeon_models 로 예측한 확률 vs
   학습 코드의 변환(from_knhanes / framingham 원본값)에 같은 JSON 계수를 적용한 확률 (화면 답 → 모델 값 변환이 학습 때와 같은지)
   ※ JSON 계수 ↔ sklearn 모델 일치(최대 1e-5, 계수 반올림)는 9/29 별도 확인
2) 일관성: 100건 × 10회 반복 예측 편차 = 0 (NFR-ML-005)
3) handoff/test_cases.json : 백엔드·프론트 연결 검증용 입력 + 기대 결과
"""
from pathlib import Path
import json
import os
import sys
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "model_b"))
import paeon_models as pm  # noqa: E402
from train_model_b import from_knhanes  # noqa: E402

DATA_DIR = Path(os.environ.get("PAEON_DATA_DIR", BASE.parents[1] / "데이터"))  # 저장소 바깥 데이터
SPEC_A, SPEC_B = json.loads(pm.SPEC_A.read_text()), json.loads(pm.SPEC_B.read_text())


def sigmoid_linear(spec, X: pd.DataFrame):
    """spec 계수로 직접 계산 (결측은 impute) — sklearn 파이프라인과 같은 식."""
    z = np.full(len(X), spec["intercept"])
    for f in spec["feats"]:
        z += f["coef"] * (X[f["k"]].fillna(f["impute"]).to_numpy() - f["mean"])
    return 1 / (1 + np.exp(-z))


# ── KNHANES 원본 코드 → 서비스 입력 (역변환, 검증용) ─────────────────────
INV = lambda d: {v: k for k, v in d.items()}  # noqa: E731
DF_INV, AMT_INV, BR_INV, EO_INV = INV(pm.DRINK_FREQ), INV(pm.DRINK_AMOUNT), INV(pm.BREAKFAST), INV(pm.EATOUT)


def knhanes_row_to_input(r):
    nz = lambda v: None if pd.isna(v) else v  # noqa: E731
    fh1, fh2 = r["HE_HPfh1"], r["HE_HPfh2"]
    parent = "yes" if 1 in (fh1, fh2) else ("no" if (fh1 == 0 and fh2 == 0) else "unknown")
    bs = r["BS3_1"]
    smoking = {1: "current", 2: "current", 3: "former", 8: "never"}.get(bs)
    bd11 = r["BD1_11"]
    drink_freq = None if bd11 == 9 else DF_INV[0 if bd11 == 8 else int(bd11)]
    amt = r["BD2_1"]
    bmi = nz(r["HE_BMI"])
    return {
        "age": int(r["age"]), "sex": "M" if r["sex"] == 1 else "F",
        # BMI를 그대로 재현하려고 키 100cm·체중=BMI 로 넣음 (검증 전용)
        "height_cm": 100.0 if bmi else None, "weight_kg": bmi,
        "waist_cm": nz(r["HE_wc"]), "parent_htn": parent, "smoking": smoking,
        "drink_freq": drink_freq, "drink_amount": AMT_INV.get(int(amt)) if amt in (1, 2, 3, 4, 5) else None,
        "aerobic": None if pd.isna(r["pa_aerobic"]) else int(r["pa_aerobic"]),
        "breakfast": None if pd.isna(r["L_BR_FQ"]) or r["L_BR_FQ"] == 9 else BR_INV[int(r["L_BR_FQ"])],
        "eatout": None if pd.isna(r["L_OUT_FQ"]) or r["L_OUT_FQ"] == 9 else EO_INV[8 - int(r["L_OUT_FQ"])],
        "htn_status": "none",
    }


def check_b():
    raw = pd.read_parquet(DATA_DIR / "KNHANES_2022_2024_selected.parquet")
    d = raw[(raw["age"] >= 19) & raw["HE_HP"].isin([1, 2, 3])].sample(2000, random_state=0)
    ref = sigmoid_linear(SPEC_B, from_knhanes(d))
    got = np.array([pm.predict_model_b(knhanes_row_to_input(r), SPEC_B)["probability"] for _, r in d.iterrows()])
    diff = np.abs(ref - got)
    return {"n": len(d), "max_abs_diff": float(diff.max()), "n_diff_gt_1e-4": int((diff > 1e-4).sum())}


def check_a():
    fr = pd.read_csv(DATA_DIR / "framingham.csv").sample(1000, random_state=0)
    fr = fr[fr["age"].between(32, 70)]
    feats = [f["k"] for f in SPEC_A["feats"]]
    ref = sigmoid_linear(SPEC_A, fr[feats])
    got = []
    for _, r in fr.iterrows():
        htn = "treated" if r["BPMeds"] == 1 else ("diagnosed_untreated" if r["prevalentHyp"] == 1 else "none")
        # Framingham은 약 복용자가 모두 prevalentHyp=1 (데이터 확인) → 3단계로 역변환 가능. BPMeds 결측은 prevalentHyp 기준
        inp = {"age": r["age"], "sex": "M" if r["male"] == 1 else "F", "sbp": r["sysBP"],
               "total_chol": None if pd.isna(r["totChol"]) else r["totChol"],
               "smoking": "current" if r["currentSmoker"] == 1 else "never",
               "diabetes": bool(r["diabetes"]), "htn_status": htn,
               "height_cm": 100.0 if not pd.isna(r["BMI"]) else None, "weight_kg": None if pd.isna(r["BMI"]) else r["BMI"]}
        got.append(pm.predict_model_a(inp, SPEC_A)["probability"])
    # BPMeds 결측 행은 서비스 입력에서 값이 생기므로 비교에서 제외
    mask = fr["BPMeds"].notna().to_numpy()
    diff = np.abs(ref - np.array(got))[mask]
    return {"n": int(mask.sum()), "max_abs_diff": float(diff.max()), "n_diff_gt_1e-4": int((diff > 1e-4).sum())}


# 모델 B v0.2.0: 운동·아침·외식은 입력에서 제외 (handoff/생활습관_입력_가이드.md 부록 A)
CASES = [
    ("T1_45세남성_흡연_데모예시", {"age": 45, "sex": "M", "height_cm": 172, "weight_kg": 78, "waist_cm": 88, "sbp": 145, "dbp": 92,
                         "total_chol": 212, "smoking": "current", "diabetes": False, "htn_status": "none",
                         "parent_htn": "yes", "drink_freq": "2_3_per_week", "drink_amount": "5_6"}),
    ("T2_35세여성_비흡연_저위험", {"age": 35, "sex": "F", "height_cm": 162, "weight_kg": 54, "waist_cm": 70, "sbp": 110, "dbp": 70,
                   "total_chol": 180, "smoking": "never", "diabetes": False, "htn_status": "none", "parent_htn": "no",
                   "drink_freq": "lt_monthly", "drink_amount": "1_2"}),
    ("T3_62세남성_고혈압약복용_고위험", {"age": 62, "sex": "M", "height_cm": 170, "weight_kg": 85, "waist_cm": 98, "sbp": 165, "dbp": 98,
                   "total_chol": 260, "smoking": "current", "diabetes": True, "htn_status": "treated", "parent_htn": "yes",
                   "drink_freq": "4plus_per_week", "drink_amount": "7_9"}),
    ("T4_55세여성_고혈압진단_약안먹음", {"age": 55, "sex": "F", "height_cm": 158, "weight_kg": 66, "waist_cm": 86, "sbp": 138, "dbp": 86,
                         "total_chol": 230, "smoking": "never", "diabetes": False, "htn_status": "diagnosed_untreated",
                         "parent_htn": "unknown", "drink_freq": "never_lifetime", "drink_amount": None}),
    ("T5_27세남성_모델A연령밖", {"age": 27, "sex": "M", "height_cm": 178, "weight_kg": 92, "waist_cm": 95, "sbp": 128, "dbp": 82,
                        "total_chol": 190, "smoking": "current", "diabetes": False, "htn_status": "none", "parent_htn": "yes",
                        "drink_freq": "2_3_per_week", "drink_amount": "10plus"}),
    ("T6_48세여성_과거흡연_선택항목결측", {"age": 48, "sex": "F", "height_cm": 165, "weight_kg": 60, "waist_cm": None, "sbp": 122, "dbp": 78,
                     "total_chol": 205, "smoking": "former", "diabetes": False, "htn_status": "none", "parent_htn": "unknown",
                     "drink_freq": "monthly", "drink_amount": None}),
]


def main():
    out = {"consistency_model_a": check_a(), "consistency_model_b": check_b()}
    # 반복 일관성 100건 × 10회
    rng = np.random.default_rng(0)
    base = [c[1] for c in CASES]
    inputs = [dict(base[i % len(base)], age=int(rng.integers(32, 71))) for i in range(100)]
    runs = [[(pm.predict_model_a(x)["probability"], pm.predict_model_b(x).get("probability")) for x in inputs] for _ in range(10)]
    out["repeat_100x10_max_deviation"] = float(np.nanmax(np.ptp(np.array(runs, dtype=float), axis=0)))
    cases = [{"case_id": cid, "input": inp, "expected_model_a": pm.predict_model_a(inp), "expected_model_b": pm.predict_model_b(inp)}
             for cid, inp in CASES]
    hand = BASE / "handoff"
    hand.mkdir(exist_ok=True)
    (hand / "test_cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2))
    (BASE / "verify_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    for c in cases:
        a, b = c["expected_model_a"], c["expected_model_b"]
        print(c["case_id"], "| A:", a["status"], a.get("probability"), a.get("risk_level"),
              (a.get("top_modifiable_factor") or {}).get("label"),
              "| B:", b["status"], b.get("skip_reason"), b.get("probability"),
              (b.get("top_risk_factor") or {}).get("label"), (b.get("top_modifiable_factor") or {}).get("label"),
              "missing", b.get("missing_features"))


if __name__ == "__main__":
    main()
