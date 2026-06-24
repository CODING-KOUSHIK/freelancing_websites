/**
 * recording.js — Single-WebSocket recording room controller
 *
 * Features:
 *  - Single WS for signaling + room control
 *  - Network quality monitor (RTT, packet loss, jitter) via WebRTC stats API
 *  - Auto-captures browser recording → uploads on button click (no file picker needed)
 *  - Session report card after recording ends
 *  - Cancel/leave at any time
 */

// ─── State ──────────────────────────────────────────────────────
let ws = null, wsRetries = 0;
const MAX_WS_RETRIES = 10;

let mediaRecorder = null;
let recordedChunks = [];
let capturedBlob = null;
let timerInterval = null, timerSeconds = 0;
let isMuted = false, isSpeakerOff = false;
let currentRating = 0;
let currentState = 'connecting';
let levelsInterval = null;
let netStatsInterval = null;

// Network stats accumulator
let netSamples = [];
let latestRtt = null, latestLoss = null, latestJitter = null;

// ─── Utility ────────────────────────────────────────────────────
function getCookie(n) {
  const v = `; ${document.cookie}`;
  const p = v.split(`; ${n}=`);
  return p.length === 2 ? p.pop().split(';').shift() : '';
}

function fmtTime(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

// ─── WebSocket ───────────────────────────────────────────────────
function connectWS() {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${scheme}://${location.host}/ws/recordings/${SESSION_ID}/`);

  ws.onopen = () => {
    console.log('[WS] Connected');
    wsRetries = 0;
    window.webRTC.setSendFn(data => sendWS(data));
    requestMic();
  };

  ws.onmessage = e => {
    try { onMsg(JSON.parse(e.data)); }
    catch (err) { console.error('[WS] Parse error:', err); }
  };

  ws.onclose = e => {
    console.warn('[WS] Closed:', e.code);
    if (e.code !== 1000 && wsRetries < MAX_WS_RETRIES) {
      const d = Math.min(1000 * Math.pow(1.5, wsRetries), 10000);
      wsRetries++;
      setTimeout(connectWS, d);
    }
  };

  ws.onerror = e => console.error('[WS] Error', e);
}

function sendWS(data) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
}

// ─── Microphone ─────────────────────────────────────────────────
async function requestMic() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, sampleRate: 48000, channelCount: 1 },
      video: false,
    });
    const la = document.getElementById('local-audio');
    if (la) la.srcObject = stream;

    window.webRTC.init(stream, IS_INITIATOR);

    levelsInterval = setInterval(() => {
      const a = document.getElementById('level-a');
      const b = document.getElementById('level-b');
      if (a) a.style.width = window.webRTC.getLocalLevel() + '%';
      if (b) b.style.width = window.webRTC.getRemoteLevel() + '%';
    }, 100);

    showState('waiting');
  } catch (err) {
    console.error('[Mic] Error:', err);
    const msg = err.name === 'NotAllowedError'
      ? 'Microphone access was denied. Please allow it and refresh the page.'
      : `Microphone error: ${err.message}`;
    showBanner(msg, 'error');
  }
}

// ─── Message Handler ────────────────────────────────────────────
function onMsg(msg) {
  console.log('[WS] →', msg.type, msg);
  switch (msg.type) {

    case 'peer.joined':
      if (msg.user_id !== String(CURRENT_USER_ID)) {
        window.webRTC.onPeerJoined();
      }
      if (msg.both_connected) showState('ready');
      break;

    case 'peer.left':
      if (msg.user_id !== String(CURRENT_USER_ID)) {
        if (currentState === 'recording') {
          showBanner(`${msg.user_name || 'Partner'} disconnected. Recording continues.`, 'warning');
        } else if (currentState === 'waiting' || currentState === 'ready') {
          showState('waiting');
        }
      }
      break;

    case 'recording.ready':
      showState('ready');
      break;

    case 'recording.started':
      showState('recording');
      startTimer();
      startLocalRecording();
      startNetworkMonitor();
      startWaveform();
      break;

    case 'recording.ended':
      stopTimer();
      stopLocalRecording();
      stopNetworkMonitor();
      buildSessionReport(msg);
      showState('ended');
      setTimeout(() => showRatingModal(), 3000);
      break;

    case 'webrtc.signal':
      if (msg.from_user !== String(CURRENT_USER_ID)) window.webRTC.handleSignal(msg);
      break;

    case 'error':
      showBanner(msg.message || 'An error occurred', 'error');
      break;
  }
}

