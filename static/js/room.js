/* Live interview room.
 * Reliability rules:
 *  - ONE camera/mic stream is opened once and kept for the whole interview (fixes "camera does not restart
 *    on the next question"). Only a new MediaRecorder is created per answer.
 *  - Each answer gets a submission id that is reused on retry; the server is idempotent, so retries and
 *    double clicks can never double-save or skip a question.
 *  - Progress is read from the server (/state), so a refresh or a dropped connection resumes correctly.
 */
(function () {
  const root = document.getElementById('room');
  const IID = root.dataset.iid, WHISPER = root.dataset.whisper === '1';
  const $ = id => document.getElementById(id);
  const el = { q: $('qText'), ans: $('answer'), start: $('startRec'), stop: $('stopRec'), submit: $('submit'), skip: $('skip'), next: $('nextQ'), fin: $('finish'), msg: $('msg') };
  let S = null;               // server state
  let stream = null, recorder = null, chunks = [], recStart = 0, recSeconds = 0, audioBlob = null;
  let audioCtx = null, raf = 0, timerBase = 0, timerStart = Date.now();
  let busy = false, audioDuration = null, answerSource = 'text';

  /* ---------- helpers ---------- */
  const fmt = s => String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(Math.floor(s % 60)).padStart(2, '0');
  setInterval(() => { $('timer').textContent = fmt(timerBase + (Date.now() - timerStart) / 1000); }, 1000);
  function note(text, kind) { el.msg.hidden = !text; el.msg.className = 'banner ' + (kind || ''); el.msg.innerHTML = text || ''; }
  function setStatus(kind, ok, text) { $(kind + 'Dot').className = 'dot ' + (ok ? 'ok' : 'bad'); $(kind + 'Txt').textContent = text; }
  function sid() {
    const key = `iiq-sid-${IID}-${S.current.idx}`;
    let v = sessionStorage.getItem(key);
    if (!v) { v = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()); sessionStorage.setItem(key, v); }
    return v;
  }
  function lock(on) { busy = on; [el.start, el.stop, el.submit, el.skip].forEach(b => b.disabled = on || b.dataset.off === '1'); el.ans.disabled = on; }

  /* ---------- devices ---------- */
  function explain(err) {
    const n = err && err.name;
    if (n === 'NotAllowedError' || n === 'SecurityError') return 'permission blocked. Allow access in the browser address bar, then reload.';
    if (n === 'NotFoundError') return 'no device found.';
    if (n === 'NotReadableError') return 'device is in use by another app.';
    return 'unavailable.';
  }
  async function initDevices() {
    if (!navigator.mediaDevices?.getUserMedia) { setStatus('cam', false, 'Camera: not supported in this browser/context'); setStatus('mic', false, 'Microphone: not supported'); $('camMsg').textContent = 'Camera unavailable. You can type your answers.'; return; }
    try { stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true }); }
    catch (e1) {
      setStatus('cam', false, 'Camera: ' + explain(e1)); $('camMsg').textContent = 'Camera unavailable. You can still answer by voice or text.';
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch (e2) { setStatus('mic', false, 'Microphone: ' + explain(e2)); note('Microphone ' + explain(e2) + ' You can type your answers instead.', 'err'); return; }
    }
    if (stream.getVideoTracks().length) { $('cam').srcObject = stream; $('camMsg').hidden = true; setStatus('cam', true, 'Camera: on'); }
    setStatus('mic', true, 'Microphone: ready');
    stream.getTracks().forEach(t => t.addEventListener('ended', () => { setStatus(t.kind === 'video' ? 'cam' : 'mic', false, (t.kind === 'video' ? 'Camera' : 'Microphone') + ': disconnected'); }));
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const an = audioCtx.createAnalyser(); an.fftSize = 512; audioCtx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.fftSize);
      (function tick() { an.getByteTimeDomainData(buf); let m = 0; for (const b of buf) m = Math.max(m, Math.abs(b - 128)); $('lvl').style.width = Math.min(100, m * 2.2) + '%'; raf = requestAnimationFrame(tick); })();
    } catch (e) { /* optional */ }
  }
  const canRecord = () => !!(stream && stream.getAudioTracks().some(t => t.readyState === 'live') && window.MediaRecorder);

  /* ---------- state ---------- */
  async function load() {
    const r = await api(`/api/interviews/${IID}/state`);
    if (!r.ok) { el.q.textContent = 'Could not load the interview.'; note(esc(r.data.error || 'Error') + ' <button class="btn btn-sm" id="retryLoad">Retry</button>', 'err'); $('retryLoad').onclick = load; return; }
    S = r.data;
    timerBase = S.elapsed_seconds; timerStart = Date.now();
    if (S.status === 'completed') { location.href = `/interview/${IID}/results`; return; }
    render();
  }
  function progress() {
    const answered = S.answered;
    $('progText').textContent = S.current ? `Question ${S.current.idx + 1} of ${S.total}` : `All ${S.total} questions answered`;
    $('progBar').style.width = Math.round(100 * answered / S.total) + '%';
  }
  function resetAnswerUI() {
    el.ans.value = ''; audioBlob = null; audioDuration = null; answerSource = 'text'; chunks = [];
    el.next.hidden = true; el.fin.hidden = true; note('');
    el.start.hidden = false; el.stop.hidden = true; el.submit.hidden = false; el.skip.hidden = false;
    el.start.dataset.off = canRecord() ? '0' : '1'; el.submit.dataset.off = '0'; el.skip.dataset.off = '0';
    lock(false);
    el.ans.focus();
  }
  function render() {
    progress();
    if (S.done || !S.current) { // all answered
      el.q.textContent = 'You have answered every question. Great work!';
      ['topicChip', 'diffChip'].forEach(i => $(i).hidden = true);
      el.ans.parentElement.hidden = true;
      [el.start, el.stop, el.submit, el.skip, el.next].forEach(b => b.hidden = true);
      el.fin.hidden = false; return;
    }
    const c = S.current;
    el.ans.parentElement.hidden = false;
    $('topicChip').hidden = false; $('diffChip').hidden = false;
    $('topicChip').textContent = c.topic_label;
    $('diffChip').textContent = ['', 'Easy', 'Medium', 'Hard'][c.difficulty] || 'Medium';
    const kc = $('kindChip');
    const kinds = { probe: 'Foundation check', followup: 'Follow-up', resume: 'From your resume' };
    kc.hidden = !kinds[c.kind]; kc.textContent = kinds[c.kind] || '';
    el.q.textContent = c.question;
    resetAnswerUI();
    if (!canRecord()) note(WHISPER ? 'Voice recording is unavailable (check microphone permission). You can type your answer.' : 'Voice transcription is not installed on this server. Type your answer below.', 'info');
  }

  /* ---------- recording ---------- */
  function pickMime() {
    for (const m of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']) if (MediaRecorder.isTypeSupported?.(m)) return m;
    return '';
  }
  el.start.onclick = () => {
    if (busy || !canRecord()) return;
    try {
      const audioOnly = new MediaStream(stream.getAudioTracks());
      const mime = pickMime();
      recorder = new MediaRecorder(audioOnly, mime ? { mimeType: mime } : undefined);
    } catch (e) { note('Could not start recording: ' + esc(e.message) + '. Type your answer instead.', 'err'); return; }
    chunks = []; audioBlob = null;
    recorder.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
    recorder.onerror = () => { note('Recording error. Try again or type your answer.', 'err'); stopUI(); };
    recorder.onstop = onRecorded;
    recorder.start(1000);
    recStart = Date.now();
    el.start.hidden = true; el.stop.hidden = false; el.submit.disabled = true; el.skip.disabled = true; el.ans.disabled = true;
    $('recDot').className = 'dot rec'; $('recTxt').textContent = 'Recording'; $('recInd').classList.add('on');
    note('Recording... speak clearly, then press Stop.', 'info');
  };
  function stopUI() { el.start.hidden = false; el.stop.hidden = true; $('recDot').className = 'dot'; $('recTxt').textContent = 'Not recording'; $('recInd').classList.remove('on'); }
  el.stop.onclick = () => { if (recorder && recorder.state !== 'inactive') { recSeconds = (Date.now() - recStart) / 1000; recorder.stop(); } };

  async function onRecorded() {
    stopUI();
    audioBlob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
    if (audioBlob.size < 1500 || recSeconds < 1) { note('That recording was too short. Try again.', 'err'); audioBlob = null; lock(false); return; }
    await transcribe();
  }
  async function transcribe() {
    lock(true);
    note('<span class="row"><span class="spinner"></span> Transcribing your answer with Whisper...</span>', 'info');
    const fd = new FormData(); fd.append('audio', audioBlob, 'answer.webm'); fd.append('idx', S.current.idx);
    const r = await api(`/api/interviews/${IID}/transcribe`, { form: fd, timeout: 240000 });
    lock(false);
    if (!r.ok) {
      note(esc(r.data.error || 'Transcription failed.') + ' <button class="btn btn-sm" id="retryTx">Retry transcription</button> You can also type your answer.', 'err');
      const b = $('retryTx'); if (b) b.onclick = transcribe; return;
    }
    el.ans.value = r.data.text; answerSource = 'audio'; audioDuration = r.data.duration || recSeconds;
    note('Transcript ready. Fix any mistakes, then press Submit answer.', 'info');
  }

  /* ---------- submit ---------- */
  el.ans.addEventListener('input', () => { if (answerSource === 'audio' && !el.ans.value.trim()) answerSource = 'text'; });

  async function submit(skipped) {
    if (busy) return;                       // prevents double submit
    const text = el.ans.value.trim();
    if (!skipped && text.length < 1) { note('Record or type an answer first, or choose Skip.', 'err'); return; }
    if (skipped && !confirm('Skip this question? It will score 0.')) return;
    lock(true);
    showProcessing('Processing your answer', 'Transcribing, evaluating and preparing feedback.', [
      { name: 'Audio transcription' }, { name: 'Speech analysis' }, { name: 'Answer evaluation' }, { name: 'Next question selection' }]);
    const body = { idx: S.current.idx, text, source: skipped ? 'skipped' : answerSource, duration: audioDuration, submission_id: sid() };
    const r = await api(`/api/interviews/${IID}/answer`, { json: body, timeout: 180000 });
    if (!r.ok) {
      hideProcessing();
      lock(false);
      note(esc(r.data.error || 'Something went wrong.') + (r.network || r.status >= 500 ? ' Your answer is not lost: press Submit again to retry safely.' : ''), 'err');
      if (r.status === 409) setTimeout(load, 800);
      return;
    }
    showStages(r.data.stages || [], r.data.duplicate);
    await new Promise(res => setTimeout(res, r.data.stages && r.data.stages.length ? 1100 : 300));
    hideProcessing();
    busy = false;  // answer saved; controls stay hidden until the next question renders
    S.answered = r.data.answered; S.done = r.data.done; S.current = r.data.next;
    progress();
    el.start.hidden = true; el.stop.hidden = true; el.submit.hidden = true; el.skip.hidden = true; el.ans.disabled = true;
    note(r.data.duplicate ? 'This answer was already saved. Moving on.' : 'Answer saved.', 'info');
    if (r.data.done) { el.fin.hidden = false; el.q.textContent = 'That was the last question.'; } else { el.next.hidden = false; el.next.focus(); }
  }
  el.submit.onclick = () => submit(false);
  el.skip.onclick = () => submit(true);
  el.next.onclick = () => { render(); };
  el.fin.onclick = async () => {
    if (busy) return; lock(true); el.fin.disabled = true;
    showProcessing('Preparing your report', 'Aggregating scores, building strengths, weaknesses and your learning roadmap.', [{ name: 'Report preparation' }]);
    const r = await api(`/api/interviews/${IID}/finish`, { method: 'POST', timeout: 180000 });
    if (!r.ok) { hideProcessing(); el.fin.disabled = false; lock(false); note(esc(r.data.error || 'Could not prepare the report.') + ' Press Finish again to retry.', 'err'); return; }
    showStages(r.data.stages || []);
    setTimeout(() => { location.href = r.data.redirect; }, 700);
  };

  /* ---------- processing overlay: real stages only, no fake percentages ---------- */
  function showProcessing(title, sub, pending) {
    $('procTitle').textContent = title; $('procSub').textContent = sub; $('procSpin').hidden = false;
    $('stages').innerHTML = pending.map(s => `<div class="stage"><span class="spinner" style="width:16px;height:16px;border-width:2px;opacity:.5"></span><span>${esc(s.name)}</span><span class="ms">waiting</span></div>`).join('');
    $('processing').hidden = false;
  }
  function showStages(stages, dup) {
    if (!stages.length) return;
    $('procSpin').hidden = true; $('procTitle').textContent = dup ? 'Already saved' : 'Done';
    $('stages').innerHTML = stages.map(s => `<div class="stage"><span class="tick ${s.status === 'skipped' ? 'skip' : ''}">${s.status === 'skipped' ? '-' : '&#10003;'}</span>
      <span>${esc(s.name)}${s.detail ? `<div class="small muted">${esc(s.detail)}</div>` : ''}</span><span class="ms">${s.status === 'skipped' ? 'not needed' : (s.ms != null ? s.ms + ' ms' : 'done')}</span></div>`).join('');
  }
  function hideProcessing() { $('processing').hidden = true; }

  window.addEventListener('beforeunload', e => { if (recorder && recorder.state === 'recording') { e.preventDefault(); e.returnValue = ''; } });
  window.addEventListener('pagehide', () => { cancelAnimationFrame(raf); if (stream) stream.getTracks().forEach(t => t.stop()); });

  (async function boot() { await Promise.all([initDevices(), load()]); if (S && (S.current || S.done)) render(); })();
})();
