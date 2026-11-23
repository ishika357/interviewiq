/* Coding practice page. Code is sent to /api/coding/<id>/run|submit and executed in the server-side sandbox. */
(function () {
  const code = document.getElementById('code'), out = document.getElementById('result');
  const runBtn = document.getElementById('runBtn'), subBtn = document.getElementById('submitBtn');
  let busy = false;

  code.addEventListener('keydown', e => {
    if (e.key === 'Tab') { e.preventDefault(); const s = code.selectionStart; code.setRangeText('    ', s, code.selectionEnd, 'end'); }
  });
  document.getElementById('resetBtn').onclick = () => { if (confirm('Reset to the starter code?')) code.value = STARTER; };

  const j = v => { try { return JSON.stringify(v); } catch (e) { return String(v); } };
  function renderResults(d, submitted) {
    let h = '';
    if (d.error && !d.results.length) h += `<div class="banner err">${esc(d.error)}</div>`;
    if (d.compile_error) h += `<div class="banner err"><strong>Error</strong><pre class="out">${esc(d.compile_error)}</pre></div>`;
    if (d.results.length) {
      h += `<div class="row between"><strong>${d.passed} / ${d.total} tests passed</strong><span class="chip ${d.passed === d.total ? 'good' : 'bad'}">${d.passed === d.total ? 'All passed' : 'Not yet'}</span></div>`;
      h += d.results.map(r => `<div class="test"><span class="chip ${r.passed ? 'good' : 'bad'}">${r.passed ? 'PASS' : 'FAIL'}</span><div style="min-width:0;flex:1">
        <div class="small">Test ${r.n}${r.hidden ? ' (hidden)' : ''} ${r.ms != null ? `<span class="muted">- ${r.ms} ms</span>` : ''}</div>
        ${!r.hidden && !r.passed ? `<div class="small muted">expected ${esc(j(r.expected))}, got ${esc(j(r.got))}</div>` : ''}
        ${r.error ? `<pre class="out">${esc(r.error)}</pre>` : ''}${r.stdout ? `<div class="small muted">Output:</div><pre class="out">${esc(r.stdout)}</pre>` : ''}</div></div>`).join('');
    }
    if (submitted && d.feedback) {
      const f = d.feedback, c = f.complexity || {};
      h += `<div class="card flat stack" style="margin-top:14px"><h3>${'AI feedback'}</h3>
        <div class="grid g2"><div><div class="small muted">Estimated time</div><strong>${esc(c.time)}</strong><div class="small muted">${esc(c.basis || '')}</div></div>
        <div><div class="small muted">Estimated space</div><strong>${esc(c.space)}</strong></div></div>
        <div class="small muted">Optimal for this problem: time ${esc(c.optimal_time)}, space ${esc(c.optimal_space)}. Complexity figures are static estimates from your code's structure.</div>
        ${f.strengths.length ? `<ul class="clean good">${f.strengths.map(s => `<li>${esc(s)}</li>`).join('')}</ul>` : ''}
        ${f.suggestions.length ? `<div><strong>Suggestions</strong><ul class="clean">${f.suggestions.map(s => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}
        ${f.ai_review ? `<div><strong>LLM review</strong><p class="small" style="white-space:pre-wrap">${esc(f.ai_review)}</p></div>` : ''}</div>`;
    }
    out.innerHTML = h;
  }
  async function go(kind) {
    if (busy) return;
    busy = true; runBtn.disabled = subBtn.disabled = true;
    out.innerHTML = '<div class="row"><span class="spinner"></span> Running in sandbox...</div>';
    const r = await api(`/api/coding/${PID}/${kind}`, { json: { code: code.value }, timeout: 60000 });
    busy = false; runBtn.disabled = subBtn.disabled = false;
    if (!r.ok) { out.innerHTML = `<div class="banner err">${esc(r.data.error || 'Request failed')}</div>`; return; }
    renderResults(r.data, kind === 'submit');
  }
  runBtn.onclick = () => go('run');
  subBtn.onclick = () => go('submit');
})();
