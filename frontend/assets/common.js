// 로그인 토큰 보관. '로그인 상태 유지'를 켜면 localStorage(브라우저를 닫아도 유지),
// 끄면 sessionStorage(이 탭을 닫으면 로그아웃). common.js와 api.js에 같은 내용이 있으니 고칠 때는 둘 다 고친다.
var PaeonTokens = window.PaeonTokens || (window.PaeonTokens = (function () {
  var KEYS = ['paeon-access-token', 'paeon-refresh-token'];
  function stores() {
    var s = [];
    try { s.push(window.sessionStorage); } catch (e) {}
    try { s.push(window.localStorage); } catch (e) {}
    return s;
  }
  function holder() {   // 토큰이 들어 있는 곳 (없으면 null)
    var all = stores();
    for (var i = 0; i < all.length; i++) {
      try { if (all[i].getItem(KEYS[1]) || all[i].getItem(KEYS[0])) return all[i]; } catch (e) {}
    }
    return null;
  }
  function read(k) { var h = holder(); try { return h ? (h.getItem(k) || '') : ''; } catch (e) { return ''; } }
  function clear() { stores().forEach(function (s) { KEYS.forEach(function (k) { try { s.removeItem(k); } catch (e) {} }); }); }
  return {
    access: function () { return read(KEYS[0]); },
    refresh: function () { return read(KEYS[1]); },
    // keep: 새로 로그인할 때 true(유지)/false(이 탭만). 재발급처럼 비워 두면 지금 들어 있는 곳에 그대로 둔다.
    save: function (access, refresh, keep) {
      var h = holder();
      var target = keep === undefined ? (h || window.localStorage) : (keep ? window.localStorage : window.sessionStorage);
      clear();
      target.setItem(KEYS[0], access);
      target.setItem(KEYS[1], refresh);
    },
    clear: clear,
  };
})());

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
  pie: '<img class="pie-coin" src="assets/img/pie-coin.png" alt="">',
};