// ─── State Machine ───────────────────────────────────────────────
function showState(state) {
  currentState = state;
  ['connecting','waiting','ready','recording','ended'].forEach(s => {
    const el = document.getElementById(`state-${s}`);
    if (el) el.classList.toggle('hidden', s !== state);
  });

  const cfg = {
    connecting: { text:'Connecting...', cls:'bg-gray-700/40 text-gray-300 border-gray-600' },
    waiting:    { text:'Waiting for partner...', cls:'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
    ready:      { text:'✅ Both Connected!', cls:'bg-green-500/10 text-green-400 border-green-500/20' },
    recording:  { text:'🔴 Recording...', cls:'bg-red-500/10 text-red-400 border-red-500/20' },
    ended:      { text:'Session Complete', cls:'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  };
  const badge = document.getElementById('session-status-badge');
  const txt = document.getElementById('status-text');
  if (badge && txt && cfg[state]) {
    txt.textContent = cfg[state].text;
    badge.className = `hidden sm:inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-semibold border ${cfg[state].cls}`;
  }
}

// ─── Recording ──────────────────────────────────────────────────
function startRecording() { sendWS({ type: 'recording.start' }); }
function stopRecording()  { sendWS({ type: 'recording.end', duration: timerSeconds }); }

function startLocalRecording() {
  const stream = window.webRTC.localStream;
  if (!stream) { console.warn('[Recorder] No stream'); return; }
  try {
    recordedChunks = [];
    capturedBlob = null;
    const opts = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? { mimeType: 'audio/webm;codecs=opus' }
      : {};
    mediaRecorder = new MediaRecorder(stream, opts);
    mediaRecorder.ondataavailable = e => { if (e.data?.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      if (recordedChunks.length > 0) {
        capturedBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        console.log('[Recorder] Captured', (capturedBlob.size / 1024 / 1024).toFixed(2), 'MB');
      }
    };
    mediaRecorder.start(10000);
    console.log('[Recorder] Started');
  } catch (e) { console.error('[Recorder] Error:', e); }
}

function stopLocalRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
}

// ─── Timer ──────────────────────────────────────────────────────
function startTimer() {
  timerSeconds = 0;
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    timerSeconds++;
    const t = document.getElementById('timer');
    const e = document.getElementById('est-earnings');
    if (t) t.textContent = fmtTime(timerSeconds);
    if (e) e.textContent = `₹${((timerSeconds / 60) * PER_MINUTE_RATE).toFixed(2)}`;
  }, 1000);
}
function stopTimer() { clearInterval(timerInterval); }

// ─── Waveform ────────────────────────────────────────────────────
let waveAnimId = null;
function startWaveform() {
  const canvas = document.getElementById('waveform-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let phase = 0;

  function draw() {
    if (currentState !== 'recording') { waveAnimId = null; return; }
    waveAnimId = requestAnimationFrame(draw);
    const w = canvas.width = canvas.offsetWidth;
    const h = canvas.height;
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, w, h);

    const lvl = window.webRTC.getLocalLevel() / 100;
    const bars = 52;
    const bw = w / bars;
    phase += 0.04;

    for (let i = 0; i < bars; i++) {
      const amp = lvl > 0.02
        ? (Math.sin((i / bars) * Math.PI * 3 + phase) * 0.5 + 0.5) * lvl * h * 0.75
        : 4;
      const x = i * bw;
      const y = (h - amp) / 2;
      ctx.fillStyle = i % 3 === 0 ? '#4ade80' : i % 3 === 1 ? '#34d399' : '#6ee7b7';
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x + 2, y, bw - 4, Math.max(amp, 4), 3);
      else ctx.rect(x + 2, y, bw - 4, Math.max(amp, 4));
      ctx.fill();
    }
  }
  draw();
}

