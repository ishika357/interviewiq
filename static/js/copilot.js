/* Interview Copilot chat widget (uses global IID set by the results page). */
(function () {
  const log = document.getElementById('chatLog'), form = document.getElementById('chatForm'), input = document.getElementById('chatIn');
  let busy = false;
  function add(text, cls, sources) {
    const d = document.createElement('div'); d.className = 'msg ' + cls; d.textContent = text;
    if (sources && sources.length) {
      const s = document.createElement('div'); s.className = 'small muted'; s.style.marginTop = '8px';
      s.textContent = 'Sources: ' + sources.map(x => `${x.source} / ${x.section}`).join('; ');
      d.appendChild(s);
    }
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  async function ask(q) {
    if (busy || !q.trim()) return;
    busy = true; add(q, 'me'); input.value = '';
    const wait = add('Thinking...', 'bot');
    const r = await api(`/api/interviews/${IID}/copilot`, { json: { message: q } });
    wait.remove();
    if (!r.ok) add(r.data.error || 'Something went wrong. Try again.', 'bot');
    else add(r.data.answer + (r.data.mode === 'llm' ? '' : ''), 'bot', r.data.sources);
    busy = false;
  }
  form.addEventListener('submit', e => { e.preventDefault(); ask(input.value); });
  document.querySelectorAll('.suggest [data-q]').forEach(b => b.addEventListener('click', () => ask(b.dataset.q)));
})();
