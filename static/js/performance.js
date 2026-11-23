/* Analytics charts. Data object P comes from the database via the server (see /api/analytics). */
(function () {
  const heat = document.getElementById('heat');
  const diffs = [1, 2, 3], dl = ['', 'Easy', 'Medium', 'Hard'];
  const topics = [...new Map(P.heatmap.map(c => [c.topic, c.label]))];
  heat.style.gridTemplateColumns = '170px repeat(3, 1fr)';
  let html = '<div></div>' + diffs.map(d => `<div class="hl" style="justify-content:center">${dl[d]}</div>`).join('');
  for (const [t, label] of topics) {
    html += `<div class="hl">${esc(label)}</div>`;
    for (const d of diffs) {
      const c = P.heatmap.find(x => x.topic === t && x.difficulty === d);
      if (!c) { html += '<div class="cell" style="background:var(--bg2);color:var(--muted)">-</div>'; continue; }
      const bg = c.avg >= 75 ? 'rgba(61,220,151,.28)' : c.avg >= 50 ? 'rgba(245,184,61,.28)' : 'rgba(255,107,129,.32)';
      html += `<div class="cell" style="background:${bg}" title="${c.n} answer(s)">${Math.round(c.avg)}</div>`;
    }
  }
  heat.innerHTML = html;

  loadChart().then(C => {
    if (!C) { document.getElementById('chartFallback').hidden = false; return; }
    const lab = P.interviews.map((i, n) => '#' + (n + 1) + ' ' + i.label);
    const opts = (extra) => Object.assign({ maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } } }, extra || {});
    new C(document.getElementById('cTrend'), { type: 'line', data: { labels: lab, datasets: [{ label: 'Overall', data: P.interviews.map(i => i.overall), borderColor: '#8667F5', backgroundColor: 'rgba(134,103,245,.18)', fill: true, tension: .3 }] }, options: opts({ plugins: { legend: { display: false } } }) });
    new C(document.getElementById('cCompare'), { type: 'bar', data: { labels: lab, datasets: [
      { label: 'Technical', data: P.interviews.map(i => i.technical), backgroundColor: '#8667F5', borderRadius: 6 },
      { label: 'Communication', data: P.interviews.map(i => i.communication), backgroundColor: '#35C9E7', borderRadius: 6 }] }, options: opts() });
    new C(document.getElementById('cTopics'), { type: 'bar', data: { labels: P.topics.map(t => t.label), datasets: [{ data: P.topics.map(t => t.avg), backgroundColor: P.topics.map(t => t.avg >= 75 ? '#3ddc97' : t.avg >= 50 ? '#f5b83d' : '#ff6b81'), borderRadius: 6 }] },
      options: opts({ indexAxis: 'y', scales: { x: { min: 0, max: 100 } }, plugins: { legend: { display: false } } }) });
    new C(document.getElementById('cDiff'), { type: 'bar', data: { labels: P.difficulty.map(d => dl[d.difficulty] + ` (n=${d.n})`), datasets: [{ label: 'Average score', data: P.difficulty.map(d => d.avg), backgroundColor: '#8667F5', borderRadius: 6 }, { label: 'Technical', data: P.difficulty.map(d => d.technical), backgroundColor: '#35C9E7', borderRadius: 6 }] }, options: opts() });
  });
})();
