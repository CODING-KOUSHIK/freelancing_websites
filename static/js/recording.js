/**
 * recording.js — Jitsi Meet + MediaRecorder
 *
 * Audio room powered by Jitsi Meet (free, no account, no config).
 * Local recording via MediaRecorder API.
 * No WebSocket / WebRTC complexity.
 */

// ─── State ───────────────────────────────────────────────────────
let jitsiApi     = null;
let mediaRecorder = null;
let recordedChunks = [];
let capturedBlob  = null;
let timerInterval = null;
let timerSeconds  = 0;
let isRecording   = false;
let pollInterval  = null;
let currentState  = 'connecting';

// ─── Init ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (typeof JitsiMeetExternalAPI !== 'undefined') {
    initJitsi();
  } else {
    showBanner('⚠️ Audio room failed to load. Please refresh the page.', 'error');
    showConnectError();
  }
  startPolling();
});

// ─── Jitsi ───────────────────────────────────────────────────────
function initJitsi() {
  // Use first 16 chars of session_id as room name (unique enough)
  const roomName = 'vm' + SESSION_ID.replace(/-/g, '').substring(0, 14);

  const options = {
    roomName,
    width: '100%',
    height: 300,
    parentNode: document.getElementById('jitsi-container'),
    configOverwrite: {
      startWithVideoMuted:   true,
      startWithAudioMuted:   false,
      disableDeepLinking:    true,
      prejoinPageEnabled:    false,
      enableClosePage:       false,
      disableInviteFunctions: true,
      enableWelcomePage:     false,
      requireDisplayName:    false,
      startAudioOnly:        true,
      disableSimulcast:      true,
      enableP2P:             true,
      p2p: { enabled: true, stunServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
      ]},
    },
    interfaceConfigOverwrite: {
      TOOLBAR_BUTTONS: ['microphone', 'hangup', 'raisehand'],
      SHOW_CHROME_EXTENSION_BANNER:     false,
      DEFAULT_REMOTE_DISPLAY_NAME:      'Partner',
      HIDE_INVITE_MORE_HEADER:          true,
      DISABLE_JOIN_LEAVE_NOTIFICATIONS: false,
    },
    userInfo: { displayName: CURRENT_USER_NAME },
  };

  jitsiApi = new JitsiMeetExternalAPI('meet.jit.si', options);

  jitsiApi.on('videoConferenceJoined', () => {
    console.log('[Jitsi] Joined room ✔');
    showState('waiting');
    setStatusBadge('waiting', 'Waiting for partner...');
  });

  jitsiApi.on('participantJoined', (p) => {
    console.log('[Jitsi] Partner joined:', p.displayName);
    showState('ready');
    setStatusBadge('ready', '✅ Both Connected!');
    showBanner('🎙 Partner joined! You can now start recording.', 'success');
  });

  jitsiApi.on('participantLeft', () => {
    if (!isRecording) {
      showState('waiting');
      setStatusBadge('waiting', 'Waiting for partner...');
      showBanner('⚠️ Partner left the room.', 'warning');
    }
  });

  jitsiApi.on('videoConferenceLeft', () => {
    doLeave();
  });

  // After 20s in 'connecting', show a fallback help message
  setTimeout(() => {
    if (currentState === 'connecting') {
      showConnectError();
    }
  }, 20000);
}

function showConnectError() {
  const el = document.getElementById('state-connecting');
  if (el) {
    el.innerHTML = `
      <div class="bg-gray-900 border border-red-800/50 rounded-3xl p-10 text-center">
        <div class="text-4xl mb-4">⚠️</div>
        <h2 class="text-xl font-bold mb-2 text-red-400">Room failed to load</h2>
        <p class="text-gray-400 text-sm mb-6">The audio room could not start.<br>Check your internet connection and allow microphone access.</p>
        <button onclick="location.reload()" class="px-8 py-3 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl mr-3">
          🔄 Reload
        </button>
        <button onclick="doLeave()" class="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-xl">
          ✕ Cancel
        </button>
      </div>
    `;
  }
}

// ─── Recording ───────────────────────────────────────────────────
async function startRecording() {
  if (isRecording) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 48000,
        channelCount: 1,
      },
      video: false,
    });

    recordedChunks = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    mediaRecorder = new MediaRecorder(stream, { mimeType });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      capturedBlob = new Blob(recordedChunks, { type: mimeType });
      stream.getTracks().forEach(t => t.stop());
      showState('ended');
      setStatusBadge('ended', 'Session Complete');
      updateEndedStats();
    };

    mediaRecorder.start(1000); // chunk every 1s
    isRecording = true;
    showState('recording');
    setStatusBadge('recording', '🔴 Recording...');
    startTimer();

    // Notify server
    apiFetch(`/api/recordings/${SESSION_ID}/start/`, { method: 'POST' }).catch(() => {});
    document.getElementById('leave-btn-text').textContent = 'Stop & Leave';

  } catch (err) {
    console.error('[Mic] Error:', err);
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      showBanner('❌ Microphone access denied. Click the 🎤 icon in your browser address bar and allow microphone.', 'error');
    } else {
      showBanner(`⚠️ Microphone error: ${err.message}`, 'error');
    }
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    isRecording = false;
    stopTimer();
  }
}

