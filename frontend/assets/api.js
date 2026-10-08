// 로컬(5500 포트)에서 열면 내 컴퓨터 서버, 아니면 배포 서버
const API_BASE = ['5500'].includes(location.port) ? 'http://127.0.0.1:8000/v1' : 'https://54-116-113-17.sslip.io/v1';
const USE_MOCK = true;
// predict·auth·health·survey는 서버 연결됨. USE_MOCK(OCR 등 아직 서버 없는 것)만 true
const USE_MOCK_PREDICT = false;
const USE_MOCK_AUTH = false;
const USE_MOCK_HEALTH = false;
const USE_MOCK_SURVEY = false;
const SEND_ECIG = false; // 혜림님이 ECIG 지표를 열면 true

function friendlyError(e) { return e instanceof TypeError ? '서버 연결에 실패했어요. 잠시 후 다시 시도해주세요.' : e.message; }

// opts.guardian = { name, relation, contact } — 만 14세 미만만. relation은 "parent" | "legal_guardian".
async function apiSignup(email, password, birthDate, opts = {}) {
  if (USE_MOCK_AUTH || opts.forceMock) {
    console.log('[MOCK] apiSignup', { email, birthDate, guardian: opts.guardian, forceMock: !!opts.forceMock });
    await sleep(400);
    return { data: { user_id: 'mock-user-1', guardian_verification_status: opts.guardian ? 'pending' : null } };
  }
  const payload = { email, password, birth_date: birthDate };
  if (opts.guardian) {
    payload.guardian_name = opts.guardian.name;
    payload.guardian_relation = opts.guardian.relation;
    payload.guardian_contact = opts.guardian.contact;
  }
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error?.message || '회원가입에 실패했습니다');
  return body;
}

