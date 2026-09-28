"""모델 A v0.1.0 — Framingham 10년 관상동맥질환(TenYearCHD), 보정 없음 (첫 번째 사이클).

입력: $PAEON_DATA_DIR/framingham.csv
출력: modeling/model_a/artifacts/
  - model_a_v0.1.0.json   로지스틱 계수 (데모 FEATS 형식: coef·mean + intercept, 원래 단위)
  - model_a_xgb_v0.1.0.json  XGBoost 비교 모델
  - metrics_model_a.json  성능 기록 (NFR-ML-003)
피처는 PRD REQ-HEALTH-002 입력 항목에서 받을 수 있는 것만 사용.
  HDL: Framingham에 없음 / glucose: 수시 혈당이라 한국 공복혈당과 다름 → 첫 번째 사이클 제외
"""
from pathlib import Path
import json
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, f1_score, confusion_matrix, brier_score_loss
import xgboost as xgb

# 데이터 위치: 환경변수 PAEON_DATA_DIR, 없으면 저장소 바깥의 `데이터/` (…/AI 웹서비스_final_project/데이터).
# 데이터는 이용 조건(질병관리청 원시자료 공개 규정 제8조) 때문에 저장소에 올리지 않음.
DATA_DIR = Path(os.environ.get("PAEON_DATA_DIR", Path(__file__).resolve().parents[3] / "데이터"))
DATA = DATA_DIR / "framingham.csv"
OUT = Path(__file__).resolve().parent / "artifacts"
VERSION = "0.1.0"
SEED = 42

# (피처, 화면 라벨, 개선 가능 여부, PRD 입력 항목)
FEATS = [
    ("age", "나이", False, "프로필 나이"),
    ("male", "성별(남)", False, "프로필 성별"),
    ("sysBP", "수축기혈압", True, "수축기혈압 mmHg"),
    ("totChol", "총콜레스테롤", True, "총콜레스테롤 mg/dL"),
    ("currentSmoker", "흡연", True, "흡연 여부"),
    ("diabetes", "당뇨", False, "당뇨병 여부"),
    ("BPMeds", "혈압약 복용", False, "고혈압 진단·치료 상태 = 약 복용 중"),
    ("prevalentHyp", "고혈압 진단", False, "고혈압 진단·치료 상태 ≠ 진단 없음"),
    ("BMI", "BMI", True, "신장·체중 → 서버 계산"),
]
F = [f[0] for f in FEATS]
LABEL = "TenYearCHD"
BINARY = {"male", "currentSmoker", "diabetes", "BPMeds", "prevalentHyp"}  # 기여도 기준점 = 0 (없음)
VALUE_LABELS = {k: {0: "없음", 1: "있음"} for k in BINARY} | {"male": {0: "여", 1: "남"}}
BANDS = [(0.10, "정상"), (0.20, "경계"), (1.01, "위험")]  # 데모 코드 기준 (r<0.10 / r<=0.20 / 그 외)


def band(p):
    if p < 0.10:
        return "정상"
    return "경계" if p <= 0.20 else "위험"


def metrics(y, p, thr):
    yhat = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat).ravel()
    return {"threshold": thr, "auc": round(roc_auc_score(y, p), 4), "f1": round(f1_score(y, yhat), 4),
            "sensitivity": round(tp / (tp + fn), 4), "specificity": round(tn / (tn + fp), 4),
            "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}}


def youden(y, p):
    from sklearn.metrics import roc_curve
    fpr, tpr, thr = roc_curve(y, p)
    return float(thr[np.argmax(tpr - fpr)])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA)
    X, y = df[F], df[LABEL]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)

    # 로지스틱회귀: 중앙값 대체 → 표준화 → LR (전처리는 학습 데이터에만 fit, NFR-ML-001)
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=5000))
    xg = make_pipeline(SimpleImputer(strategy="median"),
                       xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8,
                                         colsample_bytree=0.8, random_state=SEED, eval_metric="logloss"))
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    res = {"version": VERSION, "data": "framingham.csv", "n_total": len(df), "n_train": len(Xtr), "n_test": len(Xte),
           "positive_rate_train": round(ytr.mean(), 4), "positive_rate_test": round(yte.mean(), 4),
           "features": F, "split": "층화 무작위 80/20 (seed 42) + 학습 데이터 5-fold CV", "models": {}}
    for name, m in [("logistic", lr), ("xgboost", xg)]:
        cvs = cross_val_score(m, Xtr, ytr, cv=cv, scoring="roc_auc")
        m.fit(Xtr, ytr)
        p = m.predict_proba(Xte)[:, 1]
        thr_y = youden(ytr, m.predict_proba(Xtr)[:, 1])
        bands = pd.DataFrame({"b": [band(v) for v in p], "y": yte.values}).groupby("b")["y"].agg(["size", "mean"])
        res["models"][name] = {
            "cv_auc_mean": round(cvs.mean(), 4), "cv_auc_std": round(cvs.std(), 4),
            "test_at_0.5": metrics(yte, p, 0.5), "test_at_youden_train": metrics(yte, p, round(thr_y, 4)),
            "brier": round(brier_score_loss(yte, p), 4), "mean_pred_test": round(p.mean(), 4),
            "bands_test": {b: {"n": int(r["size"]), "observed_rate": round(r["mean"], 4)} for b, r in bands.iterrows()},
        }

    # 로지스틱 계수를 원래 단위로 변환: logit = b0 + Σ w·(x−μ)/σ = INTERCEPT + Σ coef·(x−mean)
    imp, sc, clf = lr.named_steps["simpleimputer"], lr.named_steps["standardscaler"], lr.named_steps["logisticregression"]
    coef = clf.coef_[0] / sc.scale_
    spec = {
        "model_code": "MODEL_A", "version": VERSION, "target": "10년 내 관상동맥질환(TenYearCHD) 발생 확률",
        "calibration": "없음 (미국 1950–60년대 데이터 그대로. 한국인 위험이 높게 나옴)",
        "formula": "p = 1 / (1 + exp(-(intercept + Σ coef·(x − mean))))",
        "contribution": "coef·(x − baseline). baseline = 있다/없다 요인은 0(없음), 숫자 요인은 학습 데이터 평균",
        "intercept": round(float(clf.intercept_[0]), 6),
        "feats": [{"k": k, "label": lab, "coef": round(float(c), 6), "mean": round(float(mu), 6),
                   "impute": round(float(md), 6), "modifiable": mod, "input": src,
                   "direction_matches_expectation": bool(c > 0),
                   "baseline": 0.0 if k in BINARY else round(float(mu), 6),
                   **({"value_labels": VALUE_LABELS[k]} if k in VALUE_LABELS else {})}
                  for (k, lab, mod, src), c, mu, md in zip(FEATS, coef, sc.mean_, imp.statistics_)],
        "bands": {"정상": "p < 0.10", "경계": "0.10 ≤ p ≤ 0.20", "위험": "p > 0.20", "source": "데모 코드 기준 (첫 번째 사이클 잠정)"},
        "age_range": [32, 70],
    }
    (OUT / f"model_a_v{VERSION}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2))
    xg.named_steps["xgbclassifier"].save_model(OUT / f"model_a_xgb_v{VERSION}.json")
    res["xgb_impute_medians"] = dict(zip(F, map(float, xg.named_steps["simpleimputer"].statistics_)))
    (OUT / "metrics_model_a.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(res["models"], ensure_ascii=False, indent=1, default=float))
    print(json.dumps(spec["feats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