// ─── Upload ──────────────────────────────────────────────────────
async function uploadRecording() {
  if (!capturedBlob) {
    showBanner('No recording to upload.', 'warning');
    return;
  }

  const btn = document.getElementById('upload-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="animate-spin mr-2">⏳</span> Uploading...'; }

  try {
    const formData = new FormData();
    const channel = IS_INITIATOR ? 'a' : 'b';
    const ext = capturedBlob.type.includes('webm') ? 'webm' : 'ogg';
    formData.append('file', capturedBlob, `recording_${channel}.${ext}`);
    formData.append('channel', channel);

    const res = await fetch(`/api/recordings/${SESSION_ID}/upload-chunk/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: formData,
    });

    if (res.ok) {
      if (btn) { btn.innerHTML = '✅ Uploaded'; btn.className = btn.className.replace('bg-green-600', 'bg-gray-700'); }
      showBanner('✅ Recording uploaded successfully!', 'success');
      // End session
      apiFetch(`/api/recordings/${SESSION_ID}/end/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration: timerSeconds }),
      }).catch(() => {});
    } else {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || 'Upload failed');
    }
  } catch (err) {
    console.error('[Upload] Error:', err);
    showBanner(`Upload failed: ${err.message}. Please try again.`, 'error');
    if (btn) { btn.disabled = false; btn.innerHTML = '☁️ Upload Recording'; }
  }
}

// ─── Cancel / Leave ──────────────────────────────────────────────
async function doLeave() {
  stopRecording();
  clearInterval(pollInterval);
  clearInterval(timerInterval);

  if (jitsiApi) {
    try { jitsiApi.dispose(); } catch (e) {}
    jitsiApi = null;
  }

  try {
    await fetch(`/api/recordings/${SESSION_ID}/cancel/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json' },
    });
  } catch (e) {}

  window.location.href = '/';
}

// Alias for Cancel button
function leaveSession() { doLeave(); }

// ─── Polling ─────────────────────────────────────────────────────
function startPolling() {
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/recordings/${SESSION_ID}/status/`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === 'rejected') {
        clearInterval(pollInterval);
        showBanner('Session was cancelled.', 'warning');
        setTimeout(() => { window.location.href = '/'; }, 2000);
      }
    } catch (e) { /* ignore polling errors */ }
  }, 5000);
}

// ─── State Machine ───────────────────────────────────────────────
function showState(state) {
  currentState = state;
  ['connecting', 'waiting', 'ready', 'recording', 'ended'].forEach(s => {
    const el = document.getElementById(`state-${s}`);
    if (el) el.classList.toggle('hidden', s !== state);
  });
}

function setStatusBadge(state, text) {
  const cfg = {
    connecting: 'bg-gray-700/40 text-gray-300 border-gray-600',
    waiting:    'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    ready:      'bg-green-500/10 text-green-400 border-green-500/20',
    recording:  'bg-red-500/10 text-red-400 border-red-500/20',
    ended:      'bg-blue-500/10 text-blue-400 border-blue-500/20',
  };
  const badge = document.getElementById('session-status-badge');
  const txt   = document.getElementById('status-text');
  if (txt) txt.textContent = text;
  if (badge && cfg[state]) {
    badge.className = `hidden sm:inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-semibold border ${cfg[state]}`;
  }
}

function updateEndedStats() {
  const el = document.getElementById('ended-duration');
  if (el) el.textContent = fmtTime(timerSeconds);
  const sz = document.getElementById('ended-size');
  if (sz && capturedBlob) sz.textContent = `${(capturedBlob.size / (1024 * 1024)).toFixed(2)} MB`;
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

function showBanner(msg, type) {
  const colors = {
    success: 'bg-green-900/80 text-green-300 border-green-700',
    warning: 'bg-yellow-900/80 text-yellow-300 border-yellow-700',
    error:   'bg-red-900/80 text-red-300 border-red-700',
    info:    'bg-blue-900/80 text-blue-300 border-blue-700',
  };
  const toast = document.createElement('div');
  toast.className = `fixed top-4 right-4 z-50 max-w-sm p-4 rounded-xl border ${colors[type] || colors.info} shadow-xl text-sm font-medium`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 7000);
}
