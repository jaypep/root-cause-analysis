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
      navBtn('/manage', 'Manage Garden') +
    '</div>' +
    '<div style="display:flex;align-items:center;gap:10px;">' +
      '<div style="text-align:right;">' +
        '<div id="clock" style="font-size:1.3rem;font-weight:300;letter-spacing:0.05em;">--:--</div>' +
        '<div id="date" style="font-size:0.72rem;color:var(--muted);"></div>' +
      '</div>' +
      navBtn('/settings', '⚙ Settings') +
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

// Works whether defer or not
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', buildHeader);
} else {
  buildHeader();
}