// ─── Network Quality Monitor ────────────────────────────────────
function startNetworkMonitor() {
  netSamples = [];
  netStatsInterval = setInterval(async () => {
    const stats = await getWebRTCStats();
    if (!stats) return;
    latestRtt = stats.rtt;
    latestLoss = stats.lossPercent;
    latestJitter = stats.jitter;
    netSamples.push(stats);
    updateNetworkUI(stats);
  }, 2000);
}

function stopNetworkMonitor() {
  clearInterval(netStatsInterval);
}

async function getWebRTCStats() {
  try {
    const pc = window.webRTC._pc;
    if (!pc) return null;
    const reports = await pc.getStats();
    let rtt = null, loss = null, jitter = null;

    reports.forEach(r => {
      if (r.type === 'remote-inbound-rtp' && r.kind === 'audio') {
        if (r.roundTripTime != null) rtt = Math.round(r.roundTripTime * 1000); // ms
        if (r.fractionLost != null) loss = (r.fractionLost * 100).toFixed(1);
        if (r.jitter != null) jitter = Math.round(r.jitter * 1000); // ms
      }
    });
    return { rtt, lossPercent: loss, jitter };
  } catch (e) {
    return null;
  }
}

function updateNetworkUI(stats) {
  const rttEl = document.getElementById('stat-rtt');
  const lossEl = document.getElementById('stat-loss');
  const jitterEl = document.getElementById('stat-jitter');
  const qualLabel = document.getElementById('net-quality-label');
  const qualSub = document.getElementById('net-quality-sub');
  const bars = document.getElementById('signal-bars');

  if (rttEl) rttEl.textContent = stats.rtt != null ? `${stats.rtt} ms` : '—';
  if (lossEl) lossEl.textContent = stats.lossPercent != null ? `${stats.lossPercent}%` : '—';
  if (jitterEl) jitterEl.textContent = stats.jitter != null ? `${stats.jitter} ms` : '—';

  const rtt = stats.rtt || 0;
  let quality, color, subText, barFill;

  if (rtt < 50 && (!stats.lossPercent || parseFloat(stats.lossPercent) < 1)) {
    quality = 'Excellent'; color = '#4ade80'; subText = 'Low latency'; barFill = 4;
  } else if (rtt < 150 && (!stats.lossPercent || parseFloat(stats.lossPercent) < 3)) {
    quality = 'Good'; color = '#a3e635'; subText = 'Stable connection'; barFill = 3;
  } else if (rtt < 300) {
    quality = 'Fair'; color = '#fb923c'; subText = 'Some latency'; barFill = 2;
  } else {
    quality = 'Poor'; color = '#f87171'; subText = 'High latency'; barFill = 1;
  }

  if (qualLabel) { qualLabel.textContent = quality; qualLabel.style.color = color; }
  if (qualSub)   qualSub.textContent = subText;

  if (bars) {
    const divs = bars.querySelectorAll('div');
    divs.forEach((d, i) => {
      d.style.backgroundColor = i < barFill ? color : '#374151';
    });
  }
}

function calcQualityScore() {
  if (!netSamples.length) return 85; // default if no stats
  const avgRtt = netSamples.reduce((s, n) => s + (n.rtt || 0), 0) / netSamples.length;
  const avgLoss = netSamples.reduce((s, n) => s + parseFloat(n.lossPercent || 0), 0) / netSamples.length;
  let score = 100;
  if (avgRtt > 50)  score -= Math.min(30, (avgRtt - 50) / 10);
  if (avgLoss > 1)  score -= Math.min(40, avgLoss * 8);
  return Math.max(0, Math.min(100, Math.round(score)));
}

