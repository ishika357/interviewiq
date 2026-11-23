/* Interview setup wizard: 6 steps, resume preview, camera/mic test, then create the interview. */
(function () {
  const form = document.getElementById('wiz');
  const panels = [...form.querySelectorAll('[data-panel]')];
  const stepEls = [...document.querySelectorAll('#steps .s')];
  const nextBtn = document.getElementById('next'), backBtn = document.getElementById('back');
  let step = 1, stream = null, raf = 0, audioCtx = null, resumeFile = null, starting = false;
  const LAST = panels.length;

  const val = n => (form.querySelector(`[name=${n}]`) && form.querySelector(`[name=${n}]:checked`)?.value) || '';
  const roleOther = () => val('role') === 'Other';

  form.querySelectorAll('[name=role]').forEach(r => r.addEventListener('change', () => {
    document.getElementById('customWrap').hidden = !roleOther();
  }));

  function show(n) {
    step = n;
    panels.forEach(p => p.hidden = +p.dataset.panel !== n);
    stepEls.forEach((s, i) => { s.classList.toggle('on', i + 1 === n); s.classList.toggle('done', i + 1 < n); });
    backBtn.style.visibility = n === 1 ? 'hidden' : 'visible';
    nextBtn.innerHTML = n === LAST ? 'Start interview' : 'Next';
    if (n === LAST) renderSummary();
    if (n !== 5) stopDevices();
  }

  function renderSummary() {
    const role = roleOther() ? document.getElementById('custom_role').value.trim() || 'Custom role' : val('role');
    document.getElementById('summary').innerHTML =
      `<div class="grid g2"><div><div class="muted small">Role</div><strong>${esc(role)}</strong></div>
       <div><div class="muted small">Difficulty</div><strong>${esc(val('difficulty'))}</strong></div>
       <div><div class="muted small">Questions</div><strong>${esc(val('num_questions'))}</strong></div>
       <div><div class="muted small">Resume</div><strong>${resumeFile ? esc(resumeFile.name) : 'None (general questions)'}</strong></div></div>`;
  }

  /* ---- resume ---- */
  const input = document.getElementById('resume'), drop = document.getElementById('drop');
  async function handleFile(file) {
    const out = document.getElementById('resumeOut');
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { out.innerHTML = '<div class="banner err">File is larger than 5 MB.</div>'; return; }
    if (!/\.pdf$/i.test(file.name)) { out.innerHTML = '<div class="banner err">Please choose a PDF file.</div>'; return; }
    out.innerHTML = '<div class="row"><div class="spinner"></div> Reading your resume...</div>';
    const fd = new FormData(); fd.append('resume', file);
    const r = await api('/api/resume/preview', { form: fd });
    if (!r.ok) { resumeFile = null; out.innerHTML = `<div class="banner err">${esc(r.data.error)}</div>`; return; }
    resumeFile = file;
    document.getElementById('dropText').textContent = file.name;
    const d = r.data;
    out.innerHTML = `<div class="card flat stack"><strong>What the interviewer found</strong>
      <div><div class="small muted">Skills</div><div class="tags">${d.skills.map(s => `<span class="chip">${esc(s)}</span>`).join('') || '<span class="muted small">none detected</span>'}</div></div>
      <div><div class="small muted">Projects</div>${d.projects.map(p => `<div>${esc(p.name)}</div>`).join('') || '<span class="muted small">none detected</span>'}</div>
      <div><div class="small muted">Education</div>${d.education.map(e => `<div>${esc(e)}</div>`).join('') || '<span class="muted small">none detected</span>'}</div>
      <p class="small muted" style="margin:0">Only this extracted text is used. Nothing is invented.</p></div>`;
  }
  input.addEventListener('change', () => handleFile(input.files[0]));
  ['dragover', 'dragenter'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove('drag'); }));
  drop.addEventListener('drop', ev => { const f = ev.dataTransfer.files[0]; if (f) { input.files = ev.dataTransfer.files; handleFile(f); } });

  /* ---- devices ---- */
  function setStatus(kind, ok, text) {
    document.getElementById(kind + 'Dot').className = 'dot ' + (ok ? 'ok' : 'bad');
    document.getElementById(kind + 'Txt').textContent = text;
  }
  function stopDevices() {
    cancelAnimationFrame(raf);
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
    const v = document.getElementById('prev'); v.srcObject = null;
    document.getElementById('prevMsg').hidden = false; document.getElementById('lvl').style.width = '0';
  }
  function explain(err) {
    const n = err && err.name;
    if (n === 'NotAllowedError' || n === 'SecurityError') return 'Permission was blocked. Click the camera icon in the address bar, allow access and test again.';
    if (n === 'NotFoundError' || n === 'OverconstrainedError') return 'No device was found.';
    if (n === 'NotReadableError') return 'The device is in use by another app. Close it and try again.';
    return 'Could not access the device.';
  }
  async function testDevices() {
    stopDevices();
    if (!navigator.mediaDevices?.getUserMedia) { setStatus('cam', false, 'Camera: not supported (use https or localhost in a modern browser)'); setStatus('mic', false, 'Microphone: not supported'); return; }
    let s = null;
    try { s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true }); }
    catch (e1) {
      setStatus('cam', false, 'Camera: ' + explain(e1));
      try { s = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch (e2) { setStatus('mic', false, 'Microphone: ' + explain(e2)); return; }
    }
    stream = s;
    const hasVideo = s.getVideoTracks().length > 0;
    if (hasVideo) { const v = document.getElementById('prev'); v.srcObject = s; document.getElementById('prevMsg').hidden = true; setStatus('cam', true, 'Camera: working'); }
    setStatus('mic', true, 'Microphone: working');
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const an = audioCtx.createAnalyser(); an.fftSize = 512;
      audioCtx.createMediaStreamSource(s).connect(an);
      const buf = new Uint8Array(an.fftSize);
      const tick = () => { an.getByteTimeDomainData(buf); let m = 0; for (const b of buf) m = Math.max(m, Math.abs(b - 128)); document.getElementById('lvl').style.width = Math.min(100, m * 2.2) + '%'; raf = requestAnimationFrame(tick); };
      tick();
    } catch (e) { /* level meter is optional */ }
  }
  document.getElementById('testBtn').addEventListener('click', testDevices);

  /* ---- navigation / submit ---- */
  function validate() {
    if (step === 1 && roleOther() && document.getElementById('custom_role').value.trim().length < 3) { toast('Enter a custom role name.', 'error'); return false; }
    return true;
  }
  async function start() {
    if (starting) return;
    starting = true; nextBtn.disabled = true; nextBtn.textContent = 'Preparing your interview...';
    const err = document.getElementById('startErr'); err.hidden = true;
    const fd = new FormData();
    fd.append('role', val('role')); fd.append('custom_role', document.getElementById('custom_role').value);
    fd.append('difficulty', val('difficulty')); fd.append('num_questions', val('num_questions'));
    if (resumeFile) fd.append('resume', resumeFile);
    const r = await api('/api/interviews', { form: fd });
    if (!r.ok) { err.textContent = r.data.error || 'Could not start the interview.'; err.hidden = false; starting = false; nextBtn.disabled = false; nextBtn.textContent = 'Start interview'; return; }
    stopDevices();
    location.href = r.data.redirect;
  }
  nextBtn.addEventListener('click', () => { if (!validate()) return; step === LAST ? start() : show(step + 1); });
  backBtn.addEventListener('click', () => step > 1 && show(step - 1));
  window.addEventListener('beforeunload', stopDevices);

  // pre-fill from query string (used by "Retake interview")
  const q = new URLSearchParams(location.search);
  for (const k of ['role', 'difficulty', 'num_questions']) {
    const v = q.get(k); const el = v && form.querySelector(`[name=${k}][value="${CSS.escape(v)}"]`);
    if (el) el.checked = true;
  }
  if (q.get('custom')) { const el = form.querySelector('[name=role][value=Other]'); if (el) { el.checked = true; document.getElementById('customWrap').hidden = false; document.getElementById('custom_role').value = q.get('custom'); } }
  show(1);
})();
