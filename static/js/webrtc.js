/**
 * WebRTC Manager — Dual-channel voice recording with peer connection
 * AI Voice Data Marketplace
 *
 * Creates a peer connection, captures local mic, sends to partner,
 * and records both channels separately in WAV 16-bit PCM format.
 */

class WebRTCManager {
  constructor(sessionId, isInitiator) {
    this.sessionId = sessionId;
    this.isInitiator = isInitiator;
    this.pc = null;
    this.localStream = null;
    this.remoteStream = null;
    this.ws = null;
    this.connected = false;
    this.peerJoined = false;
    this.offerCreated = false;
    this.signalingReady = false;
    this.pendingSignals = [];
    this.pendingIceCandidates = [];

    // Audio analysis
    this.localAnalyser = null;
    this.remoteAnalyser = null;
    this.audioContext = null;

    // ICE servers
    this.iceServers = [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' },
      { urls: 'stun:stun2.l.google.com:19302' },
    ];

    // Add TURN server if configured
    if (typeof TURN_URL !== 'undefined' && TURN_URL) {
      this.iceServers.push({
        urls: TURN_URL,
        username: typeof TURN_USERNAME !== 'undefined' ? TURN_USERNAME : '',
        credential: typeof TURN_CREDENTIAL !== 'undefined' ? TURN_CREDENTIAL : '',
      });
    }
  }

