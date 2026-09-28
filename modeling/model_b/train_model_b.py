"""모델 B v0.1.0 — 국민건강영양조사 2022–2024, 현재 고혈압 경계군(정상 vs 주의·전단계) (1사이클).

입력: $PAEON_DATA_DIR/KNHANES_2022_2024_selected.parquet (extract_selected.py 로 재추출)
출력: modeling/model_b/artifacts/
  - model_b_v0.1.0.json      로지스틱 계수 (원래 단위, paeon_models.predict_model_b 가 읽음)
  - model_b_xgb_v0.1.0.json  XGBoost 비교 모델
  - metrics_model_b.json     성능 기록
라벨: HE_HP 1→0, 2·3→1, 4 제외 (PRD REQ-PRED-009, NFR-ML-008). 혈압(HE_sbp·HE_dbp)은 피처 제외.
분할: 조사구(psu) 단위 — 같은 가구가 학습·테스트에 갈리지 않게 (계획 문서 §3.2)
"""
from pathlib import Path
import json
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupShuffleSplit, GroupKFold, StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, f1_score, confusion_matrix, brier_score_loss, roc_curve
import xgboost as xgb

# 데이터 위치: 환경변수 PAEON_DATA_DIR, 없으면 저장소 바깥의 `데이터/` (…/AI 웹서비스_final_project/데이터).
# 데이터는 이용 조건(질병관리청 원시자료 공개 규정 제8조) 때문에 저장소에 올리지 않음.
DATA_DIR = Path(os.environ.get("PAEON_DATA_DIR", Path(__file__).resolve().parents[3] / "데이터"))
DATA = DATA_DIR / "KNHANES_2022_2024_selected.parquet"
OUT = Path(__file__).resolve().parent / "artifacts"
VERSION = "0.1.0"
SEED = 42

# (피처, 화면 라벨, 개선 가능, 원본 변수, 기대 방향 +1 위험↑ / −1 위험↓ / 0 기대 없음)
# 학습된 계수 부호가 기대 방향과 반대면 direction_matches_expectation=False (알림용, 거르지 않음)
FEATS = [
    ("age", "나이", False, "age (80 = 80세 이상)", +1),
    ("male", "성별(남)", False, "sex 1=남", 0),
    ("bmi", "BMI", True, "HE_BMI", +1),
    ("waist", "허리둘레", True, "HE_wc", +1),
    ("parent_htn", "부모 고혈압 가족력", False, "HE_HPfh1·2 중 하나라도 1이면 1, 둘 다 0이면 0, 그 외 결측", +1),
    ("smoke_current", "현재 흡연", True, "BS3_1 1·2", +1),
    ("smoke_former", "과거 흡연", False, "BS3_1 3 (기준 = 8 피운 적 없음)", +1),
    ("drink_freq", "음주 빈도", True, "BD1_11 8→0, 1~6 그대로", +1),
    ("drink_amount", "한 번 음주량", True, "BD2_1 8→0, 1~5 그대로", +1),
    ("aerobic", "유산소 신체활동 실천", True, "pa_aerobic", -1),
    ("breakfast_skip", "아침 결식", True, "L_BR_FQ 1~4 (클수록 결식)", +1),
    ("eatout", "외식·배달 빈도", True, "8 − L_OUT_FQ (클수록 잦음)", +1),
]
F = [f[0] for f in FEATS]
BINARY = {"male", "parent_htn", "smoke_current", "smoke_former", "aerobic"}  # 기여도 기준점 = 0 (없음)
VALUE_LABELS = {k: {0: "없음", 1: "있음"} for k in BINARY} | {"male": {0: "여", 1: "남"}} | {
    "drink_freq": {0: "평생 안 마심", 1: "최근 1년 안 마심", 2: "월 1회 미만", 3: "월 1회", 4: "월 2–4회", 5: "주 2–3회", 6: "주 4회 이상"},
    "drink_amount": {0: "안 마심", 1: "1–2잔", 2: "3–4잔", 3: "5–6잔", 4: "7–9잔", 5: "10잔 이상"},
    "breakfast_skip": {1: "아침 주 5–7회", 2: "아침 주 3–4회", 3: "아침 주 1–2회", 4: "아침 거의 안 먹음"},
    "eatout": {1: "월 1회 미만", 2: "월 1–3회", 3: "주 1–2회", 4: "주 3–4회", 5: "주 5–6회", 6: "하루 1회", 7: "하루 2회 이상"},
}