function _apiBase() {
  return typeof API_BASE !== 'undefined' ? API_BASE : (['5500'].includes(location.port) ? 'http://127.0.0.1:8000/v1' : 'https://54-116-113-17.sslip.io/v1');
}
// 로그인한 사람의 파이 잔액. 로그인하지 않았거나 서버에 닿지 않으면 null (칩만 빠지고 화면은 그대로 동작한다)
async function pieBalance() {
  try {
    const t = PaeonTokens.access();
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
      ${showRight ? `<div class="hdr-right"><a class="hdr-pie" id="hdr-pie" href="pie.html" aria-label="내 파이" hidden>${ICON.pie}<span id="hdr-pie-n"></span></a><a class="hdr-bell" id="hdr-bell" href="inquiries.html?from=bell" aria-label="문의 답변">${ICON.bell}</a></div>` : ''}
    </div>`;
  if (!showRight) return;
  pieBalance().then((n) => {
    if (n === null) return;
    document.getElementById('hdr-pie-n').textContent = n;
    document.getElementById('hdr-pie').hidden = false;
  });
  Promise.all([inquiryUnread(), unseenNotices()]).then(([n, notices]) => {   // 문의 답변은 종에 숫자, 새 공지는 파란 점
    const bell = document.getElementById('hdr-bell');
    if (n) bell.insertAdjacentHTML('beforeend', `<span class="badge" aria-label="새 답변 ${n}개">${n}</span>`);
    else if (notices.length) { bell.insertAdjacentHTML('beforeend', '<span class="dot" aria-label="새 공지"></span>'); bell.href = 'notices.html'; }
  });
}
// 화면 위에 잠깐 떴다 사라지는 알림 줄. toastNext는 다른 화면으로 이동한 뒤 그 화면에서 보여 준다(글쓰기 직후 등).
function toast(msg) {
  const t = document.createElement('div');
  t.setAttribute('role', 'status');
  t.textContent = msg;
  t.style.cssText = 'position:fixed; left:50%; top:16px; transform:translate(-50%,-12px); z-index:400; max-width:calc(100% - 32px); box-sizing:border-box; padding:12px 18px; border-radius:22px; background:#243749; color:#fff; font-size:14px; font-weight:700; text-align:center; opacity:0; transition:opacity .25s, transform .25s';
  document.body.appendChild(t);
  requestAnimationFrame(() => { t.style.opacity = '1'; t.style.transform = 'translate(-50%,0)'; });
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000);
}
function toastNext(msg) { try { sessionStorage.setItem('paeon-toast', msg); } catch (e) { /* 알림만 빠진다 */ } }
document.addEventListener('DOMContentLoaded', () => {
  try { const m = sessionStorage.getItem('paeon-toast'); if (m) { sessionStorage.removeItem('paeon-toast'); toast(m); } } catch (e) { /* 알림만 빠진다 */ }
});

// 가로로 넘기는 칩 줄(.cats, .fl): 오른쪽에 더 있으면 끝을 흐리게 해서 넘길 수 있다는 걸 알려 준다
function enableScrollFade() {
  document.querySelectorAll('.cats, .fl').forEach((el) => {
    const upd = () => el.classList.toggle('fade-r', el.scrollWidth - el.clientWidth - el.scrollLeft > 4);
    if (!el.dataset.fade) { el.dataset.fade = '1'; el.addEventListener('scroll', upd, { passive: true }); new MutationObserver(upd).observe(el, { childList: true }); }
    upd();
  });
}
document.addEventListener('DOMContentLoaded', () => { enableScrollFade(); setTimeout(enableScrollFade, 600); });

// 서버 계산을 기다리는 동안 보여 주는 진행 화면. 바는 요청이 끝날 때까지 최대 92%까지 차오르고,
// finish()를 부르면 100%로 채운 뒤 잠깐 보여 주고(await), 실패하면 cancel()로 닫는다. title·sub는 우리가 쓴 문구만 넣는다(HTML 허용).
function progressOverlay(title, sub) {
  const box = document.createElement('div');
  box.style.cssText = 'position:fixed; inset:0; z-index:300; background:#fff; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; padding:24px; text-align:center';
  box.innerHTML = `<b style="font-size:22px; font-weight:800; line-height:1.4">${title}</b><p style="margin:0; font-size:14px; color:var(--body); line-height:1.6">${sub}</p><div style="width:min(280px,80%); height:10px; border-radius:5px; background:var(--line); overflow:hidden; margin-top:10px"><i class="pg-bar" style="display:block; height:100%; width:0; border-radius:5px; background:var(--accent); transition:width .35s"></i></div><span class="pg-pct" style="font-size:13px; font-weight:700; color:var(--muted)">0%</span>`;
  document.body.appendChild(box);
  let v = 0;
  const set = (n) => { v = n; box.querySelector('.pg-bar').style.width = n + '%'; box.querySelector('.pg-pct').textContent = Math.round(n) + '%'; };
  const timer = setInterval(() => set(Math.min(92, v + (92 - v) * 0.08 + 0.4)), 300);
  return {
    finish: () => { clearInterval(timer); set(100); return new Promise((r) => setTimeout(r, 500)); },
    cancel: () => { clearInterval(timer); box.remove(); },
  };
}

// 뒤로 버튼(a.back): 같은 앱에서 바로 전에 보던 화면이 있으면 그리로 돌아간다. 입력·제출 화면에서 왔거나 없으면 화면에 정해 둔 곳(href)으로.
const BACK_NEVER = ['login.html', 'signup.html', 'index.html', 'write.html', 'nickname.html', 'party-create.html', 'review.html', 'eligibility.html'];
const BACK_NEVER_PAIR = { 'reassessment.html': ['survey.html'] };
document.addEventListener('click', (e) => {
  const a = e.target.closest && e.target.closest('a.back');
  if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
  let u;
  try { u = new URL(document.referrer); } catch (err) { return; }
  if (u.origin !== location.origin) return;
  const ref = u.pathname.split('/').pop(), cur = location.pathname.split('/').pop();
  if (!ref || ref === cur || BACK_NEVER.includes(ref) || (BACK_NEVER_PAIR[cur] || []).includes(ref) || history.length <= 1) return;
  e.preventDefault();
  history.back();
});

// 파이 그림을 접시에 올린다 (선으로 그린 접시: 픽셀 파이와 어울리게). hot 인자는 예전 호출과 맞추려고 남겨 둔 것이다.
function pieDish(inner) {
  return `<span class="dish">${inner}</span>`;
}
// 공지: 게시 중인 공지(GET /notices, 로그인 불필요)와 이 기기에서 계정별로 "본 공지" 기록
async function fetchNotices() {
  try {
    const r = await fetch(_apiBase() + '/notices');
    return r.ok ? (await r.json()).data : [];
  } catch (e) { return []; }
}
function _noticeKey() { try { return 'paeon-notices-seen:' + (localStorage.getItem('paeon-user-id') || ''); } catch (e) { return 'paeon-notices-seen:'; } }
function _noticesSeen() { try { return JSON.parse(localStorage.getItem(_noticeKey()) || '[]'); } catch (e) { return []; } }
function markNoticesSeen(list) {
  try { localStorage.setItem(_noticeKey(), JSON.stringify([...new Set([..._noticesSeen(), ...list.map((n) => n.notice_id)])].slice(-100))); } catch (e) { /* 기록만 빠진다 */ }
}
async function unseenNotices() {
  if (!loggedIn()) return [];
  const seen = _noticesSeen();
  return (await fetchNotices()).filter((n) => !seen.includes(n.notice_id));
}
// 새 공지를 하나씩 팝업으로 보여 준다 (확인하면 본 것으로 기록)
async function showNoticePopups() {
  for (const n of (await unseenNotices()).reverse()) {
    await new Promise((resolve) => {
      const wrap = document.createElement('div');
      wrap.className = 'confirm-backdrop';
      wrap.innerHTML = '<div class="confirm-card" role="dialog" aria-modal="true"><span class="notice-tag">공지</span><b></b><p></p><div class="confirm-actions"><button type="button" class="cta">확인</button></div></div>';
      wrap.querySelector('b').textContent = n.title;
      const p = wrap.querySelector('p'); p.textContent = n.body; p.style.cssText = 'white-space:pre-wrap; text-align:left; max-height:50vh; overflow:auto';
      wrap.querySelector('button').addEventListener('click', () => { markNoticesSeen([n]); wrap.remove(); resolve(); });
      document.body.appendChild(wrap);
    });
  }
}
function loggedIn(){ return !!PaeonTokens.access(); }

// 하단 탭 5개. 챌린지는 진행 중인 사이클이 있으면 수행 화면, 없으면 시작 화면으로 간다.
const NAV_ITEMS = [
  { icon: ICON.record, label: '내 변화', href: 'trend.html', pages: ['trend.html', 'twelve-weeks.html', 'reassessment.html', 'program-review.html'] },
  { icon: ICON.challenge, label: '챌린지', href: localStorage.getItem('paeon-cycle') ? 'challenge-progress.html' : 'challenges.html', pages: ['challenges.html', 'challenge-progress.html', 'badges.html'] },
  { icon: ICON.home, label: '홈', href: 'dashboard.html', pages: ['dashboard.html', 'plan.html', 'health-info.html', 'survey.html', 'review.html', 'result.html', 'calendar-diary.html'] },
  { icon: ICON.community, label: '커뮤니티', href: 'feed.html', pages: ['feed.html', 'write.html', 'post.html', 'nickname.html', 'common-challenges.html', 'common-challenge.html', 'party.html', 'party-start.html', 'party-create.html', 'party-home.html'] },
  { icon: ICON.more, label: '더보기', href: 'menu.html', pages: ['menu.html', 'mypage.html', 'inquiries.html', 'notices.html', 'guide.html', 'terms.html', 'character.html', 'pie.html'] },
];
// 안 읽은 문의 답변 수. 로그인하지 않았거나 서버에 닿지 않으면 0 (메뉴만 빠지고 화면은 그대로 동작한다)
async function inquiryUnread() {
  try {
    const t = PaeonTokens.access();
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
// options = [[코드, 라벨], ...]를 주면 선택지를 같이 보여 주고, 확인하면 {code}(고르지 않으면 null)를, 취소하면 false를 돌려준다.
function confirmDialog(title, message, okLabel = '확인', options, cancelLabel = '취소') {
  return new Promise(resolve => {
    const wrap = document.createElement('div');
    wrap.className = 'confirm-backdrop';
    wrap.innerHTML = `<div class="confirm-card" role="dialog" aria-modal="true" aria-label="${title}">
      <b>${title}</b><p>${message}</p>
      ${options ? `<div class="confirm-opts">${options.map(o => `<label><input type="radio" name="confirm-opt" value="${o[0]}"><span>${o[1]}</span></label>`).join('')}</div>` : ''}
      <div class="confirm-actions"><button type="button" class="ghost" data-act="no">${cancelLabel}</button><button type="button" class="cta" data-act="yes">${okLabel}</button></div></div>`;
    const done = (v) => {
      const picked = wrap.querySelector('input[name="confirm-opt"]:checked');
      document.removeEventListener('keydown', onKey); wrap.remove();
      resolve(options && v ? { code: picked ? picked.value : null } : v);
    };
    const onKey = (e) => { if (e.key === 'Escape') done(false); };
    wrap.addEventListener('click', (e) => { if (e.target === wrap) done(false); else if (e.target.dataset.act) done(e.target.dataset.act === 'yes'); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(wrap);
    wrap.querySelector('[data-act="no"]').focus();
  });
}

// 안내만 하는 창: 확인 버튼 하나(취소 없음). 닫으면 resolve된다.
function noticeDialog(title, message, okLabel = '확인') {
  return new Promise(resolve => {
    const wrap = document.createElement('div');
    wrap.className = 'confirm-backdrop';
    wrap.innerHTML = `<div class="confirm-card" role="dialog" aria-modal="true" aria-label="${title}">
      <b>${title}</b><p>${message}</p>
      <div class="confirm-actions"><button type="button" class="cta" data-act="ok">${okLabel}</button></div></div>`;
    const done = () => { wrap.remove(); resolve(true); };
    wrap.addEventListener('click', (e) => { if (e.target.dataset.act === 'ok') done(); });
    document.body.appendChild(wrap);
    wrap.querySelector('[data-act="ok"]').focus();
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

// 모델 A v0.2.0: 서버가 주는 확률(0~1 소수)을 "%"로, 소수 첫째 자리까지 보여 준다. 값이 없으면 ''.
// 범주(양호·주의·높음)는 서버가 주는 risk_level을 그대로 쓰고 화면에서 확률로 다시 가르지 않는다.
function probText(p) { return typeof p === 'number' && isFinite(p) ? (p * 100).toFixed(1) + '%' : ''; }
// "같은 성별·연령대 상위 N%" (참고용 보조 문구. 범주 판정에는 쓰지 않는다). 값이 없으면 ''.
function percentileText(pc) { return typeof pc === 'number' && isFinite(pc) ? `같은 성별·연령대 상위 ${Math.max(1, Math.round(pc))}%` : ''; }
const PROB_NOTE = '10년 안에 관상동맥질환이 생길 가능성을 미국 Framingham 모델로 계산하고 한국인 평균에 맞춰 보정한 값이에요. 2% 미만 양호, 2~9% 주의, 9% 이상 높음 구간은 일본 동맥경화학회 기준을 참고했어요. 의학적 진단·치료를 대신하지 않아요.';
// 혈관 나이 카드의 "계산 근거" 문구 (확률 근거와 따로 둔다)
const AGE_BASIS = '혈관 나이는 혈압, 콜레스테롤, 흡연, 당뇨, 고혈압 진단·치료, BMI가 같은 성별·연령대 한국 성인 평균(국민건강영양조사 2022~2024)과 얼마나 다른지를 나이로 바꿔 더한 추정치예요. 모두 평균과 같으면 실제 나이와 같게 나와요.<br><br>상위 %는 같은 성별·연령대 한국 성인 중 위험 요인이 많은 순서로 줄 세웠을 때의 위치예요. 상위 1%에 가까울수록 위험 요인이 많은 편이고, 50% 근처면 중간쯤이에요.<br>두 값 모두 의학적 진단·치료를 대신하지 않아요.';
// 확률 근거 안내: 평소에는 접혀 있고 버튼을 누르면 펼쳐진다
function probNoteHtml(withAge, caption) {
  const chev = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 6l4.5 4.5L12.5 6"/></svg>';
  const btn = `<button type="button" aria-expanded="false" onclick="const p = this.closest('.pnote').querySelector('p'); p.hidden = !p.hidden; this.setAttribute('aria-expanded', String(!p.hidden))">확률 근거${chev}</button>`;
  return `<div class="pnote"><div class="prow">${caption ? '<span class="pcap">확률은 생활습관 관리용 참고 신호예요</span>' : ''}${btn}</div><p hidden>${PROB_NOTE}</p></div>`;
}

// 혈관 나이 카드 아래 줄: 같은 성별·연령대 상위 N%(참고용) + "계산 근거" 버튼
function ageNoteHtml(pc) {
  const chev = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 6l4.5 4.5L12.5 6"/></svg>';
  const btn = `<button type="button" aria-expanded="false" onclick="const p = this.closest('.pnote').querySelector('p'); p.hidden = !p.hidden; this.setAttribute('aria-expanded', String(!p.hidden))">계산 근거${chev}</button>`;
  const cap = percentileText(pc) ? `<span class="pcap">${percentileText(pc)} (참고용)</span>` : '';
  return `<div class="pnote agenote"><div class="prow">${cap}${btn}</div><p hidden>${AGE_BASIS}</p></div>`;
}

// 모델 B 단계 이름(서버 similarity_level)
const SIM_LEVEL = { similar: '비슷한 편이에요', slightly_different: '조금 달라요', different: '많이 달라요' };
// 모델 B 비교 칸(내 변화 탭·12주 결과): 소제목 → 처음: ○○ → (4주 후|지금): ○○ → 변화 칩 → 안내 → 비교 기준. 4주 재입력 화면과 같은 구성이다.
function simBoxHtml(m, afterLabel, chg) {
  const from = SIM_LEVEL[m.before_similarity_level], to = SIM_LEVEL[m.after_similarity_level];
  return `<div class="simbox">
    <span class="t">생활습관·체형 비교 (혈압이 정상인 사람들과)</span>
    ${from && to ? `<span class="s">처음: ${from} → ${afterLabel}: <b>${to}</b></span>` : ''}
    ${chg ? `<span class="b">${chg}</span>` : ''}
    <span class="a">허리둘레, 몸무게, 술은 내가 바꿀 수 있어요.</span></div>${simBasisHtml()}`;
}

// 모델 B "비교 기준": 확률 근거처럼 접었다 펼친다(처음 결과·4주 비교 화면)
const SIM_BASIS = '혈압이 정상인 한국 성인(국민건강영양조사 2022~2024)과 나이, 성별, BMI, 허리둘레, 부모님 고혈압, 흡연, 음주를 비교했어요.<br>혈압이 정상인 사람들 중 가운데쯤이면 ‘비슷한 편’, 4명 중 3명 안쪽이면 ‘조금 달라요’, 그보다 다르면 ‘많이 달라요’로 보여 드려요.<br>진단이 아니라, 생활습관과 체형을 돌아보는 참고 정보예요.';
function simBasisHtml() {
  const chev = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 6l4.5 4.5L12.5 6"/></svg>';
  const btn = `<button type="button" aria-expanded="false" onclick="const p = this.closest('.pnote').querySelector('p'); p.hidden = !p.hidden; this.setAttribute('aria-expanded', String(!p.hidden))">비교 기준${chev}</button>`;
  return `<div class="pnote"><div class="prow">${btn}</div><p hidden>${SIM_BASIS}</p></div>`;
}

// 모델 B: 서버가 주는 similarity_level(similar / slightly_different / different)을 말로만 보여 준다. 화면에서 기준값을 계산하지 않는다.
// 값이 아직 없으면(서버 미지원) 판정 문장은 빼고 설명만 보인다.
const SIM_NOW = { similar: '혈압이 정상인 사람들과 비슷한 편이에요', slightly_different: '혈압이 정상인 사람들과 조금 달라요', different: '혈압이 정상인 사람들과 많이 달라요' };
const SIM_RANK = { similar: 0, slightly_different: 1, different: 2 };
function simChangeText(before, after) {
  if (!(before in SIM_RANK) || !(after in SIM_RANK)) return '';
  return SIM_RANK[after] < SIM_RANK[before] ? '4주 전보다 더 비슷해졌어요' : SIM_RANK[after] === SIM_RANK[before] ? '비슷한 자리예요' : '조금 달라졌어요';
}

// 상담 권고가 필요한 경우의 제목. 혈압이 140/90 이상(진단 여부와 상관없이, 160/100 이상이면 "많이 높아요")이거나,
// 모델 A(10년 내 심장 혈관 건강 신호)가 "높음"(확률 9% 이상)일 때 뜬다. 아니면 ''.
function adviceTitle(pred, health) {
  if (!pred) return '';
  const very = health && (health.sbp >= 160 || health.dbp >= 100);
  const high = health && (health.sbp >= 140 || health.dbp >= 90);
  const aHigh = pred.model_a && pred.model_a.status === 'completed' && pred.model_a.risk_level === 'high';
  if (very || high) return `입력하신 혈압이 ${very ? '많이 ' : ''}높아요 (${health.sbp}/${health.dbp} mmHg)`;
  return aHigh ? '10년 내 심장 혈관 건강 신호가 높게 나왔어요' : '';
}
// 안내 문장: 고혈압 진단·치료 중이면 담당 의료진과 상담하도록, 진단이 없으면 가까운 의료기관을 안내한다.
function adviceText(pred) {
  return pred && pred.htn_status && pred.htn_status !== 'none' ? '치료 중이시라면 담당 의료진과 상담해 보세요.' : '가까운 의료기관에서 상담을 받아 보세요.';
}
const ADVICE_ACK_TEXT = '의료기관 상담 권고를 확인했고, 이를 확인한 뒤 챌린지를 진행하는 데 동의합니다.';
const adviceAcked = () => { try { return localStorage.getItem('paeon-advice-ack') === '1'; } catch (e) { return false; } };
const setAdviceAck = (v) => { try { v ? localStorage.setItem('paeon-advice-ack', '1') : localStorage.removeItem('paeon-advice-ack'); } catch (e) { /* 저장 못 해도 화면은 계속 */ } };
// 상담 권고 배너: X로 닫아도 챌린지는 계속 가능하고 다음 방문 때 다시 보인다. 확인 체크는 챌린지 시작 때 다시 묻는다.
// 이미 확인(체크)했으면 한 줄로 접어서 보여 주고, "다시 보기"를 누르면 원래 배너(문구 그대로)가 펼쳐진다.
function adviceFullHtml(title) {
  return `<div class="callout" id="advice-banner" style="border-color:var(--risk); position:relative; padding-right:44px"><button type="button" aria-label="닫기" onclick="document.getElementById('advice-banner').remove()" style="position:absolute; top:0; right:0; width:44px; height:44px; border:0; background:none; font-size:20px; line-height:1; color:var(--muted); cursor:pointer">×</button><b>${title}</b><br>${window.__adviceText || '가까운 의료기관에서 상담을 받아 보세요.'} <a href="guide.html" style="color:var(--accent-text); font-weight:700; display:inline-block; padding:8px 0">검사 · 상담 안내 보기</a>
    <label style="display:flex; gap:8px; align-items:flex-start; margin-top:10px; font-size:12.5px; line-height:1.5; cursor:pointer"><input type="checkbox" ${adviceAcked() ? 'checked' : ''} onchange="setAdviceAck(this.checked); if (this.checked) collapseAdvice()" style="margin-top:3px"><span>${ADVICE_ACK_TEXT}</span></label></div>`;
}
function adviceCompactHtml() {
  return `<div class="callout" id="advice-banner" style="border-color:var(--risk); display:flex; align-items:center; gap:10px; padding:6px 6px 6px 16px"><svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none; color:var(--accent-text)"><circle cx="8" cy="8" r="6.2"/><path d="M5.2 8.2l2 2 3.6-4"/></svg><span style="flex:1; font-size:14px; font-weight:700">의료기관 상담 권고를 확인했어요</span><button type="button" onclick="expandAdvice()" style="min-height:44px; padding:0 12px; border:0; background:none; font:inherit; font-size:13px; font-weight:700; color:var(--accent-text); text-decoration:underline; cursor:pointer">다시 보기</button></div>`;
}
function collapseAdvice() { setTimeout(() => { const b = document.getElementById('advice-banner'); if (b && adviceAcked()) b.outerHTML = adviceCompactHtml(); }, 500); }
function expandAdvice() { const b = document.getElementById('advice-banner'); if (b) b.outerHTML = adviceFullHtml(window.__adviceTitle || ''); }
function adviceBannerHtml(pred, health) {
  const title = adviceTitle(pred, health);
  if (!title) return '';
  window.__adviceTitle = title;
  window.__adviceText = adviceText(pred);
  return adviceAcked() ? adviceCompactHtml() : adviceFullHtml(title);
}

// 체험 모드: 서버가 3일 기록 뒤 나머지를 가상 기록으로 채운다. 패턴은 채운 순서대로 돌아가며 배정된다(코드: steady/wobble/fade). 후반에 놓침의 판정은 미완료다.
const DEMO_FILL_NAME = { steady: '꾸준함', wobble: '중간에 흔들림', fade: '후반에 놓침' };
const DEMO_FILL_ALL = Object.values(DEMO_FILL_NAME).join(' / ');
const DEMO_SURVEY_URL = 'https://docs.google.com/forms/d/e/1FAIpQLSdtcpL88OAx2zzD8Gx0ujL_BAGgB-OsSLedmYa_u15tV3DYMQ/viewform';
function demoFillHtml(rv) {
  const t = rv && rv.demo_fill && DEMO_FILL_NAME[rv.demo_fill];
  return t ? `<div class="callout"><b>체험용 가상 기록이 섞여 있어요</b><br>직접 기록하신 3일을 제외한 나머지 기간은 가상 기록이에요. 이번 체험에는 <b>"${t}"</b> 패턴이 적용됐어요(${DEMO_FILL_ALL} 중 하나). 패턴은 실제 기록과 무관하게 미리 배정돼요.<br>따라서 달성률에는 가상 기록이 포함되어 있으며, 실제 참여 결과를 의미하지 않아요.</div>` : '';
}
// 4주를 마치고 결과(전·후 비교)를 보는 모든 사람에게 화면 맨 아래에서 소감 설문을 안내한다(체험 결과 유무·패턴과 상관없이).
function demoSurveyHtml() {
  return `<div class="callout"><b>체험 소감을 남겨 주세요</b><br>결과를 보신 느낌을 알려 주시면 서비스를 고치는 데 큰 도움이 돼요.<br><a href="${DEMO_SURVEY_URL}" target="_blank" rel="noopener" style="display:inline-block; margin-top:8px; font-weight:700; color:var(--accent-d, #5C86AC)">설문 참여하기 ›</a></div>`;
}
// 체험이 끝났는데 4주 결과를 받지 못한 사람(3일 미달·중단, 3일을 채웠지만 결과 보기를 안 누른 사람)에게 보여 주는 안내
function demoEndedHtml() {
  return `<div class="callout"><b>체험 기간이 끝났어요. 함께해 주셔서 감사해요!</b><br>체험 기간이 끝나서 이번에는 4주 결과를 보여 드릴 수 없어요. 써 보신 느낌을 설문으로 남겨 주시면 서비스를 더 좋게 만드는 데 큰 도움이 돼요.<br><a href="${DEMO_SURVEY_URL}" target="_blank" rel="noopener" style="display:inline-block; margin-top:8px; font-weight:700; color:var(--accent-d, #5C86AC)">설문 참여하기 ›</a></div>`;
}
// 서버가 4주를 채웠을 때: 안내창을 보여 주고 4주 재입력 화면으로 보낸다.
async function showDemoResult(cycleId, pattern) {
  const pn = DEMO_FILL_NAME[pattern] || '';
  const P = (t) => `<span style="display:block;text-wrap:balance;margin-top:10px">${t}</span>`;
  await noticeDialog('4주 체험 결과를 준비했어요',
    P('체험판에서는 직접 기록하신 3일을 제외한 나머지 기간을 가상 기록으로 채웠어요.')
    + (pn ? P(`이번 체험에는 <b>‘${pn}’</b> 패턴이 적용됐어요. 패턴은 실제 기록과 무관하게 미리 배정돼요.`) : '')
    + P('따라서 달성률에는 가상 기록이 포함되어 있으며, 실제 참여 결과를 의미하지 않아요.')
    + P('이제 현재 상태를 입력하고 4주&nbsp;전후의 변화를 확인해 보세요!'), '지금 상태 입력하기');
  location.replace('reassessment.html?cycle=' + encodeURIComponent(cycleId));
}

// 모델 A 버전이 바뀌어 전·후를 비교할 수 없을 때(comparable=false, 둘 다 분석 완료) 비교 줄 대신 안내한다. 오류가 아니다.
function modelANoticeHtml(models) {
  const a = (models || []).find(m => m.model_code === 'MODEL_A');
  const changed = a && !a.comparable && (a.reason === 'model_version_changed' || (!a.reason && a.before_status === 'completed' && a.after_status === 'completed'));
  return changed
    ? '<p class="hint" style="margin:0 0 8px">모델이 업데이트되어 이번에는 비교하지 않아요. 다음 4주부터 비교해요.</p>' : '';
}

// ---- 캐릭터 그리기: 서버가 주는 조합 {body,color,expr,face,head} → 16x20 픽셀 SVG (시안 CharacterCreate의 그리기 코드)
const CHARACTER_DEFAULT = { body: 'mongle', color: '#AACDDC', eye: '#243749', expr: 'basic', face: 'none', head: 'none' };
function characterSvg(view, px) {
  const s = { ...CHARACTER_DEFAULT, ...(view || {}) };
  if (!/^#[0-9A-Fa-f]{6}$/.test(s.color)) s.color = CHARACTER_DEFAULT.color;
  if (!/^#[0-9A-Fa-f]{6}$/.test(s.eye)) s.eye = CHARACTER_DEFAULT.eye;
    const BODIES = {
      mongle: { top: 3, rows: ['................', '...oo......oo...', '..obbo....obbo..', '..obbboooobbbo..', '.obbbbbbbbbbbbo.', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', '.obbbbbbbbbbbbo.', '..obbbbbbbbbbo..', '..obboooooobbo..', '..oooo....oooo..'] },
      bobo: { top: 2, rows: ['................', '................', '.....oooooo.....', '...ooobbbbooo...', '..obbbbbbbbbbo..', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', '.obbbbbbbbbbbbo.', '..obbbbbbbbbbo..', '...obbbbbbbbo...', '....oooooooo....'] },
      rabbit: { top: 3, rows: ['...oooo..oooo...', '...obbo..obbo...', '...obbo..obbo...', '..ooobbbbbbooo..', '.obbbbbbbbbbbbo.', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', '.obbbbbbbbbbbbo.', '..obbbbbbbbbbo..', '...obbbbbbbbo...', '....oooooooo....'] },
      bear: { top: 3, rows: ['................', '..ooo......ooo..', '.obbbo....obbbo.', '.obbbboooobbbbo.', '.obbbbbbbbbbbbo.', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', '.obbbbbbbbbbbbo.', '..obbbbbbbbbbo..', '..obboooooobbo..', '..oooo....oooo..'] },
      ghost: { top: 2, rows: ['................', '................', '.....oooooo.....', '...ooobbbbooo...', '..obbbbbbbbbbo..', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbobbobbobbobbo', 'ooo.oo.oo.oo.ooo'] },
      dino: { top: 3, rows: ['................', '...o...o...o....', '..obo.obo.obo...', '.obbbbbbbbbbbbo.', '.obbbbbbbbbbbbo.', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', '.obbbbbbbbbbbbo.', '..obbbbbbbbbbo..', '..obboooooobbo..', '..oooo....oooo..'] },
      square: { top: 2, rows: ['................', '................', '..oooooooooooo..', '.obbbbbbbbbbbbo.', '.obbbbbbbbbbbbo.', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', '.obbbbbbbbbbbbo.', '..oooooooooooo..'] },
      cat: { top: 3, rows: ['................', '..o..........o..', '..oo........oo..', '..obboooooobbo..', '.obbbbbbbbbbbbo.', '.obhhbbbbbbbbbo.', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', 'obbbbbbbbbbbbbbo', '.obbbbbbbbbbbbo.', '..obbbbbbbbbbo..', '..obboooooobbo..', '..oooo....oooo..'] }
    };
    // 머리 장식이 몸 위로 삐져나와도 잘리지 않게 위에 4줄을 더 둔다 (좌표는 몸 기준 그대로 쓰고 put이 4줄을 더해 준다)
    const OFF = 4;
    const g = Array.from({ length: OFF }, () => Array(16).fill('.')).concat(BODIES[s.body].rows.map((r) => r.split('')));
    const put = (r, c, ch) => { if (r + OFF >= 0 && r + OFF < g.length && c >= 0 && c < 16) g[r + OFF][c] = ch; };
    const many = (list, ch) => list.forEach(([r, c]) => put(r, c, ch));
    const cheeks = [[9, 2], [9, 3], [9, 12], [9, 13]];
    const smile = [[10, 6], [10, 9], [11, 7], [11, 8]];
    const E = {
      basic: [[[7, 4], [7, 5], [8, 4], [8, 5], [7, 10], [7, 11], [8, 10], [8, 11], [10, 7], [10, 8]]],
      smile: [[[8, 4], [7, 5], [8, 6], [8, 9], [7, 10], [8, 11]].concat(smile)],
      sleepy: [[[8, 4], [8, 5], [8, 10], [8, 11], [10, 7]]],
      wow: [[[7, 4], [7, 5], [8, 4], [8, 5], [9, 4], [9, 5], [7, 10], [7, 11], [8, 10], [8, 11], [9, 10], [9, 11], [10, 7], [10, 8], [11, 7], [11, 8]]],
      wink: [[[8, 4], [8, 5], [7, 10], [7, 11], [8, 10], [8, 11]].concat(smile)],
      heart: [smile],
      angry: [[[8, 4], [8, 5], [8, 10], [8, 11], [6, 4], [7, 5], [7, 10], [6, 11], [11, 6], [11, 7], [11, 8], [11, 9]]],
      cry: [[[7, 4], [7, 5], [8, 4], [8, 5], [7, 10], [7, 11], [8, 10], [8, 11], [11, 6], [11, 7], [11, 8], [11, 9]]],
      sparkle: [smile]
    };
    const EXTRA = {
      heart: [['r', [[7, 4], [7, 6], [8, 4], [8, 5], [8, 6], [9, 5], [7, 9], [7, 11], [8, 9], [8, 10], [8, 11], [9, 10]]]],
      cry: [['t', [[9, 4], [10, 4], [9, 11], [10, 11]]]],
      sparkle: [['y', [[7, 5], [8, 4], [8, 5], [8, 6], [9, 5], [7, 10], [8, 9], [8, 10], [8, 11], [9, 10]]]]
    };
    many(cheeks, 'c');
    many(E[s.expr][0], 'e');
    (EXTRA[s.expr] || []).forEach(([ch, list]) => many(list, ch));

    // 얼굴 아이템: 눈(행 7~8)·입(행 10~11) 자리와 겹치지 않게, 눈·입을 가리는 것만 먼저 비운 뒤 그린다. 'a' 테, 'x' 마스크 주름
    const clear = (rs, cs) => rs.forEach((r) => cs.forEach((c) => put(r, c, 'b')));
    const rng = (a, z) => Array.from({ length: z - a + 1 }, (_, k) => a + k);
    if (s.face === 'glasses') {
      // 렌즈 안은 비워 둬서 눈이 그대로 보인다
      [[3, 6], [9, 12]].forEach(([c0, c1]) => {
        rng(c0, c1).forEach((c) => { put(6, c, 'a'); put(9, c, 'a'); });
        [7, 8].forEach((r) => { put(r, c0, 'a'); put(r, c1, 'a'); });
      });
      put(7, 7, 'a'); put(7, 8, 'a');
    }
    if (s.face === 'shades') {
      [[3, 6], [9, 12]].forEach(([c0, c1]) => { rng(c0, c1).forEach((c) => { put(7, c, 'o'); put(8, c, 'o'); }); });
      put(7, 7, 'o'); put(7, 8, 'o'); put(7, 4, 'w'); put(7, 10, 'w');   // 반짝이는 점
    }
    if (s.face === 'mask') {
      clear([10, 11, 12], rng(4, 11));
      rng(4, 11).forEach((c) => { put(10, c, 'w'); put(11, c, 'w'); put(12, c, 'w'); });
      rng(5, 10).forEach((c) => put(11, c, 'x'));   // 가운데 주름
      put(10, 3, 'o'); put(10, 12, 'o');            // 귀에 거는 끈
    }
    if (s.face === 'whiskers') {   // 뺨에서 몸 테두리 쪽으로 퍼지는 세 줄씩 (위는 살짝 위로, 가운데는 곧게, 아래는 살짝 아래로)
      many([[8, 1], [8, 2], [10, 1], [10, 2], [10, 3], [12, 2], [12, 3], [8, 13], [8, 14], [10, 12], [10, 13], [10, 14], [12, 12], [12, 13]], 'o');
      clear([9], [2, 3, 12, 13]);
    }
    if (s.face === 'freckles') { many([[9, 3], [10, 2], [10, 4], [9, 12], [10, 13], [10, 11]], 'k'); }
    if (s.face === 'mustache') {   // 프링글스 아저씨 콧수염: 코 밑이 살짝 솟고 양 끝이 위로 말린 작은 곡선. 입은 수염에 가려진다
      clear([10, 11, 12], rng(4, 11));
      many([[10, 4], [10, 7], [10, 8], [10, 11]].concat(rng(5, 10).map((c) => [11, c])), 'o');
    }
    if (s.face === 'eyepatch') {   // 왼쪽 눈을 덮는 둥근 안대. 끈은 오른쪽 위로 이마를 넘어가고, 왼쪽은 아래로 내려간다
      clear([7, 8, 9], rng(3, 6));
      many([[7, 4], [7, 5], [8, 3], [8, 4], [8, 5], [8, 6], [9, 4], [9, 5]], 'o');
      many([[6, 6], [5, 7], [5, 8], [4, 9], [9, 3], [10, 2], [11, 1]], 'o');
    }
    // 머리 장식: b는 머리 맨 위 테두리 줄. 장식은 이 줄과 겹치게(머리 위에 얹은 것처럼) 몸 앞에 그린다
    const b = BODIES[s.body].top;
    const H = {
      sprout: [['g', [[b - 1, 7], [b - 2, 7], [b - 3, 6], [b - 3, 8], [b - 2, 6], [b - 2, 8]]]],
      crown: [['y', [[b - 2, 5], [b - 2, 7], [b - 2, 8], [b - 2, 10], [b - 1, 5], [b - 1, 6], [b - 1, 7], [b - 1, 8], [b - 1, 9], [b - 1, 10], [b, 5], [b, 6], [b, 7], [b, 8], [b, 9], [b, 10]]]],
      bow: [['r', [[b - 1, 10], [b - 1, 12], [b, 10], [b, 12], [b + 1, 10], [b + 1, 12]]], ['y', [[b, 11]]]],
      flower: [['r', [[b - 1, 11], [b, 10], [b, 12], [b + 1, 11]]], ['y', [[b, 11]]]],
      star: [['y', [[b - 3, 8], [b - 2, 7], [b - 2, 8], [b - 2, 9], [b - 1, 8]]]],
      halo: [['y', [[b - 3, 6], [b - 3, 7], [b - 3, 8], [b - 3, 9], [b - 2, 5], [b - 2, 10], [b - 1, 6], [b - 1, 7], [b - 1, 8], [b - 1, 9]]]],
      horns: [['r', [[b, 4], [b - 1, 4], [b - 2, 3], [b, 11], [b - 1, 11], [b - 2, 12]]]],
      party: [['r', [[b, 5], [b, 6], [b, 7], [b, 8], [b, 9], [b, 10], [b - 1, 6], [b - 1, 7], [b - 1, 8], [b - 1, 9], [b - 2, 7], [b - 2, 8]]], ['y', [[b - 3, 7], [b - 3, 8]]]]
    };
    (H[s.head] || []).forEach(([ch, list]) => many(list, ch));

    const fills = { k: '#B5835A', t: '#7FB6E8', o: '#243749', e: '#243749', m: '#243749', b: s.color, h: '#FFFFFF', c: '#E8B9A5', g: '#6FA58A', y: '#F2C94C', r: '#E58F9B', w: '#DCE8EF', a: '#5C86AC', x: '#B8CDD9' };
  let rects = '';
  g.forEach((row, y) => row.forEach((ch, x) => { const col = ch === 'e' && y - OFF <= 9 ? s.eye : fills[ch]; if (col) rects += `<rect x="${x}" y="${y}" width="1" height="1" fill="${col}"/>`; }));   // 눈(몸 칸 9행 위)만 눈 색, 입은 짙은 색
  const w = px || 40;
  return `<svg width="${w}" height="${Math.round(w * 1.25)}" viewBox="0 0 16 20" shape-rendering="crispEdges" role="img" aria-label="캐릭터">${rects}</svg>`;
}

// 홈 화면에 추가(PWA)할 수 있게 매니페스트를 연결한다. 아이폰은 설치한 앱에서만 푸시를 받는다.
(function () {
  if (document.querySelector('link[rel="manifest"]')) return;
  const l = document.createElement('link'); l.rel = 'manifest'; l.href = 'manifest.webmanifest'; document.head.appendChild(l);
  const t = document.createElement('link'); t.rel = 'apple-touch-icon'; t.href = 'assets/img/icon-192.png'; document.head.appendChild(t);
})();

// 가입 감사 파이: 기간 안에 가입한 분에게만 "파이 받기" 카드를 보인다(서버가 대상·기한·중복을 판단). 자리표시(id="thanks-slot")가 있는 화면에서 mountThanksCard()를 부른다.
let _thanks = null;
async function mountThanksCard() {
  const slot = document.getElementById('thanks-slot');
  if (!slot || typeof apiCall !== 'function' || !loggedIn()) return;
  if (_thanks === null) {
    try { _thanks = (await apiCall('GET', '/pie/thanks', undefined, '')).data; } catch (e) { _thanks = { eligible: false, claimed: true }; }
  }
  if (!_thanks.eligible || _thanks.claimed) { slot.innerHTML = ''; return; }
  slot.innerHTML = `<div style="background:var(--cream); border-radius:20px; padding:18px 18px 16px; display:flex; flex-direction:column; gap:6px">
    <b style="font-size:17px">가입 감사 선물 🎁</b>
    <span style="font-size:13.5px; line-height:1.6; color:var(--body)">10월 22~23일에 가입해 주셔서 감사해요.<br>감사의 마음으로 파이 ${_thanks.amount}개를 드려요.</span>
    <span id="thanks-err" style="font-size:13px; color:var(--risk)" hidden></span>
    <button type="button" class="cta" id="thanks-go" style="margin-top:6px">파이 ${_thanks.amount}개 받기</button></div>`;
  document.getElementById('thanks-go').addEventListener('click', async (e) => {
    const b = e.currentTarget; b.disabled = true;
    try {
      await apiCall('POST', '/pie/thanks', undefined, '파이를 받지 못했어요');
      _thanks.claimed = true;
      slot.innerHTML = `<div style="background:var(--cream); border-radius:20px; padding:18px; text-align:center"><b style="font-size:16px">파이 ${_thanks.amount}개를 받았어요 🎉</b><br><span style="font-size:13.5px; color:var(--body)">감사합니다. 상단 파이 숫자를 확인해 보세요.</span></div>`;
      setTimeout(() => location.reload(), 1600);
    } catch (err) { const m = document.getElementById('thanks-err'); m.textContent = friendlyError(err); m.hidden = false; b.disabled = false; }
  });
}

// 아래로 당겨서 새로고침(모바일). 화면 맨 위에서 손가락을 아래로 80px 이상 끌었다 놓으면 onRefresh()를 부른다. 위쪽에 "당겨서 새로고침"/"놓으면 새로고침" 안내가 나온다.
function enablePullToRefresh(onRefresh) {
  if (!('ontouchstart' in window)) return;   // 터치 화면에서만
  let y0 = null, dist = 0, busy = false;
  const bar = document.createElement('div');
  bar.setAttribute('aria-live', 'polite');
  bar.style.cssText = 'position:fixed; left:50%; top:0; transform:translate(-50%,-48px); z-index:70; padding:8px 16px; border-radius:0 0 16px 16px; background:var(--cream); color:var(--ink); font-size:13px; font-weight:700; transition:transform .15s; pointer-events:none';
  document.body.appendChild(bar);
  const show = (t, px) => { bar.textContent = t; bar.style.transform = `translate(-50%, ${px}px)`; };
  const hide = () => { bar.style.transform = 'translate(-50%,-48px)'; };
  window.addEventListener('touchstart', (e) => { y0 = (window.scrollY <= 0 && !busy && e.touches.length === 1) ? e.touches[0].clientY : null; dist = 0; }, { passive: true });
  window.addEventListener('touchmove', (e) => {
    if (y0 === null) return;
    dist = e.touches[0].clientY - y0;
    if (dist > 8 && window.scrollY <= 0) show(dist >= 80 ? '놓으면 새로고침' : '당겨서 새로고침', Math.min(dist / 3, 40) - 4); else hide();
  }, { passive: true });
  window.addEventListener('touchend', async () => {
    const go = y0 !== null && dist >= 80 && window.scrollY <= 0; y0 = null;
    if (!go) { hide(); return; }
    busy = true; show('새로고침하는 중…', 8);
    try { await onRefresh(); } catch (e) { /* 실패는 각 화면이 목록 자리에 안내한다 */ }
    busy = false; hide();
  }, { passive: true });
}
