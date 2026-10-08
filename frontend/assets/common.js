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
const NO_NAV_PAGES = ['index.html', 'signup.html', 'login.html', 'eligibility.html', 'privacy.html'];

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