// ─── Session Report ─────────────────────────────────────────────
function buildSessionReport(msg) {
  const dur = msg.duration || timerSeconds;

  // Duration
  const durEl = document.getElementById('final-duration');
  if (durEl) durEl.textContent = fmtTime(dur);

  // Earnings
  const earnEl = document.getElementById('final-earnings');
  if (earnEl) earnEl.textContent = `₹${((dur / 60) * PER_MINUTE_RATE).toFixed(2)}`;

  // Network stats
  const avgRtt = netSamples.length
    ? Math.round(netSamples.reduce((s, n) => s + (n.rtt || 0), 0) / netSamples.length)
    : null;
  const avgLoss = netSamples.length
    ? (netSamples.reduce((s, n) => s + parseFloat(n.lossPercent || 0), 0) / netSamples.length).toFixed(1)
    : null;

  const rttEl = document.getElementById('final-rtt');
  if (rttEl) rttEl.textContent = avgRtt != null ? `${avgRtt} ms` : '—';

  const lossEl = document.getElementById('final-loss');
  if (lossEl) lossEl.textContent = avgLoss != null ? `${avgLoss}%` : '—';

  // Quality score bar
  const score = calcQualityScore();
  const bar = document.getElementById('quality-bar');
  const lbl = document.getElementById('quality-score-label');
  setTimeout(() => {
    if (bar) {
      const clr = score >= 80 ? 'from-green-400 to-emerald-500'
                : score >= 60 ? 'from-yellow-400 to-orange-400'
                : 'from-red-400 to-rose-500';
      bar.className = `h-full bg-gradient-to-r ${clr} rounded-full transition-all duration-1000`;
      bar.style.width = `${score}%`;
    }
    if (lbl) {
      const grade = score >= 80 ? 'Excellent' : score >= 60 ? 'Good' : score >= 40 ? 'Fair' : 'Poor';
      lbl.textContent = `${grade} (${score}/100)`;
      lbl.style.color = score >= 80 ? '#4ade80' : score >= 60 ? '#fb923c' : '#f87171';
    }
  }, 300);

  // Ended by
  const byEl = document.getElementById('ended-by-text');
  if (byEl) {
    const who = msg.ended_by === String(CURRENT_USER_ID) ? 'you' : (msg.ended_by_name || 'your partner');
    byEl.textContent = `Session ended by ${who}`;
  }
}

// ─── Upload ─────────────────────────────────────────────────────
async function uploadRecording() {
  const btn = document.getElementById('btn-upload');
  const btnText = document.getElementById('upload-btn-text');
  const btnIcon = document.getElementById('upload-btn-icon');
  const progressArea = document.getElementById('upload-progress-area');
  const progressBar = document.getElementById('upload-progress-bar');
  const pctEl = document.getElementById('upload-pct');
  const statusText = document.getElementById('upload-status-text');
  const successArea = document.getElementById('upload-success-area');

  // Get the recorded audio blob (auto-captured)
  if (!capturedBlob && recordedChunks.length > 0) {
    capturedBlob = new Blob(recordedChunks, { type: 'audio/webm' });
  }

  if (!capturedBlob || capturedBlob.size === 0) {
    showBanner('No recording found. The session may not have captured audio properly.', 'error');
    return;
  }

  btn.disabled = true;
  if (btnText) btnText.textContent = 'Uploading...';
  if (btnIcon) btnIcon.className = 'fas fa-spinner fa-spin';
  if (progressArea) progressArea.classList.remove('hidden');
  if (statusText) statusText.textContent = 'Preparing upload...';

  const ext = capturedBlob.type.includes('webm') ? 'webm' : 'wav';
  const file = new File([capturedBlob], `recording_${SESSION_ID.slice(0, 8)}.${ext}`, { type: capturedBlob.type });

  try {
    const formData = new FormData();
    formData.append('audio_file', file);
    formData.append('session_id', SESSION_ID);

    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `/api/recordings/${SESSION_ID}/chunk/`);
      xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));

      xhr.upload.onprogress = e => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          if (progressBar) progressBar.style.width = `${pct}%`;
          if (pctEl) pctEl.textContent = `${pct}%`;
          if (statusText) statusText.textContent = pct < 30 ? 'Uploading...' : pct < 70 ? 'Sending to Drive...' : 'Almost done...';
        }
      };

      xhr.onload = () => xhr.status < 300 ? resolve() : reject(new Error(`Server: ${xhr.status}`));
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });

    // Success!
    if (progressArea) progressArea.classList.add('hidden');
    if (successArea) successArea.classList.remove('hidden');
    if (btnText) btnText.textContent = 'Uploaded ✓';
    if (btnIcon) btnIcon.className = 'fas fa-check';
    btn.className = btn.className.replace('from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500', 'from-green-600 to-emerald-600');

  } catch (err) {
    console.error('[Upload] Error:', err);
    if (progressArea) progressArea.classList.add('hidden');
    if (statusText) { statusText.textContent = `Upload failed: ${err.message}`; progressArea.classList.remove('hidden'); }
    if (pctEl) pctEl.textContent = '';
    if (btnText) btnText.textContent = 'Try Again';
    if (btnIcon) btnIcon.className = 'fas fa-redo';
    btn.disabled = false;
  }
}