def from_knhanes(d: pd.DataFrame) -> pd.DataFrame:
    """원본 코드 → 모델 피처 (paeon_models.features_b 와 같은 정의). 9 = 모름/무응답만 결측."""
    nan = np.nan
    fh1, fh2 = d["HE_HPfh1"], d["HE_HPfh2"]
    parent = np.where((fh1 == 1) | (fh2 == 1), 1.0, np.where((fh1 == 0) & (fh2 == 0), 0.0, nan))
    bs = d["BS3_1"].where(d["BS3_1"] != 9)
    return pd.DataFrame({
        "age": d["age"].clip(upper=80),
        "male": (d["sex"] == 1).astype(float),
        "bmi": d["HE_BMI"],
        "waist": d["HE_wc"],
        "parent_htn": parent,
        "smoke_current": bs.isin([1, 2]).astype(float).where(bs.notna()),
        "smoke_former": (bs == 3).astype(float).where(bs.notna()),
        "drink_freq": d["BD1_11"].where(d["BD1_11"] != 9).replace({8: 0}),
        "drink_amount": d["BD2_1"].where(d["BD2_1"] != 9).replace({8: 0}),
        "aerobic": d["pa_aerobic"],
        "breakfast_skip": d["L_BR_FQ"].where(d["L_BR_FQ"] != 9),
        "eatout": 8 - d["L_OUT_FQ"].where(d["L_OUT_FQ"] != 9),
    }, index=d.index)[F]


