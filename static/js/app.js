/* Shared helpers: CSRF-aware fetch, toasts, sidebar toggle, chart loader. */
(function () {
  const csrf = () => document.querySelector('meta[name=csrf-token]')?.content || '';

  window.toast = function (msg, kind) {
    const box = document.getElementById('toasts');
    if (!box) return;
    const el = document.createElement('div');
    el.className = 'toast ' + (kind || '');
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => el.remove(), 5000);
  };

  /** api(url, {method, json, form}) -> {ok, status, data}. Never throws; network errors return ok:false. */
  window.api = async function (url, opts) {
    opts = opts || {};
    const init = { method: opts.method || 'GET', headers: { 'X-CSRF-Token': csrf() }, credentials: 'same-origin' };
    if (opts.json !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.json); init.method = opts.method || 'POST'; }
    if (opts.form) { init.body = opts.form; init.method = opts.method || 'POST'; }
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), opts.timeout || 120000);
      init.signal = ctl.signal;
      const res = await fetch(url, init);
      clearTimeout(t);
      let data = null;
      try { data = await res.json(); } catch (e) { /* non-JSON */ }
      return { ok: res.ok, status: res.status, data: data || {} };
    } catch (e) {
      return { ok: false, status: 0, data: { error: e.name === 'AbortError' ? 'The request timed out. Please retry.' : 'Network error. Check your connection and retry.' }, network: true };
    }
  };

  window.scoreClass = v => (v == null ? 'muted' : v >= 75 ? 'good' : v >= 50 ? 'ok' : 'bad');
  window.esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const toggle = document.getElementById('navToggle'), side = document.getElementById('sidebar');
  if (toggle && side) {
    toggle.addEventListener('click', () => side.classList.toggle('open'));
    document.addEventListener('click', e => { if (side.classList.contains('open') && !side.contains(e.target) && e.target !== toggle && !toggle.contains(e.target)) side.classList.remove('open'); });
  }

  /** Load Chart.js from CDN once; resolves null if it cannot load (pages show a text fallback). */
  window.loadChart = function () {
    if (window.Chart) return Promise.resolve(window.Chart);
    return new Promise(resolve => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
      s.onload = () => {
        Chart.defaults.color = '#A5A5B8'; Chart.defaults.borderColor = '#262a42'; Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
        resolve(window.Chart);
      };
      s.onerror = () => resolve(null);
      document.head.appendChild(s);
    });
  };
})();