async function apiLogin(email, password) {
  if (USE_MOCK_AUTH) {
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

// 로그인이 필요한 요청 공통 창구. 팔찌 만료(401 AUTH_TOKEN_EXPIRED)면 재발급 후 원래 요청을 한 번 다시 보낸다.
let refreshing = null; // 동시에 여러 요청이 만료돼도 재발급은 한 번만 (쓴 쿠폰은 버려지므로)

function goLogin() {
  try { localStorage.removeItem('paeon-access-token'); localStorage.removeItem('paeon-refresh-token'); } catch (e) {}
  location.href = 'login.html';
  return new Promise(() => {}); // 이동 중에는 호출한 쪽이 에러를 띄우지 않게 멈춰 둔다
}

function refreshTokens() {
  if (!refreshing) {
    refreshing = (async () => {
      const refresh_token = localStorage.getItem('paeon-refresh-token') || '';
      const res = await fetch(`${API_BASE}/auth/token/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token }),
      });
      if (!res.ok) return false;
      const { data } = await res.json();
      localStorage.setItem('paeon-access-token', data.access_token);
      localStorage.setItem('paeon-refresh-token', data.refresh_token); // 쿠폰도 새로 오므로 꼭 교체
      return true;
    })().catch(() => false).finally(() => { refreshing = null; });
  }
  return refreshing;
}

// 건강정보 동의를 철회한 사람이 건강정보·설문·예측을 쓰면 서버가 403(CONSENT_WITHDRAWN)을 준다. 화면 위에 안내를 띄우고 마이페이지로 이어 준다.
function showConsentBanner(message) {
  if (typeof document === 'undefined' || document.getElementById('consent-banner')) return;
  const show = () => {
    const b = document.createElement('div');
    b.id = 'consent-banner';
    b.style.cssText = 'position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:9999;max-width:min(92vw,520px);background:#FBEAE5;border:1.5px solid var(--danger,#C97B6B);border-radius:14px;padding:12px 16px;font-size:13px;line-height:1.5;box-shadow:0 6px 20px rgba(0,0,0,.15)';
    b.innerHTML = `<b>건강정보 동의를 철회한 상태예요</b><br>${message || '다시 동의하면 이어서 이용할 수 있어요.'} <a href="mypage.html" style="font-weight:700;text-decoration:underline">마이페이지에서 다시 동의하기</a> <button type="button" aria-label="닫기" style="float:right;border:0;background:none;font-size:16px;cursor:pointer" onclick="this.parentNode.remove()">×</button>`;
    document.body.appendChild(b);
  };
  document.body ? show() : document.addEventListener('DOMContentLoaded', show);
}

async function apiCall(method, path, payload, failMsg, retried = false) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getAccessToken()}` },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (res.status === 204) return null;
  const body = await res.json();
  if (!res.ok) {
    const code = body.error?.code;
    if (code === 'AUTH_TOKEN_EXPIRED' && !retried) {
      if (await refreshTokens()) return apiCall(method, path, payload, failMsg, true);
      return goLogin();
    }
    if (code === 'AUTH_UNAUTHORIZED' || code === 'AUTH_TOKEN_EXPIRED' || code === 'AUTH_INVALID_REFRESH_TOKEN') return goLogin();
    if (code === 'CONSENT_WITHDRAWN') showConsentBanner();
    const err = new Error(body.error?.message || failMsg);
    err.code = code;
    throw err;
  }
  return body;
}

// 건강기록 3단계 저장: 성별(PATCH users/me) → 기록 상자(POST records) → 측정값(POST measurements)
async function apiSubmitHealthRecord(payload) {
  if (USE_MOCK_HEALTH) {
    console.log('[MOCK] apiSubmitHealthRecord', payload);
    await sleep(400);
    return { data: { health_record_id: 'mock-record-1' } };
  }
  const num = (code, v) => ({ metric_code: code, value_num: v });
  const cat = (code, v) => ({ metric_code: code, value_code: String(v) });
  const measurements = [
    num('SBP', payload.sbp), num('DBP', payload.dbp),
    num('HEIGHT', payload.height_cm), num('WEIGHT', payload.weight_kg), num('WAIST', payload.waist_cm),
    num('TOTAL_CHOL', payload.total_chol), num('HDL', payload.hdl),
    cat('SMOKING', payload.smoking), cat('DIABETES', payload.diabetes),
    cat('HTN_STATUS', payload.htn_status), cat('PARENT_HTN', payload.parent_htn),
    cat('ALCOHOL_FREQ', payload.drink_freq),
  ];
  if (payload.drink_amount) measurements.push(cat('ALCOHOL_AMOUNT', payload.drink_amount));
  if (SEND_ECIG && payload.ecig) measurements.push(cat('ECIG', payload.ecig)); // 서버가 ECIG 지표를 받기 전에는 422(HEALTH_METRIC_UNKNOWN)
  if (payload.fasting_glucose != null) measurements.push(num('FASTING_GLUCOSE', payload.fasting_glucose));

  const date = payload.recorded_at.slice(0, 10);
  await apiCall('PATCH', '/users/me', { sex: payload.sex }, '성별 저장에 실패했습니다');

  // 같은 날 같은 종류의 기록이 이미 있으면(409) 목록에서 찾아 다시 쓴다. 같은 지표를 다시 보내면 서버가 새 값으로 바꿔 준다.
  const recordIdFor = async (inputType) => {
    try {
      return (await apiCall('POST', '/health/records', { input_type: inputType, examination_date: date }, '건강기록 생성에 실패했습니다')).data.health_record_id;
    } catch (e) {
      if (e.code !== 'HEALTH_RECORD_DUPLICATED') throw e;
      const list = (await apiCall('GET', '/health/records', undefined, '건강기록 목록을 불러오지 못했습니다')).data;
      const found = list.find(r => r.input_type === inputType && r.examination_date === date);
      if (!found) throw e;
      return found.health_record_id;
    }
  };
  const save = (id) => apiCall('POST', `/health/records/${id}/measurements`, { measurements }, '건강정보 저장에 실패했습니다');

  let id = await recordIdFor('initial');
  let res;
  try {
    res = await save(id);
  } catch (e) {
    if (e.code !== 'HEALTH_RECORD_LOCKED') throw e;
    // 이미 예측에 쓴 기록은 서버가 잠가서 못 고친다 → 오늘 날짜의 직접 입력(manual) 기록에 새로 저장
    id = await recordIdFor('manual');
    try {
      res = await save(id);
    } catch (e2) {
      if (e2.code === 'HEALTH_RECORD_LOCKED') throw new Error('오늘 입력한 기록은 이미 분석에 사용돼서 더 고칠 수 없어요. 내일 다시 입력해주세요.');
      throw e2;
    }
  }
  try { localStorage.setItem('paeon-health-record-id', id); } catch (e) {}
  return { data: { health_record_id: id } };
}

// 검진 결과지 사진 → Clova OCR → OpenAI 구조화. 혜림님이 백엔드 엔드포인트 만들면 USE_MOCK 끄기.
async function apiOcrHealthRecord(file) {
  if (USE_MOCK) {
    console.log('[MOCK] apiOcrHealthRecord', file && file.name);
    await sleep(1200);
    return {
      data: {
        fields: { height_cm: 172, weight_kg: 78, waist_cm: 88, sbp: 138, dbp: 86, total_chol: 210, hdl: 44 },
        missing: ['fasting_glucose'],
      },
    };
  }
  const form = new FormData();
  form.append('image', file);
  const res = await fetch(`${API_BASE}/health/records/ocr`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${getAccessToken()}` },
    body: form,
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error?.message || '인식에 실패했습니다');
  return body;
}

function getAccessToken() {
  try { return localStorage.getItem('paeon-access-token') || ''; } catch (e) { return ''; }
}

// 설문 제출: 설문지 조회 → 답안지 시작 → 답 저장 → 내기.
// - 서버가 설문 v2(문항 코드 N0..)를 열면 문항 코드 → 보기 코드(option_code)로 맞춰 보낸다. 보기 코드는 가이드 §1.2의 코드 문자열(N 문항은 점수 문자열)을 쓴다고 가정.
// - 서버가 아직 v1(BREAKFAST·EATOUT·AEROBIC 필수 3문항)이면 세 문항에 모두 답했을 때만 v1 코드로 바꿔 보낸다. 건너뛴 게 있으면 서버 제출은 생략(예측은 그대로 진행).
const SCALE5_CODES = ['never', 'slightly', 'moderate', 'much', 'very'];
const FREQ5_CODES = ['le3_month', '1_2_week', '3_6_week', '1_day', '2_3_day'];
const SCORE_UP = ['2', '4', '6', '8', '10'], SCORE_DOWN = ['10', '8', '6', '4', '2'];
const N_MAP = {                                    // 문항 → { codes: 서버 보기 코드, scores: 화면 값 }
  N0: { codes: ['bland', 'slightly_bland', 'normal', 'slightly_salty', 'salty'], scores: ['10', '20', '30', '40', '50'] },
  N1: { codes: SCALE5_CODES, scores: SCORE_UP }, N2: { codes: SCALE5_CODES, scores: SCORE_UP }, N3: { codes: SCALE5_CODES, scores: SCORE_UP },
  N4: { codes: SCALE5_CODES, scores: SCORE_DOWN }, N5: { codes: SCALE5_CODES, scores: SCORE_DOWN },
  N6: { codes: FREQ5_CODES, scores: SCORE_UP }, N7: { codes: FREQ5_CODES, scores: SCORE_UP }, N8: { codes: FREQ5_CODES, scores: SCORE_UP },
  N9: { codes: FREQ5_CODES, scores: SCORE_DOWN }, N10: { codes: FREQ5_CODES, scores: SCORE_DOWN },
};
const scoreToServerCode = (q, v) => { const m = N_MAP[q]; return m ? m.codes[m.scores.indexOf(String(v))] : v; };
const serverCodeToScore = (q, c) => { const m = N_MAP[q]; return m && m.codes.includes(c) ? m.scores[m.codes.indexOf(c)] : c; };
const EATOUT_V1 = { rare: 'lt_monthly', '1_2_week': '1_2_per_week', '3_4_week': '3_4_per_week', '5_6_week': '5_6_per_week', '1_day': '1_per_day', '2plus_day': '2plus_per_day' };
async function apiSubmitSurvey(payload) {
  if (USE_MOCK_SURVEY) {
    console.log('[MOCK] apiSubmitSurvey', payload);
    await sleep(400);
    return { data: { survey_instance_id: 'mock-survey-1' } };
  }
  const survey = (await apiCall('GET', '/surveys/initial_lifestyle/active', undefined, '설문을 불러오지 못했습니다')).data;
  const isV2 = survey.questions.some(q => q.question_code === 'N0');
  const a = payload.answers || {};
  const want = isV2
    ? { N0: a.N0, N1: a.N1, N2: a.N2, N3: a.N3, N4: a.N4, N5: a.N5, N6: a.N6, N7: a.N7, N8: a.N8, N9: a.N9, N10: a.N10,
        P1: a.P1, E1: a.E1, B1: a.B1, BP_MEASURE_METHOD: a.BPM }
    : { BREAKFAST: a.B1, EATOUT: a.E1 ? EATOUT_V1[a.E1] : undefined, AEROBIC: a.P1 ? (a.P1 === '150plus' ? 'yes' : 'no') : undefined };
  const responses = [];
  for (const q of survey.questions) {
    if (isV2 && q.question_code === 'P2') {            // 숫자 문항(걸음 수)
      const steps = payload.baseline_steps;
      if (steps != null && steps !== '' && !isNaN(Number(steps))) responses.push({ question_id: q.question_id, value_num: Number(steps) });
      continue;
    }
    let code = want[q.question_code];
    if (code == null) continue;                       // 건너뛴 문항
    if (isV2) code = scoreToServerCode(q.question_code, code);
    const opt = q.options.find(o => o.option_code === String(code));
    if (!opt) throw new Error('설문 보기를 찾지 못했습니다. 잠시 후 다시 시도해주세요.');
    responses.push({ question_id: q.question_id, option_id: opt.option_id });
  }
  if (!isV2 && responses.length < survey.questions.filter(q => q.required).length) {
    return { data: { skipped: true } };               // v1은 필수 3문항이라 건너뛴 게 있으면 제출할 수 없음
  }
  if (!responses.length) return { data: { skipped: true } };
  const recordId = (() => { try { return localStorage.getItem('paeon-health-record-id'); } catch (e) { return null; } })();
  const inst = (await apiCall('POST', '/survey-instances',
    { survey_version_id: survey.survey_version_id, health_record_id: recordId }, '설문을 시작하지 못했습니다')).data;
  const base = `/survey-instances/${inst.survey_instance_id}`;
  try { localStorage.setItem('paeon-survey-instance-id', inst.survey_instance_id); } catch (e) {}
  await apiCall('POST', `${base}/responses`, { responses }, '설문 저장에 실패했습니다');
  return apiCall('POST', `${base}/submit`, undefined, '설문 제출에 실패했습니다');
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
  return feats.map(f => ({ ...f, contribution: f.coef * ((x[f.k] == null ? f.impute : x[f.k]) - f.baseline), direction_matches_expectation: f.dirOK }));
}
function riskOf(feats, intercept, x) {
  const sum = feats.reduce((s, f) => s + f.coef * ((x[f.k] == null ? f.impute : x[f.k]) - f.mean), 0);
  return sigmoid(intercept + sum);
}
function band(r) {
  return r < 0.10 ? { code: 'normal', label: '정상' } : r <= 0.20 ? { code: 'borderline', label: '경계' } : { code: 'high', label: '위험' };
}
const MODEL_A_AGE_COEF = 0.066053;
function vascularAge(x) {
  const sum = contribs(MODEL_A_FEATS, x).filter(f => f.k !== 'age' && f.k !== 'male').reduce((s, f) => s + f.contribution, 0);
  return Math.max(20, Math.min(90, x.age + sum / MODEL_A_AGE_COEF));
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
  return contribs(feats, x).filter(f => f.k !== 'male' && Math.abs(f.contribution) > minAbs).sort((p, q) => q.contribution - p.contribution);
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
  const stage = bpStage(health.sbp, health.dbp);

  if (!USE_MOCK_PREDICT) {
    const body = await apiPredictionJob();
    return { data: { ...body.data, bp_stage: stage, htn_status: health.htn_status } };
  }

  console.log('[MOCK] apiRequestPrediction', { profile, elig, health, survey });
  await sleep(500);

  const skipAReason = elig.ageBand !== 'in' ? 'age_out_of_range' : elig.chd ? 'cad_diagnosed' : null;
  const skipBReason = elig.ageBand === 'under19' ? 'age_out_of_range' : health.htn_status !== 'none' ? 'htn_diagnosed' : null;

  let modelA;
  if (skipAReason) {
    modelA = { status: 'skipped', skip_reason: skipAReason, factors: [] };
  } else {
    const xA = buildXA(profile, health);
    const r = riskOf(MODEL_A_FEATS, MODEL_A_INTERCEPT, xA);
    modelA = { status: 'completed', skip_reason: null, risk_level: band(r).code, vascular_age: Math.round(vascularAge(xA) * 10) / 10, factors: topFactors(MODEL_A_FEATS, xA, 0.004) };
  }

  let modelB;
  if (skipBReason) {
    modelB = { status: 'skipped', skip_reason: skipBReason, factors: [] };
  } else {
    const xB = buildXB(profile, health, survey);
    const r = riskOf(MODEL_B_FEATS, MODEL_B_INTERCEPT, xB);
    modelB = { status: 'completed', skip_reason: null, probability: r, factors: topFactors(MODEL_B_FEATS, xB, 0.004) };
  }

  return { data: { bp_stage: stage, htn_status: health.htn_status, model_a: modelA, model_b: modelB } };
}

// 정식 예측 창구: 저장해 둔 건강기록·설문 번호로 신청 → 결과(model_a/model_b)를 바로 돌려받는다.
async function apiPredictionJob() {
  const get = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const health_record_id = get('paeon-health-record-id');
  if (!health_record_id) throw new Error('건강정보가 서버에 저장되어 있지 않아요. 건강정보를 다시 저장해주세요.');
  const survey_instance_id = get('paeon-survey-instance-id');
  return apiCall('POST', '/predictions/jobs', {
    health_record_id,
    ...(survey_instance_id ? { survey_instance_id } : {}),
    request_type: 'initial',
  }, '예측 요청에 실패했습니다');
}

// 내 정보 조회 (이메일·성별·생년월일)
async function apiGetMe() {
  return (await apiCall('GET', '/users/me', undefined, '내 정보를 불러오지 못했습니다')).data;
}

// 가장 최근 예측 결과. 아직 예측한 적이 없으면(404 PREDICTION_NOT_FOUND) null.
async function apiGetLatestPrediction() {
  try {
    return (await apiCall('GET', '/predictions/latest', undefined, '예측 결과를 불러오지 못했습니다')).data;
  } catch (e) {
    if (e.code === 'PREDICTION_NOT_FOUND') return null;
    throw e;
  }
}

// ---- 설문 값 계산 (설문 화면과 서버 복원이 같이 쓴다). 가이드 §2.1 나트륨 지수.
function ageOfBirth(birth) {
  const b = new Date(birth), n = new Date();
  let age = n.getFullYear() - b.getFullYear();
  if (n.getMonth() < b.getMonth() || (n.getMonth() === b.getMonth() && n.getDate() < b.getDate())) age--;
  return age;
}
const SODIUM_CODES = ['N0', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8', 'N9', 'N10'];
function sodiumCalc(answers, health, profile) {
  if (SODIUM_CODES.some(c => answers[c] == null)) return { status: 'incomplete' };
  if (!health || !profile || !profile.birth) return { status: 'no_input' };
  const age = ageOfBirth(profile.birth);
  if (age >= 70 || health.htn_status !== 'none' || health.diabetes) return { status: 'not_applicable' };
  const sex = health.sex === 'male' ? 1 : 2;
  const band = age <= 29 ? 1 : age <= 39 ? 2 : age <= 49 ? 3 : age <= 59 ? 4 : 5;
  const bmi = health.weight_kg / Math.pow(health.height_cm / 100, 2);
  const sum = SODIUM_CODES.slice(1).reduce((s, c) => s + Number(answers[c]), 0);
  const est = -191.9 - 705.2 * sex + 189.6 * band + 130.6 * bmi + 24.2 * Number(answers.N0) + 18.5 * sum;
  const index = Math.round(est / 20 * 10) / 10;
  const grade = index < 75 ? 'careful_low' : index <= 100 ? 'very_moderate' : index <= 150 ? 'moderate' : index <= 250 ? 'careful_high' : 'severe';
  return { status: 'ok', est_mg: Math.round(est), index, grade };
}
const EATOUT_TO_V1 = { rare: 'lt_monthly', '1_2_week': '1_2_per_week', '3_4_week': '3_4_per_week', '5_6_week': '5_6_per_week', '1_day': '1_per_day', '2plus_day': '2plus_per_day' };
function buildSurveyPayload(answers, health, profile, steps) {
  const sodium = sodiumCalc(answers, health, profile);
  const high = sodium.status === 'not_applicable' || (sodium.status === 'ok' && ['careful_high', 'severe'].includes(sodium.grade));
  return {
    answers: { ...answers },
    sodium,
    baseline_steps: steps != null ? steps : (answers.P2 != null ? answers.P2 : null),
    activity_code: answers.P1, eatout_code: answers.E1, breakfast_code: answers.B1, bp_measure_method: answers.BPM,
    // challenges.html가 가이드 §3 규칙으로 바뀌기 전까지 기존 화면이 읽는 값
    sodium_score: (sodium.status === 'ok' || sodium.status === 'not_applicable') ? (high ? 7 : 2) : undefined,
    aerobic: answers.P1 ? (answers.P1 === '150plus' ? 1 : 0) : undefined,
    eatout: answers.E1 ? EATOUT_TO_V1[answers.E1] : undefined,
    breakfast: answers.B1,
  };
}

// ---- 서버에서 복원: 건강기록 목록·상세, 설문 최근 답안지 (백엔드: GET /health/records, /health/records/{id}, /survey-instances/latest).
// 서버에 이 API가 없거나 실패하면 조용히 넘어가고, 브라우저에 보관해 둔 값을 그대로 쓴다.
const METRIC_TO_FIELD = { SBP: 'sbp', DBP: 'dbp', HEIGHT: 'height_cm', WEIGHT: 'weight_kg', WAIST: 'waist_cm', TOTAL_CHOL: 'total_chol', HDL: 'hdl',
  FASTING_GLUCOSE: 'fasting_glucose', SMOKING: 'smoking', HTN_STATUS: 'htn_status', PARENT_HTN: 'parent_htn', ALCOHOL_FREQ: 'drink_freq', ALCOHOL_AMOUNT: 'drink_amount' };
async function restoreHealthFromServer(sex) {
  try {
    const list = (await apiCall('GET', '/health/records', undefined, '')).data;
    const rec0 = list.find(r => r.input_type !== 'weekly_bp');          // 주간 혈압 기록은 건강정보 본문이 아니다
    if (!rec0) return false;
    const rec = (await apiCall('GET', `/health/records/${rec0.health_record_id}`, undefined, '')).data;
    const h = (() => { try { return JSON.parse(localStorage.getItem('paeon-health') || 'null') || {}; } catch (e) { return {}; } })();
    rec.measurements.forEach(m => {
      if (m.metric_code === 'DIABETES') h.diabetes = m.value_code === 'true';
      else if (METRIC_TO_FIELD[m.metric_code]) h[METRIC_TO_FIELD[m.metric_code]] = m.value_num != null ? m.value_num : m.value_code;
    });
    if (!h.drink_amount && ['never_lifetime', 'none_past_year'].includes(h.drink_freq)) h.drink_amount = null;
    if (sex) h.sex = sex;
    h.recorded_at = rec.examination_date;
    localStorage.setItem('paeon-health', JSON.stringify(h));
    localStorage.setItem('paeon-health-record-id', rec.health_record_id);
    return true;
  } catch (e) { return false; }
}
const V1_TO_ANSWER = { BREAKFAST: 'B1', EATOUT: 'E1', AEROBIC: 'P1' };
const EATOUT_FROM_V1 = { lt_monthly: 'rare', '1_3_per_month': 'rare', '1_2_per_week': '1_2_week', '3_4_per_week': '3_4_week', '5_6_per_week': '5_6_week', '1_per_day': '1_day', '2plus_per_day': '2plus_day' };
async function restoreSurveyFromServer() {
  try {
    const inst = (await apiCall('GET', '/survey-instances/latest', undefined, '')).data;
    const answers = {};
    inst.responses.forEach(r => {
      const c = r.question_code;
      if (V1_TO_ANSWER[c]) {                                           // 예전 설문(v1) 3문항
        if (c === 'EATOUT') answers.E1 = EATOUT_FROM_V1[r.option_code];
        else if (c === 'AEROBIC') answers.P1 = r.option_code === 'yes' ? '150plus' : 'lt150';
        else answers.B1 = r.option_code;
      } else if (c === 'BP_MEASURE_METHOD') answers.BPM = r.option_code;
      else if (r.option_code == null && r.value_num != null) answers[c] = r.value_num;   // v2 숫자 문항(P2 걸음 수)
      else answers[c] = serverCodeToScore(c, r.option_code);            // v2: N0..N10(서버 코드→점수), P1, E1, B1
    });
    const read = (k) => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
    localStorage.setItem('paeon-survey', JSON.stringify(buildSurveyPayload(answers, read('paeon-health'), read('paeon-profile'))));
    localStorage.setItem('paeon-survey-instance-id', inst.survey_instance_id);
    return true;
  } catch (e) { return false; }
}

// ---- 임시: 서버에 건강정보·챌린지·일기를 읽어 오는 API가 생기기 전까지, 로그아웃할 때 계정별로 보관했다가 같은 계정이 다시 로그인하면 되돌린다.
// 서버 API가 준비되면 이 보관은 없애고 서버에서 읽어 온다.
const LOCAL_DATA_KEYS = ['paeon-eligibility', 'paeon-health', 'paeon-survey', 'paeon-cycle', 'paeon-cycle-history', 'paeon-progress', 'paeon-recheck',
  'paeon-calendar', 'paeon-health-record-id', 'paeon-survey-instance-id', 'paeon-prediction', 'paeon-profile'];
function stashLocalData(uid) {
  if (!uid) return;
  try {
    const box = {};
    LOCAL_DATA_KEYS.forEach(k => { const v = localStorage.getItem(k); if (v != null) box[k] = v; });
    localStorage.setItem('paeon-store:' + uid, JSON.stringify(box));
    LOCAL_DATA_KEYS.forEach(k => localStorage.removeItem(k));
  } catch (e) {}
}
function restoreLocalData(uid) {
  try {
    const box = JSON.parse(localStorage.getItem('paeon-store:' + uid) || 'null');
    if (!box) return;
    Object.entries(box).forEach(([k, v]) => { if (localStorage.getItem(k) == null) localStorage.setItem(k, v); });  // 지금 쓰던 값이 있으면 그걸 우선
  } catch (e) {}
}

// 로그인 직후: 서버에 있는 내 정보·최근 예측을 이 브라우저에 채운다 (다른 기기에서 로그인해도 이어서 보이게). 실패해도 로그인은 그대로 진행.
async function apiSyncAfterLogin() {
  const read = (k) => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
  try {
    const me = await apiGetMe();
    const prevUid = localStorage.getItem('paeon-user-id');
    if (prevUid && prevUid !== me.user_id) stashLocalData(prevUid);   // 다른 계정의 데이터가 남아 있으면 그 계정 몫으로 보관
    restoreLocalData(me.user_id);                                      // 이 계정이 보관해 둔 기록을 되돌림
    localStorage.setItem('paeon-user-id', me.user_id);
    localStorage.setItem('paeon-profile', JSON.stringify({ ...(read('paeon-profile') || {}), email: me.email, birth: me.birth_date, sex: me.sex }));
  } catch (e) { /* 내 정보는 없어도 진행 */ }
  // 서버에 건강정보·설문 조회 API가 있으면 서버 값으로 복원 (없으면 위에서 되돌린 브라우저 보관본을 그대로 씀)
  try {
    const sex = (read('paeon-profile') || {}).sex;
    await restoreHealthFromServer(sex);
    if (!localStorage.getItem('paeon-survey')) await restoreSurveyFromServer();   // 설문은 걸음 수처럼 서버에 없는 값이 있어 브라우저 값을 우선
  } catch (e) { /* 복원 실패해도 로그인은 진행 */ }
  try {
    const latest = await apiGetLatestPrediction();
    if (latest) {
      const health = read('paeon-health');
      const prev = read('paeon-prediction') || {};
      localStorage.setItem('paeon-prediction', JSON.stringify({
        ...latest,
        bp_stage: health ? bpStage(health.sbp, health.dbp) : prev.bp_stage,
        htn_status: health ? health.htn_status : prev.htn_status,
      }));
    }
  } catch (e) { /* 결과는 없어도 진행 */ }
}

// 로그아웃: 서버 쿠폰을 폐기하고, 이 계정의 기록은 계정별로 보관해 둔 뒤 로그인 화면으로 간다.
async function apiLogout() {
  let uid = localStorage.getItem('paeon-user-id');
  if (!uid) { try { uid = (await apiGetMe()).user_id; } catch (e) {} }
  stashLocalData(uid);                                 // 서버 호출이 실패해도 기록은 먼저 보관
  const refresh_token = localStorage.getItem('paeon-refresh-token') || '';
  try { await apiCall('POST', '/auth/logout', { refresh_token }, '로그아웃에 실패했습니다'); } catch (e) { /* 서버 실패여도 이 기기에서는 로그아웃 */ }
  ['paeon-access-token', 'paeon-refresh-token', 'paeon-user-id'].forEach(k => { try { localStorage.removeItem(k); } catch (e) {} });
  location.href = 'login.html';
}

// (구) 혜림님 임시 창구(POST /v1/predict) 전용 — 정식 /predictions/jobs 생기면 지울 예정.
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
  if (!res.ok) throw new Error(body.error?.message || '예측 요청에 실패했습니다');
  return body;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
