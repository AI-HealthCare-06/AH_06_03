const API_BASE = 'http://localhost:8000/v1';
const USE_MOCK = true;

async function apiSignup(email, password, birthDate) {
  if (USE_MOCK) {
    console.log('[MOCK] apiSignup', { email, birthDate });
    await sleep(400);
    return { data: { user_id: 'mock-user-1' } };
  }
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, birth_date: birthDate }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error?.message || '회원가입에 실패했습니다');
  return body;
}

async function apiLogin(email, password) {
  if (USE_MOCK) {
    console.log('[MOCK] apiLogin', { email });
    await sleep(300);
    return { data: { access_token: 'mock-token', refresh_token: 'mock-refresh' } };
  }
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error?.message || '로그인에 실패했습니다');
  return body;
}

async function apiSubmitHealthRecord(payload) {
  if (USE_MOCK) {
    console.log('[MOCK] apiSubmitHealthRecord', payload);
    await sleep(400);
    return { data: { health_record_id: 'mock-record-1' } };
  }
  const res = await fetch(`${API_BASE}/health/records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getAccessToken()}` },
    body: JSON.stringify(payload),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error?.message || '건강정보 저장에 실패했습니다');
  return body;
}

function getAccessToken() {
  try { return localStorage.getItem('paeon-access-token') || ''; } catch (e) { return ''; }
}

