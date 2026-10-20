"""모델 A v0.2.0 생성 — v0.1.1의 계수는 그대로 두고, 한국인 기준으로 세 가지를 추가·변경한다.

① kr_percentile  : 국민건강영양조사 2022~24 만 32~70세(가중)에서 성별 × 연령대의 점수(z) 분위수 → "같은 성별·연령대 상위 %"
② intercept_by_sex: 성별 절편 재보정. 목표 10년 위험 = Jee 2014 본문의 평균 10년 위험(남 1.03% · 여 0.40%),
                     위험요인 평균 = Jee 2014 Table 1 (Korean Heart Study)
③ vascular_age.ref_means: 혈관 나이의 기준 평균을 Framingham 평균 → 국민건강영양조사 성별 × 연령대 평균으로 변경

기록 문구 (handoff/데이터_특성.md §1.6):
  모델 A의 재보정은 D'Agostino 2001(JAMA 286:180)의 재보정 개념(계수는 유지, 위험요인 평균과 기저 발생률을
  대상 집단 값으로 교체)을 로지스틱 절편에만 적용한 실험이다. 한국인 목표값(위험요인 평균, 발생률)은 Jee 2014
  (BMJ Open 4:e005025, Korean Heart Study)의 Table 1·2에서 가져왔다. Jee 2014 자체도 Framingham을 한국인에
  재보정했으며, 우리 방식은 그 논문의 방법과 같지 않다. 한국인 결과 자료로는 검증하지 않았다.

입력 : $PAEON_DATA_DIR/KNHANES_2022_2024_selected.parquet (저장소 밖), artifacts/model_a_v0.1.1.json
출력 : artifacts/model_a_v0.2.0.json
실행 : PAEON_DATA_DIR=<데이터 폴더> python3 modeling/model_a/build_model_a_v020.py
"""
from pathlib import Path
import copy
import json
import math
import os
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import paeon_models as pm  # noqa: E402  (features_a 변환만 사용)

DATA_DIR = Path(os.environ.get("PAEON_DATA_DIR", BASE.parents[2] / "데이터"))
V011 = BASE / "artifacts" / "model_a_v0.1.1.json"
OUT = BASE / "artifacts" / "model_a_v0.2.0.json"

AGE_BANDS = [(32, 39), (40, 49), (50, 59), (60, 70)]
# Jee 2014 (Korean Heart Study) Table 1 평균. 'rate'는 이 모델에서 쓰지 않음(Table 2 발생률, 참고)
KHS = {
    "M": {"age": 45.8, "sysBP": 123.3, "totChol": 194.5, "BMI": 23.8, "currentSmoker": 0.530, "diabetes": 0.084,
          "prevalentHyp": 0.286, "BPMeds": 0.044},
    "F": {"age": 47.6, "sysBP": 121.0, "totChol": 195.1, "BMI": 23.2, "currentSmoker": 0.051, "diabetes": 0.060,
          "prevalentHyp": 0.247, "BPMeds": 0.053},
}
TARGET_10Y = {"M": 0.0103, "F": 0.0040}  # Jee 2014 본문 "평균 10년 위험" (산출 방식은 본문에 없음)
REF_FEATS = ["sysBP", "totChol", "currentSmoker", "diabetes", "BPMeds", "prevalentHyp", "BMI"]  # 혈관 나이 계산 요인


def knhanes_inputs() -> pd.DataFrame:
    d = pd.read_parquet(DATA_DIR / "KNHANES_2022_2024_selected.parquet")
    d = d[d["age"].between(32, 70)]
    d = d[d["HE_sbp"].notna() & d["HE_chol"].notna() & d["HE_BMI"].notna() & d["wt_tot"].notna()]
    d = d[d["BS3_1"].isin([1, 2, 3, 8]) & d["DE1_dg"].isin([0, 1]) & d["DI1_dg"].isin([0, 1])]
    smoking = d["BS3_1"].map({1: "current", 2: "current", 3: "former", 8: "never"})
    treated = d["DI1_2"].isin([1, 2, 3, 4])
    htn = np.where(d["DI1_dg"] == 1, np.where(treated, "treated", "diagnosed_untreated"), "none")
    return pd.DataFrame({
        "age": d["age"].astype(int), "sex": np.where(d["sex"] == 1, "M", "F"),
        "sbp": d["HE_sbp"], "total_chol": d["HE_chol"], "smoking": smoking,
        "diabetes": d["DE1_dg"] == 1, "htn_status": htn,
        "height_cm": 100.0, "weight_kg": d["HE_BMI"],  # BMI를 그대로 재현 (verify_models와 같은 방식)
        "w": d["wt_tot"],
    }, index=d.index)


def band_of(age: int) -> str:
    return next(f"{lo}-{hi}" for lo, hi in AGE_BANDS if lo <= age <= hi)


def wquantiles(v, w, qs):
    o = np.argsort(v)
    v, w = np.asarray(v)[o], np.asarray(w)[o]
    c = np.cumsum(w) / w.sum()
    return np.interp(qs, c, v)