// ─── Audio Controls ──────────────────────────────────────────────
function toggleMute() {
  isMuted = !isMuted;
  window.webRTC.setMute(isMuted);
  const icon = document.getElementById('mute-icon');
  const lbl = document.getElementById('mute-label');
  if (icon) icon.className = `fas ${isMuted ? 'fa-microphone-slash text-red-400' : 'fa-microphone text-green-400'} text-xl`;
  if (lbl) lbl.textContent = isMuted ? 'Unmute' : 'Mute';
}

function toggleSpeaker() {
  isSpeakerOff = !isSpeakerOff;
  const audio = document.getElementById('remote-audio');
  if (audio) audio.muted = isSpeakerOff;
  const icon = document.getElementById('speaker-icon');
  if (icon) icon.className = `fas ${isSpeakerOff ? 'fa-volume-mute text-red-400' : 'fa-volume-up text-blue-400'} text-xl`;
}

// ─── Cancel / Leave ──────────────────────────────────────────────
function leaveSession() {
  if (currentState === 'recording') {
    if (!confirm('Recording is in progress. Stop recording and leave?')) return;
    stopRecording();
    setTimeout(doLeave, 1200);
  } else {
    doLeave();
  }
}

function doLeave() {
  clearInterval(levelsInterval);
  clearInterval(netStatsInterval);
  clearInterval(timerInterval);
  if (waveAnimId) cancelAnimationFrame(waveAnimId);
  window.webRTC.cleanup();
  if (ws?.readyState === WebSocket.OPEN) ws.close(1000, 'User left');
  window.location.href = '/my-jobs/';
}

// ─── Banners ────────────────────────────────────────────────────
function showBanner(msg, type = 'info') {
  const cls = {
    error: 'bg-red-900/80 border-red-500/50 text-red-200',
    warning: 'bg-yellow-900/80 border-yellow-500/50 text-yellow-200',
    info: 'bg-blue-900/80 border-blue-500/50 text-blue-200',
  }[type] || 'bg-gray-800 border-gray-600 text-gray-200';
  const el = document.createElement('div');
  el.className = `fixed top-4 left-1/2 -translate-x-1/2 z-[9999] max-w-sm w-full px-5 py-3 rounded-2xl border text-sm font-medium shadow-2xl ${cls}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

// ─── Rating ─────────────────────────────────────────────────────
function showRatingModal() {
  const m = document.getElementById('rating-modal');
  if (m) m.classList.remove('hidden');
}

function setRating(val) {
  currentRating = val;
  document.querySelectorAll('.star-btn').forEach((b, i) => {
    b.style.color = i < val ? '#facc15' : '#374151';
  });
}

async function submitRating() {
  const feedback = document.getElementById('rating-feedback')?.value || '';
  if (currentRating > 0) {
    try {
      await fetch('/api/ratings/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ ratee: PARTNER_ID, session: SESSION_ID, score: currentRating, comment: feedback }),
      });
    } catch (e) {}
  }
  skipRating();
}

function skipRating() {
  const m = document.getElementById('rating-modal');
  if (m) m.classList.add('hidden');
}

// ─── Init ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  connectWS();
});
