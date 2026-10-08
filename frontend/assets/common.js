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

function renderHeader(){
  const slot = document.getElementById('header-slot');
  if (!slot) return;
  slot.innerHTML = `
    <div class="picker">
      <a class="brand" href="index.html">${PAEON_LOGO_SVG} PAEON</a>
    </div>`;
}

const NAV_ITEMS = [
  { icon: '🏠', label: '홈', href: 'dashboard.html', pages: ['dashboard.html'] },
  { icon: '🩺', label: '건강정보', href: 'health-info.html', pages: ['health-info.html', 'survey.html', 'review.html'] },
  { icon: '🎯', label: '챌린지', href: localStorage.getItem('paeon-cycle') ? 'challenge-progress.html' : 'challenges.html', pages: ['challenges.html', 'challenge-progress.html'] },
  { icon: '📝', label: '내 기록', href: 'trend.html', pages: ['trend.html'] },
  { icon: '👤', label: '마이페이지', href: 'mypage.html', pages: ['mypage.html'] },
];
const NO_NAV_PAGES = ['index.html', 'signup.html', 'login.html', 'eligibility.html', 'privacy.html', 'my-data.html'];

function renderNav(){
  const body = document.querySelector('.frame-body');
  if (!body || body.querySelector('.app-shell')) return;
  const page = location.pathname.split('/').pop() || 'index.html';
  if (NO_NAV_PAGES.includes(page)) return;
  const shell = document.createElement('div');
  shell.className = 'app-shell';
  const navCol = document.createElement('div');
  navCol.className = 'nav-col';
  navCol.innerHTML = NAV_ITEMS.map(it => `<a class="nav-item${it.pages.includes(page) ? ' active' : ''}" href="${it.href}">${it.icon} ${it.label}</a>`).join('');
  const contentCol = document.createElement('div');
  contentCol.className = 'content-col';
  while (body.firstChild) contentCol.appendChild(body.firstChild);
  shell.appendChild(navCol);
  shell.appendChild(contentCol);
  body.appendChild(shell);
}

// 처음 시작하는 4단계(대상 확인 → 건강정보 → 설문 → 위험도 분석)의 진행 상태와 다음 할 일. 대시보드와 입력 검토 화면의 안내에 쓴다.
function setupProgress() {
  const has = (k) => { try { return !!JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return false; } };
  const steps = [
    { label: '대상 확인', done: has('paeon-eligibility'), href: 'eligibility.html' },
    { label: '건강정보 입력', done: has('paeon-health'), href: 'health-info.html' },
    { label: '생활습관 설문', done: has('paeon-survey'), href: 'survey.html' },
    { label: '위험도 분석', done: has('paeon-prediction'), href: 'review.html' },
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

document.addEventListener('DOMContentLoaded', () => { renderHeader(); renderNav(); addPasswordToggles(); });
