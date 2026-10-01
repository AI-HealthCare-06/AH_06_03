// 모델 A v0.1.1 — artifacts JSON에서 자동 생성. 계수·평균은 원래 단위. 결측이면 impute 값 사용
// 확률: p = σ(INTERCEPT + Σ coef·(x − mean)) / 기여도: coef·(x − baseline), 0이면 '해당 없음'으로 표시 안 함
const MODEL_A_FEATS = [
  {k:'age', fixed:true, label:'나이', coef:0.066053, mean:49.663915, baseline:49.663915, impute:49.0, modifiable:false, dirOK:true, valueLabels:null},
  {k:'male', fixed:true, label:'성별(남)', coef:0.551428, mean:0.428656, baseline:0.0, impute:0.0, modifiable:false, dirOK:true, valueLabels:{"0": "여", "1": "남"}},
  {k:'sysBP', label:'수축기혈압', coef:0.014823, mean:132.439858, baseline:132.439858, impute:128.0, modifiable:true, dirOK:true, valueLabels:null},
  {k:'totChol', label:'총콜레스테롤', coef:0.002373, mean:236.670106, baseline:236.670106, impute:234.0, modifiable:true, dirOK:true, valueLabels:null},
  {k:'currentSmoker', label:'흡연', coef:0.386011, mean:0.49204, baseline:0.0, impute:0.0, modifiable:true, dirOK:true, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'diabetes', label:'당뇨', coef:0.730864, mean:0.025943, baseline:0.0, impute:0.0, modifiable:false, dirOK:true, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'BPMeds', label:'혈압약 복용', coef:0.445113, mean:0.028302, baseline:0.0, impute:0.0, modifiable:false, dirOK:true, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'prevalentHyp', label:'고혈압 진단', coef:0.151593, mean:0.310436, baseline:0.0, impute:0.0, modifiable:false, dirOK:true, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'BMI', label:'BMI', coef:0.003351, mean:25.824534, baseline:25.824534, impute:25.38, modifiable:true, dirOK:true, valueLabels:null},
];
const MODEL_A_INTERCEPT = -1.98072;
const MODEL_A_AGE_COEF = 0.066053;  // 혈관 나이: age + Σ(fixed 아닌 요인 coef·(x − mean)) / AGE_COEF, 20~90 (데모 vascAge 식과 같음)

// 모델 B v0.1.0 — artifacts JSON에서 자동 생성. 계수·평균은 원래 단위. 결측이면 impute 값 사용
// 확률: p = σ(INTERCEPT + Σ coef·(x − mean)) / 기여도: coef·(x − baseline), 0이면 '해당 없음'으로 표시 안 함
const MODEL_B_FEATS = [
  {k:'age', label:'나이', coef:0.039918, mean:48.143845, baseline:48.143845, impute:48.0, modifiable:false, dirOK:true, valueLabels:null},
  {k:'male', label:'성별(남)', coef:0.750122, mean:0.406597, baseline:0.0, impute:0.0, modifiable:false, dirOK:true, valueLabels:{"0": "여", "1": "남"}},
  {k:'bmi', label:'BMI', coef:0.085623, mean:23.479185, baseline:23.479185, impute:23.096938, modifiable:true, dirOK:true, valueLabels:null},
  {k:'waist', label:'허리둘레', coef:0.026385, mean:81.507209, baseline:81.507209, impute:81.1, modifiable:true, dirOK:true, valueLabels:null},
  {k:'parent_htn', label:'부모 고혈압 가족력', coef:0.32087, mean:0.356949, baseline:0.0, impute:0.0, modifiable:false, dirOK:true, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'smoke_current', label:'현재 흡연', coef:-0.24049, mean:0.148039, baseline:0.0, impute:0.0, modifiable:true, dirOK:false, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'smoke_former', label:'과거 흡연', coef:-0.399381, mean:0.208683, baseline:0.0, impute:0.0, modifiable:false, dirOK:false, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'drink_freq', label:'음주 빈도', coef:0.026241, mean:2.819995, baseline:2.819995, impute:3.0, modifiable:true, dirOK:true, valueLabels:{"0": "평생 안 마심", "1": "최근 1년 안 마심", "2": "월 1회 미만", "3": "월 1회", "4": "월 2–4회", "5": "주 2–3회", "6": "주 4회 이상"}},
  {k:'drink_amount', label:'한 번 음주량', coef:0.108098, mean:1.801292, baseline:1.801292, impute:1.0, modifiable:true, dirOK:true, valueLabels:{"0": "안 마심", "1": "1–2잔", "2": "3–4잔", "3": "5–6잔", "4": "7–9잔", "5": "10잔 이상"}},
  {k:'aerobic', label:'유산소 신체활동 실천', coef:0.025881, mean:0.460667, baseline:0.0, impute:0.0, modifiable:true, dirOK:false, valueLabels:{"0": "없음", "1": "있음"}},
  {k:'breakfast_skip', label:'아침 결식', coef:0.001559, mean:2.019497, baseline:2.019497, impute:1.0, modifiable:true, dirOK:true, valueLabels:{"1": "아침 주 5–7회", "2": "아침 주 3–4회", "3": "아침 주 1–2회", "4": "아침 거의 안 먹음"}},
  {k:'eatout', label:'외식·배달 빈도', coef:-0.045957, mean:3.879619, baseline:3.879619, impute:4.0, modifiable:true, dirOK:false, valueLabels:{"1": "월 1회 미만", "2": "월 1–3회", "3": "주 1–2회", "4": "주 3–4회", "5": "주 5–6회", "6": "하루 1회", "7": "하루 2회 이상"}},
];
const MODEL_B_INTERCEPT = -0.768114;
