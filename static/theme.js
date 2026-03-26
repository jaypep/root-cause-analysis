// ── Inject shared CSS ──────────────────────────────────────────────────────
(function() {
  var css = [
    // CSS variables — light
    ':root {',
    '  --bg: #f4f7f0; --bg2: #eaf0e4; --bg3: #dde8d5;',
    '  --border: rgba(141,184,122,0.35); --border2: #8db87a;',
    '  --text: #1e2d17; --text2: #3d5c2e; --text3: #6b8f5a;',
    '  --green: #3a7a28; --green-dim: #5a8a46;',
    '  --amber: #8a6a10; --red: #8a3a2a;',
    '  --blue: #2a5c7a; --blue-dim: #1a3c5a;',
    '  --surface: #eaf0e4; --muted: #6b8f5a; --radius: 16px;',
    '}',
    // CSS variables — dark
    ':root.dark {',
    '  --bg: #0d1109; --bg2: #141a10; --bg3: #1c2417;',
    '  --border: rgba(141,184,122,0.18); --border2: #3d5430;',
    '  --text: #c8d5b9; --text2: #7a9068; --text3: #4a5e3a;',
    '  --green: #8db87a; --green-dim: #4a7a28;',
    '  --amber: #d4942a; --red: #c0443a;',
    '  --blue: #4a90a4; --blue-dim: #2d5f70;',
    '  --surface: #182417; --muted: #6a8060; --radius: 16px;',
    '}',
    // Reset
    '*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }',
    // Body base
    'body {',
    '  font-family: "DM Sans", sans-serif; background: var(--bg); color: var(--text);',
    '  height: 100dvh; display: grid; grid-template-rows: auto 1fr; overflow: hidden;',
    '  font-size: 16px;',
    '}',
    // Header
    '#site-header {',
    '  display: flex; align-items: center; justify-content: space-between;',
    '  padding: 0 28px; height: 60px;',
    '  border-bottom: 1px solid var(--border);',
    '  flex-shrink: 0; gap: 12px; background: var(--bg2);',
    '}',
    '.site-title {',
    '  font-family: "Playfair Display", serif; font-size: 1.35rem;',
    '  font-weight: 500; color: var(--green); white-space: nowrap;',
    '}',
    // Nav buttons
    '.nav-btn {',
    '  background: var(--surface); border: 1px solid var(--border);',
    '  border-radius: 10px; color: var(--muted); font-family: "DM Sans", sans-serif;',
    '  font-size: 1rem; font-weight: 500; padding: 11px 22px; min-height: 46px;',
    '  cursor: pointer; text-decoration: none; display: inline-flex;',
    '  align-items: center; gap: 8px;',
    '  transition: border-color 0.15s, color 0.15s, background 0.15s;',
    '  white-space: nowrap;',
    '}',
    '.nav-btn:hover { border-color: var(--border2); color: var(--text); }',
    '.nav-active { border-color: var(--green) !important; color: var(--green) !important; background: var(--bg2) !important; }',
    // Common utility
    '.empty { color: var(--muted); font-size: 1rem; padding: 24px; text-align: center; }',
    '.panel {',
    '  background: var(--surface); border: 1px solid var(--border);',
    '  border-radius: var(--radius); box-shadow: 0 1px 4px rgba(0,0,0,0.06);',
    '  display: flex; flex-direction: column; overflow: hidden;',
    '}',
    '.panel-header {',
    '  padding: 14px 20px; border-bottom: 1px solid var(--border);',
    '  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;',
    '}',
    '.panel-label {',
    '  font-size: 0.8rem; font-weight: 500; text-transform: uppercase;',
    '  letter-spacing: 0.12em; color: var(--muted);',
    '}',
    // Form fields
    '.field { display: flex; flex-direction: column; gap: 6px; }',
    '.field label {',
    '  font-size: 0.8rem; font-weight: 500; color: var(--muted);',
    '  text-transform: uppercase; letter-spacing: 0.08em;',
    '}',
    '.field input, .field select, .field textarea {',
    '  background: var(--bg); border: 1px solid var(--border);',
    '  border-radius: 10px; color: var(--text); font-family: "DM Sans", sans-serif;',
    '  font-size: 1rem; padding: 12px 14px; width: 100%; outline: none;',
    '  transition: border-color 0.15s;',
    '}',
    '.field input:focus, .field select:focus, .field textarea:focus { border-color: var(--green-dim); }',
    '.field select option { background: var(--bg2); }',
    '.field textarea { resize: vertical; min-height: 70px; }',
    // Primary button
    '.btn-primary {',
    '  background: var(--green-dim); border: none; border-radius: 10px; color: #fff;',
    '  font-family: "DM Sans", sans-serif; font-size: 1rem; font-weight: 500;',
    '  padding: 14px; cursor: pointer; width: 100%; transition: background 0.15s;',
    '}',
    '.btn-primary:hover { background: var(--green); }',
    '.btn-primary:active { transform: scale(0.97); }',
    // Tabs
    '.tab {',
    '  padding: 14px 22px; font-family: "DM Sans", sans-serif;',
    '  font-size: 1rem; font-weight: 500; color: var(--muted);',
    '  background: none; border: none; border-bottom: 2px solid transparent;',
    '  cursor: pointer; transition: color 0.15s, border-color 0.15s; margin-bottom: -1px;',
    '}',
    '.tab:hover { color: var(--text); }',
    '.tab.active { color: var(--green); border-bottom-color: var(--green); }',
  ].join('\n');

  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);
})();

