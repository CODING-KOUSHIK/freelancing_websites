/**
 * Recording Manager — Dual-channel WAV recording with auto-save
 * AI Voice Data Marketplace
 *
 * Records two separate MediaStreams (local + remote) into
 * a stereo WAV file: Ch1=local, Ch2=remote. 16-bit PCM.
 * Auto-saves chunks every 10 minutes via API.
 */

class RecordingManager {
  constructor() {
    this.isRecording = false;
    this.audioContext = null;
    this.localProcessor = null;
    this.remoteProcessor = null;
    this.localBuffers = [];
    this.remoteBuffers = [];
    this.chunkIndex = 0;
    this.autoSaveInterval = null;
    this.sampleRate = 48000;
    this.AUTO_SAVE_MS = 10 * 60 * 1000; // 10 minutes
  }

  startRecording(localStream, remoteStream) {
    if (this.isRecording) return;
    this.isRecording = true;

    this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this.sampleRate });
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume().catch((err) => {
        console.warn('[Recording] Unable to resume audio context:', err);
      });
    }

    // Local channel
    const localSource = this.audioContext.createMediaStreamSource(localStream);
    this.localProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);
    this.localProcessor.onaudioprocess = (e) => {
      if (!this.isRecording) return;
      this.localBuffers.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };
    localSource.connect(this.localProcessor);
    this.localProcessor.connect(this.audioContext.destination);

    // Remote channel
    const remoteSource = this.audioContext.createMediaStreamSource(remoteStream);
    this.remoteProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);
    this.remoteProcessor.onaudioprocess = (e) => {
      if (!this.isRecording) return;
      this.remoteBuffers.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };
    remoteSource.connect(this.remoteProcessor);
    this.remoteProcessor.connect(this.audioContext.destination);

    // Auto-save every 10 minutes
    this.autoSaveInterval = setInterval(() => this.autoSaveChunk(), this.AUTO_SAVE_MS);

    console.log('[Recording] Started dual-channel recording at', this.sampleRate, 'Hz');
  }

  stopRecording() {
    this.isRecording = false;
    if (this.autoSaveInterval) clearInterval(this.autoSaveInterval);
    if (this.localProcessor) this.localProcessor.disconnect();
    if (this.remoteProcessor) this.remoteProcessor.disconnect();
    return this.generateStereoWav();
  }

  autoSaveChunk() {
    if (!this.isRecording) return;
    this.chunkIndex++;

    const localBlob = this.generateMonoWav(this.localBuffers);
    const remoteBlob = this.generateMonoWav(this.remoteBuffers);

    // Upload chunk via API
    this.uploadChunk(localBlob, 'a', this.chunkIndex);
    this.uploadChunk(remoteBlob, 'b', this.chunkIndex);

    // Clear buffers after saving
    this.localBuffers = [];
    this.remoteBuffers = [];

    const el = document.getElementById('autosave-status');
    const ts = document.getElementById('last-saved');
    if (el) el.textContent = `Chunk ${this.chunkIndex} auto-saved`;
    if (ts) ts.textContent = new Date().toLocaleTimeString();

    console.log(`[Recording] Auto-saved chunk ${this.chunkIndex}`);
  }

  async uploadChunk(blob, channel, index) {
    try {
      const formData = new FormData();
      formData.append('file', blob, `chunk_${index}_ch${channel}.wav`);
      formData.append('channel', channel);
      formData.append('chunk_index', index);
      formData.append('duration_seconds', Math.floor(blob.size / (this.sampleRate * 2)));

      await apiFetch(`/api/recordings/${SESSION_ID}/chunk/`, {
        method: 'POST',
        body: formData,
      });
    } catch (e) {
      console.error('[Recording] Chunk upload error:', e);
    }
  }

  generateStereoWav() {
    const localData = this.mergeBuffers(this.localBuffers);
    const remoteData = this.mergeBuffers(this.remoteBuffers);
    const length = Math.min(localData.length, remoteData.length);

    const buffer = new ArrayBuffer(44 + length * 4); // stereo 16-bit = 4 bytes/sample
    const view = new DataView(buffer);

    // WAV Header
    this.writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + length * 4, true);
    this.writeString(view, 8, 'WAVE');
    this.writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);          // chunk size
    view.setUint16(20, 1, true);           // PCM
    view.setUint16(22, 2, true);           // stereo
    view.setUint32(24, this.sampleRate, true);
    view.setUint32(28, this.sampleRate * 4, true); // byte rate
    view.setUint16(32, 4, true);           // block align
    view.setUint16(34, 16, true);          // bits per sample
    this.writeString(view, 36, 'data');
    view.setUint32(40, length * 4, true);

    // Interleave: Ch1=local, Ch2=remote
    let offset = 44;
    for (let i = 0; i < length; i++) {
      const localSample = Math.max(-1, Math.min(1, localData[i]));
      const remoteSample = Math.max(-1, Math.min(1, remoteData[i]));
      view.setInt16(offset, localSample < 0 ? localSample * 0x8000 : localSample * 0x7FFF, true);
      offset += 2;
      view.setInt16(offset, remoteSample < 0 ? remoteSample * 0x8000 : remoteSample * 0x7FFF, true);
      offset += 2;
    }

    return new Blob([buffer], { type: 'audio/wav' });
  }

  generateMonoWav(buffers) {
    const data = this.mergeBuffers(buffers);
    const buffer = new ArrayBuffer(44 + data.length * 2);
    const view = new DataView(buffer);

    this.writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + data.length * 2, true);
    this.writeString(view, 8, 'WAVE');
    this.writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, this.sampleRate, true);
    view.setUint32(28, this.sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    this.writeString(view, 36, 'data');
    view.setUint32(40, data.length * 2, true);

    let offset = 44;
    for (let i = 0; i < data.length; i++) {
      const s = Math.max(-1, Math.min(1, data[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
  }

  mergeBuffers(buffers) {
    let length = 0;
    for (const b of buffers) length += b.length;
    const result = new Float32Array(length);
    let offset = 0;
    for (const b of buffers) { result.set(b, offset); offset += b.length; }
    return result;
  }

  writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }
}

// ─── Page-level recording logic ─────────────────────────────

let recordingManager;
let timerSeconds = 0;
let timerInterval = null;
let isMuted = false;

document.addEventListener('DOMContentLoaded', () => {
  if (typeof SESSION_ID !== 'undefined') {
    recordingManager = new RecordingManager();
    startTimer();
    startVisualizer();
  }
});

function startTimer() {
  timerInterval = setInterval(() => {
    timerSeconds++;
    const h = Math.floor(timerSeconds / 3600);
    const m = Math.floor((timerSeconds % 3600) / 60);
    const s = timerSeconds % 60;
    document.getElementById('timer').textContent =
      `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    // Estimated earnings
    const rate = typeof PER_MINUTE_RATE !== 'undefined' ? PER_MINUTE_RATE : 2.5;
    const earnings = ((timerSeconds / 60) * rate).toFixed(2);
    document.getElementById('est-earnings').textContent = `₹${earnings}`;
  }, 1000);
}

function startVisualizer() {
  const canvas = document.getElementById('waveform-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  function draw() {
    requestAnimationFrame(draw);
    const w = canvas.width = canvas.offsetWidth;
    const h = canvas.height = canvas.offsetHeight;
    ctx.clearRect(0, 0, w, h);

    // Get levels
    let localLevel = 0, remoteLevel = 0;
    if (typeof webrtcManager !== 'undefined' && webrtcManager) {
      localLevel = webrtcManager.getLocalLevel();
      remoteLevel = webrtcManager.getRemoteLevel();
    }

    // Update level bars
    const levelA = document.getElementById('level-a');
    const levelB = document.getElementById('level-b');
    if (levelA) levelA.style.width = `${localLevel}%`;
    if (levelB) levelB.style.width = `${remoteLevel}%`;

    // Draw waveform
    const time = Date.now() / 1000;
    ctx.lineWidth = 2;

    // Local waveform (green)
    ctx.strokeStyle = 'rgba(34, 197, 94, 0.6)';
    ctx.beginPath();
    for (let x = 0; x < w; x++) {
      const amp = (localLevel / 100) * (h * 0.3);
      const y = h / 2 + Math.sin((x * 0.02) + time * 3) * amp + Math.sin((x * 0.05) + time * 5) * amp * 0.3;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Remote waveform (blue)
    ctx.strokeStyle = 'rgba(96, 165, 250, 0.6)';
    ctx.beginPath();
    for (let x = 0; x < w; x++) {
      const amp = (remoteLevel / 100) * (h * 0.3);
      const y = h / 2 + Math.sin((x * 0.025) + time * 2.5 + 1) * amp + Math.cos((x * 0.04) + time * 4) * amp * 0.25;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  draw();
}

function toggleMute() {
  if (typeof webrtcManager !== 'undefined' && webrtcManager) {
    isMuted = webrtcManager.toggleMute();
    const icon = document.getElementById('mute-icon');
    const label = document.getElementById('mute-label');
    const btn = document.getElementById('btn-mute');
    if (isMuted) {
      icon.className = 'fas fa-microphone-slash text-red-400 text-xl mb-1';
      label.textContent = 'Unmute';
      btn.classList.add('muted');
    } else {
      icon.className = 'fas fa-microphone text-green-400 text-xl mb-1';
      label.textContent = 'Mute';
      btn.classList.remove('muted');
    }
  }
}

function toggleSpeaker() {
  const audio = document.getElementById('remote-audio');
  if (audio) audio.muted = !audio.muted;
}

async function endSession() {
  if (!confirm('End this recording session?')) return;
  if (timerInterval) clearInterval(timerInterval);

  // Stop recording and get final WAV
  let finalBlob = null;
  if (recordingManager) {
    finalBlob = recordingManager.stopRecording();
  }

  // End via API
  try {
    await apiFetch(`/api/recordings/${SESSION_ID}/end/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (e) { console.error(e); }

  // End WebRTC
  if (typeof webrtcManager !== 'undefined' && webrtcManager) {
    webrtcManager.endSession();
  }

  // Show rating modal
  document.getElementById('rating-modal').classList.remove('hidden');
}

// ─── Rating ──────────────────────────────────────────────────
let selectedRating = 0;

function setRating(value) {
  selectedRating = value;
  document.querySelectorAll('.star-btn').forEach(btn => {
    const v = parseInt(btn.dataset.value);
    btn.className = `star-btn text-4xl transition-colors ${v <= value ? 'text-yellow-400' : 'text-gray-600'} hover:text-yellow-400`;
  });
}

async function submitRating() {
  if (selectedRating === 0) { alert('Please select a rating'); return; }
  try {
    await apiFetch('/api/ratings/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID,
        score: selectedRating,
        feedback: document.getElementById('rating-feedback').value,
      }),
    });
  } catch (e) { console.error(e); }
  window.location.href = '/dashboard/';
}

function skipRating() {
  window.location.href = '/dashboard/';
}

// ─── Page unload: save recording ─────────────────────────────
window.addEventListener('beforeunload', (e) => {
  if (recordingManager && recordingManager.isRecording) {
    recordingManager.autoSaveChunk();
    e.preventDefault();
    e.returnValue = 'Recording in progress. Are you sure you want to leave?';
  }
});