def main():
    spec = json.loads(V011.read_text(encoding="utf-8"))
    co = {f["k"]: f for f in spec["feats"]}
    r = knhanes_inputs()
    xs = [pm.features_a(row) for row in r.to_dict("records")]
    r["z"] = [sum(f["coef"] * ((x[f["k"]] if x[f["k"]] is not None else f["impute"]) - f["mean"]) for f in spec["feats"])
              for x in xs]
    for k in REF_FEATS:
        r[k] = [x[k] for x in xs]
    r["band"] = r["age"].map(band_of)

    # ① 성별 × 연령대 점수(z) 분위수 1~99 (가중)
    qs = np.arange(1, 100) / 100
    groups, ref_means = {}, {}
    for (sex, b), g in r.groupby(["sex", "band"]):
        key = f"{sex}|{b}"
        groups[key] = {"n": int(len(g)), "z_quantiles": [round(float(v), 6) for v in wquantiles(g["z"], g["w"], qs)]}
        ref_means[key] = {k: round(float(np.average(g[k].astype(float), weights=g["w"])), 4) for k in REF_FEATS}

    # ② 성별 절편: Korean Heart Study 평균 프로필의 위험 = 목표 10년 위험
    calib = {}
    for sex, k in KHS.items():
        xbar = dict(k, male=1.0 if sex == "M" else 0.0)
        z_khs = sum(co[f]["coef"] * (xbar[f] - co[f]["mean"]) for f in xbar if f in co)
        t = TARGET_10Y[sex]
        a_new = math.log(t / (1 - t)) - z_khs
        calib[sex] = {"target_10y_risk": t, "z_at_khs_mean": round(z_khs, 6), "intercept": round(a_new, 6)}

    v2 = copy.deepcopy(spec)
    v2["version"] = "0.2.0"
    v2["target"] = "10년 내 심장 혈관 건강 신호 (Framingham 계열 로지스틱, 한국인 상대 위치·성별 절편 재보정, v0.1.1과 같은 계수)"
    v2["calibration"] = ("v0.2.0: 계수·입력은 v0.1.1과 같음. ① 같은 성별·연령대 한국 성인(국민건강영양조사 2022~24) 상위 % ② 성별 절편을 "
                         "Korean Heart Study 평균 10년 위험(남 1.03% · 여 0.40%)에 맞춰 재보정 ③ 혈관 나이 기준 평균을 한국 성인 평균으로. "
                         "D'Agostino 2001(JAMA 286:180)의 재보정 개념을 로지스틱 절편에만 적용한 실험이며 그 논문의 방법과 같지 않다. "
                         "한국인 결과 자료로는 검증하지 않았다. 결과 정의: 모델은 협심증 포함 TenYearCHD로 학습, 목표값은 협심증 제외 hard CHD")
    v2["formula"] = "p = 1 / (1 + exp(-(intercept_by_sex[성별] + Σ coef·(x − mean))))"
    v2["intercept"] = spec["intercept"]  # v0.1.1 미국 절편(참고용, 계산에는 intercept_by_sex 사용)
    v2["intercept_by_sex"] = {s: calib[s]["intercept"] for s in calib}
    v2["kr_calibration"] = {
        "method": "계수 유지, 성별 절편만 변경: intercept = logit(목표 10년 위험) − Σ coef·(Korean Heart Study 평균 − 학습 평균)",
        "source_targets": "Jee SH 등. BMJ Open 2014;4:e005025 (Korean Heart Study). 위험요인 평균 = Table 1, 평균 10년 위험 = 본문",
        "by_sex": calib,
        "note": "목표 10년 위험은 본문의 1.03%·0.40%(산출 방식 미확인). Table 2 발생률×10으로 계산한 1.20%·0.52%는 쓰지 않음",
    }
    v2["bands"] = {
        "기준": "보정된 10년 위험(probability)의 절대 기준 — JAS 2017(일본 동맥경화학회, Suita 점수)의 10년 관상동맥질환 위험 구간",
        "양호": "probability < 0.02", "주의": "0.02 ≤ probability < 0.09", "높음": "probability ≥ 0.09",
        "borderline_min_risk": 0.02, "high_min_risk": 0.09,
        "source": "Japan Atherosclerosis Society(JAS) Guidelines for Prevention of Atherosclerotic Cardiovascular Diseases 2017 (J Atheroscler Thromb 2018;25(9):846-, "
                  "공개 전문 PMC6143773): Suita 점수 ≤40 low(10년 CAD 확률 <2%), 41~55 moderate(2~8%), ≥56 high(≥9%). 지침은 임계값을 통계가 아니라 임상 합의·관습으로 "
                  "정했다고 적음. 일본 인구 기준이며 이 모델·한국인 자료로 검증한 것이 아님. handoff/데이터_특성.md §1.7",
        "not_used": "상위 % (percentile)는 범주에 쓰지 않고 참고 정보로만 제공. 미국 NCEP ATP III의 10%/20%는 한국인 보정 확률에서 구분이 안 되어 쓰지 않음(§1.7)",
    }
    v2["kr_percentile"] = {
        "method": "국민건강영양조사 2022~24, 만 32~70세, 조사 가중치(wt_tot) 적용, 성별×연령대 모델 A 선형합(z) 분위수. "
                  "상위 % = max(1, 100 − (z보다 작은 분위수 개수))",
        "n_total": int(len(r)), "age_bands": [list(b) for b in AGE_BANDS], "groups": groups,
    }
    va = spec["vascular_age"]
    v2["vascular_age"] = {
        "formula": "age + Σ_{k ∉ fixed} coef_k·(x_k − ref_mean_k) / age_coef, clamp [20, 90]. ref_mean = 같은 성별·연령대 한국 성인 평균",
        "fixed": va["fixed"], "age_coef": va["age_coef"], "clamp": va["clamp"],
        "ref_means": ref_means,
        "note": "기준은 국민건강영양조사 성별×연령대 평균(위험요인이 한국 평균이면 혈관 나이 = 실제 나이). 추정치로 표기",
    }
    OUT.write_text(json.dumps(v2, ensure_ascii=False, indent=2), encoding="utf-8")
    print("저장:", OUT)
    print("절편:", v2["intercept_by_sex"])
    print("n:", {k: v["n"] for k, v in groups.items()})


if __name__ == "__main__":
    main()