def metrics(y, p, thr):
    yhat = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat).ravel()
    return {"threshold": round(float(thr), 4), "auc": round(roc_auc_score(y, p), 4), "f1": round(f1_score(y, yhat), 4),
            "sensitivity": round(tp / (tp + fn), 4), "specificity": round(tn / (tn + fp), 4),
            "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}}


def youden(y, p):
    fpr, tpr, thr = roc_curve(y, p)
    return float(thr[np.argmax(tpr - fpr)])


def make_models():
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=5000))
    xg = make_pipeline(SimpleImputer(strategy="median"),
                       xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8,
                                         colsample_bytree=0.8, random_state=SEED, eval_metric="logloss"))
    return {"logistic": lr, "xgboost": xg}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_parquet(DATA)
    d = raw[(raw["age"] >= 19) & raw["HE_HP"].isin([1, 2, 3])].copy()
    y = d["HE_HP"].isin([2, 3]).astype(int)
    X, groups = from_knhanes(d), d["psu"]

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    tr, te = next(gss.split(X, y, groups))
    Xtr, Xte, ytr, yte, gtr = X.iloc[tr], X.iloc[te], y.iloc[tr], y.iloc[te], groups.iloc[tr]
    res = {"version": VERSION, "data": DATA.name, "population": "19세 이상, HE_HP 1·2·3",
           "n_total": len(d), "n_train": len(Xtr), "n_test": len(Xte), "psu_train": int(gtr.nunique()),
           "psu_test": int(groups.iloc[te].nunique()), "psu_overlap": int(len(set(gtr) & set(groups.iloc[te]))),
           "positive_rate_train": round(ytr.mean(), 4), "positive_rate_test": round(yte.mean(), 4),
           "missing_rate_train": {k: round(float(v), 4) for k, v in Xtr.isna().mean().items()},
           "features": F, "split": "조사구(psu) 단위 80/20 (seed 42) + 학습 데이터 GroupKFold 5", "models": {}}

    for name, m in make_models().items():
        cvs = cross_val_score(m, Xtr, ytr, cv=GroupKFold(5), groups=gtr, scoring="roc_auc")
        m.fit(Xtr, ytr)
        p = m.predict_proba(Xte)[:, 1]
        # 누수 점검용: 같은 모델을 무작위 분할로 학습했을 때 (조사구 무시)
        rXtr, rXte, rytr, ryte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
        rm = make_models()[name].fit(rXtr, rytr)
        res["models"][name] = {
            "cv_auc_mean": round(cvs.mean(), 4), "cv_auc_std": round(cvs.std(), 4),
            "test_at_0.5": metrics(yte, p, 0.5),
            "test_at_youden_train": metrics(yte, p, youden(ytr, m.predict_proba(Xtr)[:, 1])),
            "brier": round(brier_score_loss(yte, p), 4), "mean_pred_test": round(float(p.mean()), 4),
            "random_split_test_auc": round(roc_auc_score(ryte, rm.predict_proba(rXte)[:, 1]), 4),
        }
        if name == "logistic":
            lr = m
        else:
            booster = m.named_steps["xgbclassifier"].get_booster()
            contrib = booster.predict(xgb.DMatrix(m.named_steps["simpleimputer"].transform(Xte), feature_names=F),
                                      pred_contribs=True)[:, :-1]
            res["models"][name]["mean_abs_shap_test"] = dict(sorted(
                zip(F, map(lambda v: round(float(v), 4), np.abs(contrib).mean(0))), key=lambda kv: -kv[1]))
            m.named_steps["xgbclassifier"].save_model(OUT / f"model_b_xgb_v{VERSION}.json")

    imp, sc, clf = lr.named_steps["simpleimputer"], lr.named_steps["standardscaler"], lr.named_steps["logisticregression"]
    coef = clf.coef_[0] / sc.scale_
    # 로지스틱 기여도 = coef·(x − mean): 테스트 데이터 평균 |기여도|
    Xi = imp.transform(Xte)
    res["models"]["logistic"]["mean_abs_contribution_test"] = dict(sorted(
        zip(F, map(lambda v: round(float(v), 4), np.abs((Xi - sc.mean_) * coef).mean(0))), key=lambda kv: -kv[1]))
    res["models"]["logistic"]["odds_ratio_per_unit"] = {k: round(float(np.exp(c)), 4) for k, c in zip(F, coef)}
    spec = {
        "model_code": "MODEL_B", "version": VERSION,
        "target": "현재 고혈압 경계군(주의혈압·고혈압전단계)과 닮은 정도 (혈압 제외 특징으로 추정한 확률)",
        "label": "HE_HP 1→0, 2·3→1, 4 학습 제외",
        "formula": "p = 1 / (1 + exp(-(intercept + Σ coef·(x − mean))))",
        "contribution": "coef·(x − baseline). baseline = 있다/없다 요인은 0(없음), 숫자·단계 요인은 학습 데이터 평균",
        "intercept": round(float(clf.intercept_[0]), 6),
        "feats": [{"k": k, "label": lab, "coef": round(float(c), 6), "mean": round(float(mu), 6),
                   "impute": round(float(md), 6), "modifiable": mod, "source": src,
                   "expected_sign": exp, "direction_matches_expectation": bool(exp == 0 or np.sign(c) == exp),
                   "baseline": 0.0 if k in BINARY else round(float(mu), 6),
                   **({"value_labels": VALUE_LABELS[k]} if k in VALUE_LABELS else {})}
                  for (k, lab, mod, src, exp), c, mu, md in zip(FEATS, coef, sc.mean_, imp.statistics_)],
        "age_min": 19,
    }
    (OUT / f"model_b_v{VERSION}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2))
    (OUT / "metrics_model_b.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in res.items() if k != "missing_rate_train"}, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