// ── Theme toggle ───────────────────────────────────────────────────────────
(function() {
  var saved = localStorage.getItem('rca-theme');
  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (saved ? saved === 'dark' : prefersDark) document.documentElement.classList.add('dark');
})();

function toggleTheme() {
  var isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('rca-theme', isDark ? 'dark' : 'light');
  updateThemeBtn(isDark);
}

function updateThemeBtn(isDark) {
  document.querySelectorAll('.theme-toggle-text').forEach(function(el) {
    el.textContent = isDark ? '☀' : '☾';
  });
}

// ── Build header ───────────────────────────────────────────────────────────
function buildHeader() {
  var el = document.getElementById('site-header');
  if (!el) return;

  var isDark = document.documentElement.classList.contains('dark');
  var path = window.location.pathname;

  function navBtn(href, label) {
    var isActive = href === '/' ? path === '/' : path.indexOf(href) === 0;
    return '<a class="nav-btn' + (isActive ? ' nav-active' : '') + '" href="' + href + '">' + label + '</a>';
  }

  el.innerHTML =
    '<div style="display:flex;align-items:center;gap:14px;">' +
      '<span class="site-title">🌱 Root Cause Analysis</span>' +
      navBtn('/', 'Dashboard') +
      navBtn('/tasks', 'Tasks') +
      navBtn('/seeds', 'Seeds') +
      navBtn('/plants', 'Plants') +
      navBtn('/manage', 'Manage Garden') +
    '</div>' +
    '<div style="display:flex;align-items:center;gap:10px;">' +
      '<div style="text-align:right;">' +
        '<div id="clock" style="font-size:1.3rem;font-weight:300;letter-spacing:0.05em;">--:--</div>' +
        '<div id="date" style="font-size:0.85rem;color:var(--muted);"></div>' +
      '</div>' +
      navBtn('/settings', '⚙ Settings') +
      navBtn('/help', 'Help') +
      '<button class="nav-btn" onclick="toggleTheme()">' +
        '<span class="theme-toggle-text">' + (isDark ? '☀' : '☾') + '</span> Toggle Theme' +
      '</button>' +
    '</div>';

  updateThemeBtn(isDark);

  function tick() {
    var now = new Date();
    var c = document.getElementById('clock');
    var d = document.getElementById('date');
    if (c) c.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (d) d.textContent = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
  }
  tick();
  setInterval(tick, 1000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', buildHeader);
} else {
  buildHeader();
}