async function apiSubmitSurvey(payload) {
  if (USE_MOCK) {
    console.log('[MOCK] apiSubmitSurvey', payload);
    await sleep(400);
    return { data: { survey_instance_id: 'mock-survey-1' } };
  }
  const res = await fetch(`${API_BASE}/survey-instances`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getAccessToken()}` },
    body: JSON.stringify(payload),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error?.message || '설문 제출에 실패했습니다');
  return body;
}

const MODEL_A_FEATS = [
  { k: 'age', label: '나이', coef: 0.066053, mean: 49.663915, baseline: 49.663915, impute: 49.0, modifiable: false, dirOK: true },
  { k: 'male', label: '성별(남)', coef: 0.551428, mean: 0.428656, baseline: 0.0, impute: 0.0, modifiable: false, dirOK: true },
  { k: 'sysBP', label: '수축기혈압', coef: 0.014823, mean: 132.439858, baseline: 132.439858, impute: 128.0, modifiable: true, dirOK: true },
  { k: 'totChol', label: '총콜레스테롤', coef: 0.002373, mean: 236.670106, baseline: 236.670106, impute: 234.0, modifiable: true, dirOK: true },
  { k: 'currentSmoker', label: '흡연', coef: 0.386011, mean: 0.49204, baseline: 0.0, impute: 0.0, modifiable: true, dirOK: true },
  { k: 'diabetes', label: '당뇨', coef: 0.730864, mean: 0.025943, baseline: 0.0, impute: 0.0, modifiable: false, dirOK: true },
  { k: 'BPMeds', label: '혈압약 복용', coef: 0.445113, mean: 0.028302, baseline: 0.0, impute: 0.0, modifiable: false, dirOK: true },
  { k: 'prevalentHyp', label: '고혈압 진단', coef: 0.151593, mean: 0.310436, baseline: 0.0, impute: 0.0, modifiable: false, dirOK: true },
  { k: 'BMI', label: 'BMI', coef: 0.003351, mean: 25.824534, baseline: 25.824534, impute: 25.38, modifiable: true, dirOK: true },
];
const MODEL_A_INTERCEPT = -1.98072;

const MODEL_B_FEATS = [
  { k: 'age', label: '나이', coef: 0.039918, mean: 48.143845, baseline: 48.143845, impute: 48.0, modifiable: false, dirOK: true },
  { k: 'male', label: '성별(남)', coef: 0.750122, mean: 0.406597, baseline: 0.0, impute: 0.0, modifiable: false, dirOK: true },
  { k: 'bmi', label: 'BMI', coef: 0.085623, mean: 23.479185, baseline: 23.479185, impute: 23.096938, modifiable: true, dirOK: true },
  { k: 'waist', label: '허리둘레', coef: 0.026385, mean: 81.507209, baseline: 81.507209, impute: 81.1, modifiable: true, dirOK: true },
  { k: 'parent_htn', label: '부모 고혈압 가족력', coef: 0.32087, mean: 0.356949, baseline: 0.0, impute: 0.0, modifiable: false, dirOK: true },
  { k: 'smoke_current', label: '현재 흡연', coef: -0.24049, mean: 0.148039, baseline: 0.0, impute: 0.0, modifiable: true, dirOK: false },
  { k: 'smoke_former', label: '과거 흡연', coef: -0.399381, mean: 0.208683, baseline: 0.0, impute: 0.0, modifiable: false, dirOK: false },
  { k: 'drink_freq', label: '음주 빈도', coef: 0.026241, mean: 2.819995, baseline: 2.819995, impute: 3.0, modifiable: true, dirOK: true },
  { k: 'drink_amount', label: '한 번 음주량', coef: 0.108098, mean: 1.801292, baseline: 1.801292, impute: 1.0, modifiable: true, dirOK: true },
  { k: 'aerobic', label: '유산소 신체활동 실천', coef: 0.025881, mean: 0.460667, baseline: 0.0, impute: 0.0, modifiable: true, dirOK: false },
  { k: 'breakfast_skip', label: '아침 결식', coef: 0.001559, mean: 2.019497, baseline: 2.019497, impute: 1.0, modifiable: true, dirOK: true },
  { k: 'eatout', label: '외식·배달 빈도', coef: -0.045957, mean: 3.879619, baseline: 3.879619, impute: 4.0, modifiable: true, dirOK: false },
];
const MODEL_B_INTERCEPT = -0.768114;

function sigmoid(z) { return 1 / (1 + Math.exp(-z)); }
function contribs(feats, x) {
  return feats.map(f => ({ ...f, c: f.coef * ((x[f.k] == null ? f.impute : x[f.k]) - f.baseline) }));
}
function riskOf(feats, intercept, x) {
  const sum = feats.reduce((s, f) => s + f.coef * ((x[f.k] == null ? f.impute : x[f.k]) - f.mean), 0);
  return sigmoid(intercept + sum);
}
function band(r) {
  return r < 0.10 ? { code: 'normal', label: '정상' } : r <= 0.20 ? { code: 'borderline', label: '경계' } : { code: 'high', label: '위험' };
}
function vascularAge(x) {
  const c = contribs(MODEL_A_FEATS, x).filter(f => f.k !== 'age' && f.k !== 'male').reduce((s, f) => s + f.c, 0);
  return Math.max(20, Math.min(90, x.age + c / 0.066053));
}
function bpStage(sbp, dbp) {
  if (sbp >= 140 || dbp >= 90) return 'hypertension';
  if (sbp >= 130 || dbp >= 80) return 'prehypertension';
  if (sbp >= 120) return 'elevated';
  return 'normal';
}
function ageFromBirth(birthDateStr) {
  const birth = new Date(birthDateStr);
  const now = new Date('2026-09-29');
  let age = now.getFullYear() - birth.getFullYear();
  if (now < new Date(now.getFullYear(), birth.getMonth(), birth.getDate())) age--;
  return age;
}
function topFactors(feats, x, minAbs) {
  return contribs(feats, x).filter(f => f.k !== 'male' && Math.abs(f.c) > minAbs).sort((p, q) => q.c - p.c);
}

function buildXA(profile, health) {
  const bmi = health.weight_kg / Math.pow(health.height_cm / 100, 2);
  return {
    age: ageFromBirth(profile.birth), male: health.sex === 'male' ? 1 : 0,
    sysBP: health.sbp, totChol: health.total_chol,
    currentSmoker: health.smoking === 'current' ? 1 : 0, diabetes: health.diabetes ? 1 : 0,
    BPMeds: health.htn_status === 'treated' ? 1 : 0, prevalentHyp: health.htn_status !== 'none' ? 1 : 0, BMI: bmi,
  };
}
const EATOUT_LEGACY_NUM = { '2plus_per_day': 7, '1_per_day': 6, '5_6_per_week': 5, '3_4_per_week': 4, '1_2_per_week': 3, '1_3_per_month': 2, lt_monthly: 1 };
const BREAKFAST_LEGACY_NUM = { '5_7': 1, '3_4': 2, '1_2': 3, '0': 4 };

function buildXB(profile, health, survey) {
  const bmi = health.weight_kg / Math.pow(health.height_cm / 100, 2);
  const drinkFreqIdx = { never_lifetime: 0, none_past_year: 1, lt_monthly: 2, monthly: 3, '2_4_per_month': 4, '2_3_per_week': 5, '4plus_per_week': 6 }[health.drink_freq] ?? 0;
  const drinkAmountIdx = { '1_2': 1, '3_4': 2, '5_6': 3, '7_9': 4, '10plus': 5 }[health.drink_amount] ?? 0;
  return {
    age: ageFromBirth(profile.birth), male: health.sex === 'male' ? 1 : 0, bmi, waist: health.waist_cm,
    parent_htn: health.parent_htn === 'yes' ? 1 : 0,
    smoke_current: health.smoking === 'current' ? 1 : 0, smoke_former: health.smoking === 'former' ? 1 : 0,
    drink_freq: drinkFreqIdx, drink_amount: drinkAmountIdx,
    aerobic: survey.aerobic, breakfast_skip: BREAKFAST_LEGACY_NUM[survey.breakfast] ?? 2, eatout: EATOUT_LEGACY_NUM[survey.eatout] ?? 4,
  };
}

async function apiRequestPrediction(profile, elig, health, survey) {
  if (!USE_MOCK) {
    const res = await fetch(`${API_BASE}/predictions/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getAccessToken()}` },
      body: JSON.stringify({ health_record_id: health.health_record_id, request_type: 'auto' }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error?.message || '예측 요청에 실패했습니다');
    return body;
  }

  console.log('[MOCK] apiRequestPrediction', { profile, elig, health, survey });
  await sleep(500);

  const stage = bpStage(health.sbp, health.dbp);
  const skipAReason = elig.ageBand !== 'in' ? 'age_out_of_range' : elig.chd ? 'cad_diagnosed' : null;
  const skipBReason = elig.ageBand === 'under19' ? 'age_out_of_range' : health.htn_status !== 'none' ? 'htn_diagnosed' : null;

  let modelA = null;
  if (!skipAReason) {
    const xA = buildXA(profile, health);
    const r = riskOf(MODEL_A_FEATS, MODEL_A_INTERCEPT, xA);
    modelA = { risk_level: band(r).code, risk_label: band(r).label, vascular_age: Math.round(vascularAge(xA)), factors: topFactors(MODEL_A_FEATS, xA, 0.004) };
  }

  let modelB = null;
  if (!skipBReason) {
    const xB = buildXB(profile, health, survey);
    const r = riskOf(MODEL_B_FEATS, MODEL_B_INTERCEPT, xB);
    modelB = { probability: r, factors: topFactors(MODEL_B_FEATS, xB, 0.004) };
  }

  return { data: { bp_stage: stage, htn_status: health.htn_status, model_a: modelA, model_a_skip_reason: skipAReason, model_b: modelB, model_b_skip_reason: skipBReason } };
}

// 혜림님 임시 창구(POST /v1/predict) 전용 — 정식 /predictions/jobs 생기면 지울 예정.
// 요청 필드는 modeling/handoff/모델_연결_명세.md §1과 글자 하나까지 동일해야 함.
function buildPredictV1Payload(profile, health, survey) {
  const isDrinker = !['', 'never_lifetime', 'none_past_year'].includes(health.drink_freq);
  return {
    age: ageFromBirth(profile.birth),
    sex: health.sex === 'male' ? 'M' : 'F',
    height_cm: health.height_cm,
    weight_kg: health.weight_kg,
    waist_cm: health.waist_cm,
    sbp: health.sbp,
    dbp: health.dbp,
    total_chol: health.total_chol,
    smoking: health.smoking,
    diabetes: health.diabetes,
    htn_status: health.htn_status,
    parent_htn: health.parent_htn,
    drink_freq: health.drink_freq,
    drink_amount: isDrinker ? health.drink_amount : null,
    breakfast: survey.breakfast,
    eatout: survey.eatout,
    aerobic: survey.aerobic,
  };
}

async function apiPredictV1Temp(profile, health, survey) {
  const res = await fetch(`${API_BASE}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildPredictV1Payload(profile, health, survey)),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(Array.isArray(body.detail) ? body.detail.map(d => `${d.loc?.join('.')}: ${d.msg}`).join(', ') : (body.detail || '예측 요청에 실패했습니다'));
  return body;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