  async init() {
    try {
      // Create the peer connection first so early peer events can be queued safely.
      this.createPeerConnection();

      // Connect signaling WebSocket
      this.connectSignaling();

      // Get local media
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000,
          channelCount: 1,
        },
        video: false,
      });

      document.getElementById('local-audio').srcObject = this.localStream;

      // Setup audio analysis
      this.setupAudioAnalysis();

      // Add local tracks
      this.localStream.getTracks().forEach(track => {
        this.pc.addTrack(track, this.localStream);
      });

      this.signalingReady = true;
      await this.flushPendingSignals();
      await this.flushPendingIceCandidates();
      await this.tryCreateOffer();

      this.updateStatus('Waiting for peer...', 'yellow');

    } catch (err) {
      console.error('WebRTC init error:', err);
      if (err.name === 'NotAllowedError') {
        this.updateStatus('Microphone access denied', 'red');
      } else {
        this.updateStatus('Error: ' + err.message, 'red');
      }
    }
  }

  connectSignaling() {
    const url = `${WS_PROTOCOL}//${window.location.host}/ws/recording/${this.sessionId}/`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[WebRTC] Signaling connected');
    };

    this.ws.onmessage = async (e) => {
      const data = JSON.parse(e.data);

      switch (data.type) {
        case 'peer.joined':
          this.handlePeerJoined(data);
          break;

        case 'webrtc.signal':
          if (data.from_user !== CURRENT_USER_ID) {
            await this.handleSignal(data);
          }
          break;

        case 'peer.left':
          if (data.user_id !== CURRENT_USER_ID) {
            console.log('[WebRTC] Peer left');
            document.getElementById('partner-online-dot').className =
              'absolute bottom-0 right-0 w-5 h-5 bg-gray-600 rounded-full border-2 border-gray-900';
            this.updateStatus('Peer disconnected', 'red');
          }
          break;

        case 'recording.ended':
          this.updateStatus('Session ended', 'gray');
          break;
      }
    };

    this.ws.onclose = () => {
      console.log('[WebRTC] Signaling disconnected');
    };
  }

  handlePeerJoined(data) {
    if (data.user_id === CURRENT_USER_ID) return;

    console.log('[WebRTC] Peer joined:', data.user_name);
    this.peerJoined = true;

    const dot = document.getElementById('partner-online-dot');
    if (dot) {
      dot.className = 'absolute bottom-0 right-0 w-5 h-5 bg-green-400 rounded-full border-2 border-gray-900';
    }

    if (this.isInitiator) {
      this.tryCreateOffer();
    }
  }

  createPeerConnection() {
    this.pc = new RTCPeerConnection({ iceServers: this.iceServers });

    this.pc.onicecandidate = (event) => {
      if (event.candidate && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({
          type: 'webrtc.ice_candidate',
          payload: { candidate: event.candidate },
        }));
      }
    };

    this.pc.ontrack = (event) => {
      console.log('[WebRTC] Remote track received');
      this.remoteStream = event.streams[0];
      document.getElementById('remote-audio').srcObject = this.remoteStream;
      this.setupRemoteAnalysis();
      this.connected = true;
      this.updateStatus('Recording in progress', 'green');
      document.getElementById('rec-dot').classList.add('rec-pulse');

      // Start recording immediately, then sync session state with the API.
      if (typeof recordingManager !== 'undefined') {
        recordingManager.startRecording(this.localStream, this.remoteStream);
      }

      (async () => {
        try {
          await apiFetch(`/api/recordings/${this.sessionId}/start/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          });
        } catch (error) {
          console.error('[WebRTC] Failed to sync recording session start:', error);
        }
      })();
    };

    this.pc.onconnectionstatechange = () => {
      console.log('[WebRTC] Connection state:', this.pc.connectionState);
      if (this.pc.connectionState === 'failed') {
        this.updateStatus('Connection failed', 'red');
      } else if (this.pc.connectionState === 'disconnected') {
        this.updateStatus('Reconnecting...', 'yellow');
      }
    };
  }

  async createOffer() {
    try {
      if (!this.pc) return false;
      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);
      this.ws.send(JSON.stringify({
        type: 'webrtc.offer',
        payload: { sdp: this.pc.localDescription },
      }));
      return true;
    } catch (err) {
      console.error('Create offer error:', err);
      return false;
    }
  }

  async handleSignal(data) {
    if (!this.signalingReady || !this.pc) {
      this.pendingSignals.push(data);
      return;
    }

    await this.processSignal(data);
  }

  async processSignal(data) {
    try {
      if (data.signal_type === 'offer') {
        await this.pc.setRemoteDescription(new RTCSessionDescription(data.payload.sdp));
        await this.flushPendingIceCandidates();
        const answer = await this.pc.createAnswer();
        await this.pc.setLocalDescription(answer);
        this.ws.send(JSON.stringify({
          type: 'webrtc.answer',
          payload: { sdp: this.pc.localDescription },
        }));
      } else if (data.signal_type === 'answer') {
        await this.pc.setRemoteDescription(new RTCSessionDescription(data.payload.sdp));
        await this.flushPendingIceCandidates();
      } else if (data.signal_type === 'ice_candidate' && data.payload.candidate) {
        if (!this.pc.remoteDescription) {
          this.pendingIceCandidates.push(data.payload.candidate);
          return;
        }
        await this.pc.addIceCandidate(new RTCIceCandidate(data.payload.candidate));
      }
    } catch (err) {
      console.error('Handle signal error:', err);
    }
  }

  async flushPendingSignals() {
    if (!this.signalingReady || !this.pc || this.pendingSignals.length === 0) return;
    const signals = this.pendingSignals.splice(0, this.pendingSignals.length);
    for (const signal of signals) {
      await this.processSignal(signal);
    }
  }

  async flushPendingIceCandidates() {
    if (!this.pc || !this.pc.remoteDescription || this.pendingIceCandidates.length === 0) return;
    const candidates = this.pendingIceCandidates.splice(0, this.pendingIceCandidates.length);
    for (const candidate of candidates) {
      try {
        await this.pc.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (err) {
        console.error('Add pending ICE candidate error:', err);
      }
    }
  }

  async tryCreateOffer() {
    if (!this.isInitiator || !this.peerJoined || !this.signalingReady || !this.pc || !this.localStream) return;
    if (this.offerCreated) return;

    const created = await this.createOffer();
    if (created) {
      this.offerCreated = true;
    }
  }

  setupAudioAnalysis() {
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume().catch((err) => {
        console.warn('[WebRTC] Unable to resume audio context:', err);
      });
    }
    const source = this.audioContext.createMediaStreamSource(this.localStream);
    this.localAnalyser = this.audioContext.createAnalyser();
    this.localAnalyser.fftSize = 256;
    source.connect(this.localAnalyser);
  }

  setupRemoteAnalysis() {
    if (!this.remoteStream || !this.audioContext) return;
    const source = this.audioContext.createMediaStreamSource(this.remoteStream);
    this.remoteAnalyser = this.audioContext.createAnalyser();
    this.remoteAnalyser.fftSize = 256;
    source.connect(this.remoteAnalyser);
  }

  getLocalLevel() {
    if (!this.localAnalyser) return 0;
    const data = new Uint8Array(this.localAnalyser.frequencyBinCount);
    this.localAnalyser.getByteFrequencyData(data);
    return Math.min(100, (data.reduce((a, b) => a + b, 0) / data.length) * 1.5);
  }

  getRemoteLevel() {
    if (!this.remoteAnalyser) return 0;
    const data = new Uint8Array(this.remoteAnalyser.frequencyBinCount);
    this.remoteAnalyser.getByteFrequencyData(data);
    return Math.min(100, (data.reduce((a, b) => a + b, 0) / data.length) * 1.5);
  }

  updateStatus(text, color) {
    const statusEl = document.getElementById('session-status-badge');
    const recText = document.getElementById('rec-status-text');
    if (statusEl) {
      const colors = {
        green: 'bg-green-500/10 text-green-400 border border-green-500/20',
        yellow: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
        red: 'bg-red-500/10 text-red-400 border border-red-500/20',
        gray: 'bg-gray-700/50 text-gray-400 border border-gray-600',
      };
      statusEl.className = `inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold ${colors[color] || colors.gray}`;
      statusEl.innerHTML = `<span class="w-2 h-2 bg-${color}-400 rounded-full ${color === 'green' ? 'animate-pulse' : ''}"></span> ${text}`;
    }
    if (recText) recText.textContent = text;
  }

  endSession() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'recording.end',
        duration: typeof timerSeconds !== 'undefined' ? timerSeconds : 0,
      }));
    }
    if (this.localStream) {
      this.localStream.getTracks().forEach(t => t.stop());
    }
    if (this.pc) {
      this.pc.close();
    }
    if (this.audioContext) {
      this.audioContext.close();
    }
    this.connected = false;
  }

  toggleMute() {
    if (!this.localStream) return false;
    const track = this.localStream.getAudioTracks()[0];
    if (track) {
      track.enabled = !track.enabled;
      return !track.enabled; // returns true if now muted
    }
    return false;
  }
}

/* ─── Global init (called from session.html) ─────────────── */
let webrtcManager;

document.addEventListener('DOMContentLoaded', () => {
  if (typeof SESSION_ID !== 'undefined') {
    // Determine if this user is the initiator (user_a)
    const isInitiator = document.body.dataset.initiator === 'true';
    webrtcManager = new WebRTCManager(SESSION_ID, isInitiator);
    webrtcManager.init();
  }
});
