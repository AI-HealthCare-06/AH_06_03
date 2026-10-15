const PAEON_LOGO_SVG = `
<svg width="20" height="20" viewBox="0 0 100 100">
  <g style="fill:var(--stem)">
    <ellipse cx="50" cy="76" rx="8" ry="16" transform="rotate(35 50 76)"/>
    <ellipse cx="50" cy="76" rx="8" ry="16" transform="rotate(-35 50 76)"/>
  </g>
  <g style="fill:var(--petal1)">
    <ellipse cx="50" cy="26" rx="14" ry="21"/>
    <ellipse cx="50" cy="26" rx="14" ry="21" transform="rotate(60 50 50)"/>
    <ellipse cx="50" cy="26" rx="14" ry="21" transform="rotate(120 50 50)"/>
    <ellipse cx="50" cy="26" rx="14" ry="21" transform="rotate(180 50 50)"/>
    <ellipse cx="50" cy="26" rx="14" ry="21" transform="rotate(240 50 50)"/>
    <ellipse cx="50" cy="26" rx="14" ry="21" transform="rotate(300 50 50)"/>
  </g>
  <g style="fill:var(--petal2)">
    <ellipse cx="50" cy="30" rx="11" ry="17" transform="rotate(30 50 50)"/>
    <ellipse cx="50" cy="30" rx="11" ry="17" transform="rotate(90 50 50)"/>
    <ellipse cx="50" cy="30" rx="11" ry="17" transform="rotate(150 50 50)"/>
    <ellipse cx="50" cy="30" rx="11" ry="17" transform="rotate(210 50 50)"/>
    <ellipse cx="50" cy="30" rx="11" ry="17" transform="rotate(270 50 50)"/>
    <ellipse cx="50" cy="30" rx="11" ry="17" transform="rotate(330 50 50)"/>
  </g>
  <circle cx="50" cy="50" r="11" style="fill:var(--center)"/>
  <circle cx="45" cy="47" r="2.2" style="fill:var(--dots)"/>
  <circle cx="55" cy="47" r="2.2" style="fill:var(--dots)"/>
  <circle cx="50" cy="54" r="2.2" style="fill:var(--dots)"/>
</svg>`;

