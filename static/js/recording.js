/**
 * recording.js — MediaRecorder + upload + cancel polling
 * Audio is handled by Jitsi Meet iframe (no JS integration needed).
 */

// ─── State ───────────────────────────────────────────────────────
let mediaRecorder  = null;
let recordedChunks = [];
let capturedBlob   = null;
let timerInterval  = null;
let timerSeconds   = 0;
let isRecording    = false;
let pollInterval   = null;
let currentRating  = 0;

// ─── Recording ───────────────────────────────────────────────────
async function startRecording() {
  if (isRecording) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl:  true,
        sampleRate:       48000,
        channelCount:     1,
      },
      video: false,
    });

    recordedChunks = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg');

    mediaRecorder = new MediaRecorder(stream, { mimeType });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      capturedBlob = new Blob(recordedChunks, { type: mimeType });
      stream.getTracks().forEach(t => t.stop());
      onRecordingStopped();
    };

    mediaRecorder.start(1000);
    isRecording = true;
    startTimer();
    setRecordingUI(true);

    apiFetch(`/api/recordings/${SESSION_ID}/start/`, { method: 'POST' }).catch(() => {});

  } catch (err) {
    console.error('[Mic]', err);
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      showError('Microphone access denied. Click the 🎤 icon in the browser address bar and allow microphone, then try again.');
    } else if (err.name === 'NotFoundError') {
      showError('No microphone found. Please connect a microphone and try again.');
    } else {
      showError(`Microphone error: ${err.message}`);
    }
  }
}

function stopRecording() {
  if (!isRecording || !mediaRecorder) return;
  if (mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  isRecording = false;
  stopTimer();
  setRecordingUI(false);
}

function onRecordingStopped() {
  const sizeEl = document.getElementById('rec-size');
  if (sizeEl && capturedBlob) {
    sizeEl.textContent = `${(capturedBlob.size / (1024 * 1024)).toFixed(2)} MB recorded`;
    sizeEl.classList.remove('hidden');
  }
  const btnUpload = document.getElementById('btn-upload');
  if (btnUpload) btnUpload.classList.remove('hidden');
}

// ─── Upload ──────────────────────────────────────────────────────
async function uploadRecording() {
  if (!capturedBlob) { showError('No recording to upload.'); return; }

  const lbl = document.getElementById('upload-btn-label');
  const btn = document.getElementById('btn-upload');
  if (lbl) lbl.textContent = 'Uploading...';
  if (btn) btn.disabled = true;

  try {
    const channel = IS_INITIATOR ? 'a' : 'b';
    const ext = capturedBlob.type.includes('webm') ? 'webm' : 'ogg';
    const formData = new FormData();
    formData.append('file', capturedBlob, `recording_${channel}.${ext}`);
    formData.append('channel', channel);

    const res = await fetch(`/api/recordings/${SESSION_ID}/upload-chunk/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: formData,
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `HTTP ${res.status}`);
    }

    // Success
    if (btn) btn.classList.add('hidden');
    document.getElementById('upload-success').classList.remove('hidden');

    // Tell server the session ended
    apiFetch(`/api/recordings/${SESSION_ID}/end/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration: timerSeconds }),
    }).catch(() => {});

    // Show rating modal after a moment
    setTimeout(() => {
      const modal = document.getElementById('rating-modal');
      if (modal) modal.classList.remove('hidden');
    }, 2000);

  } catch (err) {
    console.error('[Upload]', err);
    showError(`Upload failed: ${err.message}. Please try again.`);
    if (lbl) lbl.textContent = 'Upload Recording';
    if (btn) btn.disabled = false;
  }
}

// ─── Cancel / Leave ──────────────────────────────────────────────
async function doLeave() {
  stopRecording();
  clearInterval(pollInterval);
  try {
    await fetch(`/api/recordings/${SESSION_ID}/cancel/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json' },
    });
  } catch (e) { /* best effort */ }
  window.location.href = '/';
}

function leaveSession() { doLeave(); }

// ─── Polling — detect if partner cancels ─────────────────────────
function startPolling() {
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/recordings/${SESSION_ID}/status/`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === 'rejected') {
        clearInterval(pollInterval);
        showError('Session was cancelled by your partner.');
        setTimeout(() => { window.location.href = '/'; }, 3000);
      }
    } catch (e) { /* ignore */ }
  }, 5000);
}

// ─── Timer ───────────────────────────────────────────────────────
function startTimer() {
  timerSeconds = 0;
  timerInterval = setInterval(() => {
    timerSeconds++;
    const el = document.getElementById('timer-display');
    if (el) el.textContent = fmtTime(timerSeconds);
  }, 1000);
}

function stopTimer() { clearInterval(timerInterval); }

// ─── UI Helpers ──────────────────────────────────────────────────
function setRecordingUI(recording) {
  const btnStart  = document.getElementById('btn-start');
  const btnStop   = document.getElementById('btn-stop');
  const btnCancel = document.getElementById('cancel-btn');
  const recDot    = document.getElementById('rec-dot');
  const statusTxt = document.getElementById('rec-status-text');

  if (recording) {
    if (btnStart)  btnStart.classList.add('hidden');
    if (btnStop)   btnStop.classList.remove('hidden');
    if (btnCancel) document.getElementById('cancel-btn-text').textContent = 'Stop & Leave';
    if (recDot)    { recDot.classList.remove('bg-gray-600'); recDot.classList.add('bg-red-500', 'animate-pulse'); }
    if (statusTxt) statusTxt.textContent = '🔴 Recording...';
  } else {
    if (btnStart)  btnStart.classList.remove('hidden');
    if (btnStop)   btnStop.classList.add('hidden');
    if (btnCancel) document.getElementById('cancel-btn-text').textContent = 'Leave';
    if (recDot)    { recDot.classList.add('bg-gray-600'); recDot.classList.remove('bg-red-500', 'animate-pulse'); }
    if (statusTxt) statusTxt.textContent = 'Live Room';
  }
}

function showError(msg) {
  const el = document.getElementById('error-banner');
  if (el) { el.textContent = '⚠️ ' + msg; el.classList.remove('hidden'); }
  console.error('[Room]', msg);
}

// ─── Rating ──────────────────────────────────────────────────────
function setRating(n) {
  currentRating = n;
  document.querySelectorAll('.star-btn').forEach((btn, i) => {
    btn.classList.toggle('text-yellow-400', i < n);
    btn.classList.toggle('text-gray-600', i >= n);
  });
}

async function submitRating() {
  try {
    await apiFetch(`/api/recordings/${SESSION_ID}/rate/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rating: currentRating,
        feedback: document.getElementById('rating-feedback')?.value || '',
        partner_id: PARTNER_ID,
      }),
    });
  } catch (e) { /* ignore rating errors */ }
  skipRating();
}

function skipRating() {
  const modal = document.getElementById('rating-modal');
  if (modal) modal.classList.add('hidden');
  window.location.href = '/';
}

// ─── Utilities ───────────────────────────────────────────────────
function fmtTime(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function getCookie(n) {
  const v = `; ${document.cookie}`;
  const p = v.split(`; ${n}=`);
  return p.length === 2 ? p.pop().split(';').shift() : '';
}

async function apiFetch(url, opts = {}) {
  opts.headers = { ...opts.headers, 'X-CSRFToken': getCookie('csrftoken') };
  return fetch(url, opts);
}

// ─── Init ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  startPolling();

  // Show the status badge
  const badge = document.getElementById('rec-status-badge');
  if (badge) badge.classList.remove('hidden');
});