// 시안(design/redesign-2026-10)에서 쓰는 선 아이콘. 한 곳에 모아 두고 화면에서는 ICON.이름 으로 쓴다.
const _svg = (inner, w = 24) => `<svg width="${w}" height="${w}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
const ICON = {
  home: _svg('<path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z"/>'),
  record: _svg('<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h3"/>'),
  challenge: _svg('<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>'),
  community: _svg('<path d="M4 5h16v11h-7l-4 4v-4H4z"/>'),
  more: _svg('<path d="M4 7h16M4 12h16M4 17h16"/>'),
  bell: _svg('<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0"/>'),
  back: _svg('<path d="M15 5l-7 7 7 7"/>'),
  chevron: _svg('<path d="M9 5l7 7-7 7"/>', 18),
  search: _svg('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'),
  plus: _svg('<path d="M12 5v14M5 12h14"/>', 18),
  calendar: _svg('<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>', 26),
  pie: '<svg class="pie-coin" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#F3E3D0" stroke="#243749" stroke-width="1.6"/><path d="M12 12V2a10 10 0 0 1 8.5 4.8z" fill="#F2C94C" stroke="#243749" stroke-width="1.6" stroke-linejoin="round"/><circle cx="8" cy="14" r="1.2" fill="#243749"/></svg>',
};

function _apiBase() {
  return typeof API_BASE !== 'undefined' ? API_BASE : (['5500'].includes(location.port) ? 'http://127.0.0.1:8000/v1' : 'https://54-116-113-17.sslip.io/v1');
}
// 로그인한 사람의 파이 잔액. 로그인하지 않았거나 서버에 닿지 않으면 null (칩만 빠지고 화면은 그대로 동작한다)
async function pieBalance() {
  try {
    const t = localStorage.getItem('paeon-access-token');
    if (!t) return null;
    const r = await fetch(_apiBase() + '/pie', { headers: { Authorization: 'Bearer ' + t } });
    return r.ok ? (await r.json()).data.balance : null;
  } catch (e) { return null; }
}

const PIE_PAGES_HIDE_CHIP = ['index.html', 'signup.html', 'login.html', 'guest-inquiry.html', 'eligibility.html'];

function renderHeader(){
  const slot = document.getElementById('header-slot');
  if (!slot) return;
  const page = location.pathname.split('/').pop() || 'index.html';
  // 시안: 상단 바에 PAEON·파이·알림이 있는 건 홈뿐이다. 더보기와 챌린지 탭은 제목을 쓰고, 나머지 화면은 화면 안의 제목·뒤로가기 줄을 쓴다.
  const HEADERS = { 'dashboard.html': { brand: true }, 'menu.html': { title: '더보기' }, 'challenge-progress.html': { title: '챌린지', plain: true }, 'challenges.html': { title: '챌린지 고르기', plain: true } };
  const hd = HEADERS[page];
  if (!hd) { slot.innerHTML = ''; return; }
  const showRight = loggedIn() && !hd.plain && !PIE_PAGES_HIDE_CHIP.includes(page);
  slot.innerHTML = `
    <div class="picker">
      ${hd.brand ? `<a class="brand" href="dashboard.html">PAEON</a>` : `<span class="brand" style="font-size:22px; letter-spacing:-.3px">${hd.title}</span>`}
      ${showRight ? `<div class="hdr-right"><a class="hdr-pie" id="hdr-pie" href="pie.html" aria-label="내 파이" hidden>${ICON.pie}<span id="hdr-pie-n"></span></a><a class="hdr-bell" id="hdr-bell" href="inquiries.html" aria-label="문의 답변">${ICON.bell}</a></div>` : ''}
    </div>`;
  if (!showRight) return;
  pieBalance().then((n) => {
    if (n === null) return;
    document.getElementById('hdr-pie-n').textContent = n;
    document.getElementById('hdr-pie').hidden = false;
  });
  inquiryUnread().then((n) => {   // 1:1 문의에 답변이 오면 종에 숫자
    if (n) document.getElementById('hdr-bell').insertAdjacentHTML('beforeend', `<span class="badge" aria-label="새 답변 ${n}개">${n}</span>`);
  });
}
function loggedIn(){ try { return !!localStorage.getItem('paeon-access-token'); } catch (e) { return false; } }

// 하단 탭 5개. 챌린지는 진행 중인 사이클이 있으면 수행 화면, 없으면 시작 화면으로 간다.
const NAV_ITEMS = [
  { icon: ICON.record, label: '내 기록', href: 'trend.html', pages: ['trend.html', 'twelve-weeks.html', 'reassessment.html'] },
  { icon: ICON.challenge, label: '챌린지', href: localStorage.getItem('paeon-cycle') ? 'challenge-progress.html' : 'challenges.html', pages: ['challenges.html', 'challenge-progress.html'] },
  { icon: ICON.home, label: '홈', href: 'dashboard.html', pages: ['dashboard.html', 'health-info.html', 'survey.html', 'review.html', 'result.html', 'calendar-diary.html'] },
  { icon: ICON.community, label: '커뮤니티', href: 'feed.html', pages: ['feed.html', 'write.html', 'post.html', 'nickname.html', 'common-challenges.html', 'common-challenge.html'] },
  { icon: ICON.more, label: '더보기', href: 'menu.html', pages: ['menu.html', 'mypage.html', 'inquiries.html', 'guide.html', 'terms.html', 'pie.html'] },
];
// 안 읽은 문의 답변 수. 로그인하지 않았거나 서버에 닿지 않으면 0 (메뉴만 빠지고 화면은 그대로 동작한다)
async function inquiryUnread() {
  try {
    const t = localStorage.getItem('paeon-access-token');
    if (!t) return 0;
    const r = await fetch(_apiBase() + '/inquiries', { headers: { Authorization: 'Bearer ' + t } });
    return r.ok ? ((await r.json()).data.unread || 0) : 0;
  } catch (e) { return 0; }
}

const NO_NAV_PAGES = ['index.html', 'signup.html', 'login.html', 'guest-inquiry.html', 'eligibility.html', 'privacy.html', 'my-data.html', 'write.html', 'nickname.html'];

function renderNav(){
  if (document.querySelector('.tabbar')) return;
  const page = location.pathname.split('/').pop() || 'index.html';
  if (NO_NAV_PAGES.includes(page) || !loggedIn()) return;
  const nav = document.createElement('nav');
  nav.className = 'tabbar';
  nav.setAttribute('aria-label', '주요 메뉴');
  nav.innerHTML = NAV_ITEMS.map(it => `<a href="${it.href}"${it.pages.includes(page) ? ' class="active" aria-current="page"' : ''}>${it.icon}${it.label}</a>`).join('');
  document.body.appendChild(nav);
  inquiryUnread().then((n) => {   // 더보기(문의 포함)에 점
    const a = nav.querySelector('a[href="menu.html"]');
    if (n && a) a.insertAdjacentHTML('beforeend', '<span class="nav-dot" aria-label="새 답변"></span>');
  });
}

// 처음 시작하는 4단계(대상 확인 → 건강정보 → 설문 → 위험도 분석)의 진행 상태와 다음 할 일. 대시보드와 입력 검토 화면의 안내에 쓴다.
function setupProgress() {
  const has = (k) => { try { return !!JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return false; } };
  const steps = [
    { label: '대상 확인', done: has('paeon-eligibility'), href: 'eligibility.html' },
    { label: '건강정보 입력', done: has('paeon-health'), href: 'health-info.html' },
    { label: '생활습관 설문', done: has('paeon-survey'), href: 'survey.html' },
    { label: '위험 신호 분석', done: has('paeon-prediction'), href: 'review.html' },
  ];
  const next = steps.find(s => !s.done) || null;
  const html = `<ol class="setup-steps">${steps.map((s, i) =>
    `<li class="${s.done ? 'done' : (s === next ? 'now' : '')}"><span class="no">${s.done ? '✓' : i + 1}</span>${s.label}<em>${s.done ? '완료' : (s === next ? '다음 단계' : '')}</em></li>`).join('')}</ol>`;
  return { steps, next, html };
}

// "정말 할까요?" 확인 창. 확인하면 true, 취소(버튼·바깥 클릭·Esc)하면 false로 끝나는 Promise를 돌려준다.
function confirmDialog(title, message, okLabel = '확인') {
  return new Promise(resolve => {
    const wrap = document.createElement('div');
    wrap.className = 'confirm-backdrop';
    wrap.innerHTML = `<div class="confirm-card" role="dialog" aria-modal="true" aria-label="${title}">
      <b>${title}</b><p>${message}</p>
      <div class="confirm-actions"><button type="button" class="ghost" data-act="no">취소</button><button type="button" class="cta" data-act="yes">${okLabel}</button></div></div>`;
    const done = (v) => { document.removeEventListener('keydown', onKey); wrap.remove(); resolve(v); };
    const onKey = (e) => { if (e.key === 'Escape') done(false); };
    wrap.addEventListener('click', (e) => { if (e.target === wrap) done(false); else if (e.target.dataset.act) done(e.target.dataset.act === 'yes'); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(wrap);
    wrap.querySelector('[data-act="no"]').focus();
  });
}

// 비밀번호 칸 오른쪽에 "보기" 버튼을 붙인다. 나중에 그려지는 칸은 addPasswordToggles(그 영역)를 다시 부른다.
function addPasswordToggles(root = document) {
  root.querySelectorAll('input[type=password]').forEach(input => {
    if (input.dataset.pwToggle) return;
    input.dataset.pwToggle = '1';
    const wrap = document.createElement('div');
    wrap.className = 'pw-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pw-toggle';
    btn.textContent = '보기';
    btn.setAttribute('aria-label', '비밀번호 보기');
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.textContent = show ? '숨기기' : '보기';
      btn.setAttribute('aria-label', show ? '비밀번호 숨기기' : '비밀번호 보기');
    });
    wrap.appendChild(btn);
  });
}

document.addEventListener('DOMContentLoaded', () => { renderHeader(); renderNav(); addPasswordToggles(); document.querySelectorAll('[data-icon]').forEach(e => { e.innerHTML = ICON[e.dataset.icon] || ''; }); });

// 모델 B: 서버가 주는 similarity_level(similar / slightly_different / different)을 말로만 보여 준다. 화면에서 기준값을 계산하지 않는다.
// 값이 아직 없으면(서버 미지원) 판정 문장은 빼고 설명만 보인다.
const SIM_NOW = { similar: '혈압이 정상인 사람들과 비슷한 편이에요', slightly_different: '혈압이 정상인 사람들과 조금 달라요', different: '혈압이 정상인 사람들과 많이 달라요' };
const SIM_RANK = { similar: 0, slightly_different: 1, different: 2 };
function simChangeText(before, after) {
  if (!(before in SIM_RANK) || !(after in SIM_RANK)) return '';
  return SIM_RANK[after] < SIM_RANK[before] ? '4주 전보다 더 비슷해졌어요' : SIM_RANK[after] === SIM_RANK[before] ? '비슷한 자리예요' : '조금 달라졌어요';
}

// 상담 권고가 필요한 경우의 제목(혈압 140/90·160/100 이상, 또는 10년 내 심장 혈관 건강 신호 높음). 필요 없으면 ''.
function adviceTitle(pred, health) {
  if (!pred) return '';
  const very = health && (health.sbp >= 160 || health.dbp >= 100);
  const high = health && (health.sbp >= 140 || health.dbp >= 90);
  const aHigh = pred.model_a && pred.model_a.status === 'completed' && pred.model_a.risk_level === 'high';
  if (very || (high && pred.htn_status === 'none')) return `입력하신 혈압이 ${very ? '많이 ' : ''}높아요 (${health.sbp}/${health.dbp} mmHg)`;
  return aHigh ? '10년 내 심장 혈관 건강 신호가 높게 나왔어요' : '';
}
const ADVICE_ACK_TEXT = '의료기관 상담 권고를 확인했고, 이를 확인한 뒤 챌린지를 진행하는 데 동의합니다.';
const adviceAcked = () => { try { return localStorage.getItem('paeon-advice-ack') === '1'; } catch (e) { return false; } };
const setAdviceAck = (v) => { try { v ? localStorage.setItem('paeon-advice-ack', '1') : localStorage.removeItem('paeon-advice-ack'); } catch (e) { /* 저장 못 해도 화면은 계속 */ } };
// 상담 권고 배너: X로 닫아도 챌린지는 계속 가능하고 다음 방문 때 다시 보인다. 확인 체크는 챌린지 시작 때 다시 묻는다.
function adviceBannerHtml(pred, health) {
  const title = adviceTitle(pred, health);
  if (!title) return '';
  return `<div class="callout" id="advice-banner" style="border-color:var(--risk); position:relative; padding-right:34px"><button type="button" aria-label="닫기" onclick="document.getElementById('advice-banner').remove()" style="position:absolute; top:8px; right:10px; border:0; background:none; font-size:18px; line-height:1; color:var(--muted); cursor:pointer">×</button><b>${title}</b><br>가까운 의료기관에서 상담을 받아 보세요. <a href="guide.html" style="color:var(--sage-deep); font-weight:700">검사 · 상담 안내 보기</a>
    <label style="display:flex; gap:8px; align-items:flex-start; margin-top:10px; font-size:12.5px; line-height:1.5; cursor:pointer"><input type="checkbox" ${adviceAcked() ? 'checked' : ''} onchange="setAdviceAck(this.checked)" style="margin-top:3px"><span>${ADVICE_ACK_TEXT}</span></label></div>`;
}

// 모델 A 버전이 바뀌어 전·후를 비교할 수 없을 때(comparable=false, 둘 다 분석 완료) 비교 줄 대신 안내한다. 오류가 아니다.
function modelANoticeHtml(models) {
  const a = (models || []).find(m => m.model_code === 'MODEL_A');
  return a && !a.comparable && a.before_status === 'completed' && a.after_status === 'completed'
    ? '<p class="hint" style="margin:0 0 8px">모델이 업데이트되어 이번에는 비교하지 않아요. 다음 4주부터 비교해요.</p>' : '';
}
