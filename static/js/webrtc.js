/**
 * webrtc.js — WebRTC peer connection manager for VoiceMarket recording rooms
 *
 * IMPORTANT: Does NOT open its own WebSocket.
 * It receives signaling messages forwarded from recording.js (single WS).
 *
 * API:
 *   window.webRTC.init(localStream)  — called after mic permission granted
 *   window.webRTC.handleSignal(msg)  — called from recording.js on webrtc.* messages
 *   window.webRTC.sendViaWS(data)    — injected by recording.js
 *   window.webRTC.cleanup()          — called on session end
 */

window.webRTC = (() => {
  let pc = null;
  let localStream = null;
  let remoteStream = null;
  let isInitiator = false;
  let audioCtx = null;
  let localAnalyser = null;
  let remoteAnalyser = null;
  let peerConnected = false;
  let offerSent = false;
  let pendingCandidates = [];

  const ICE_SERVERS = [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    { urls: 'stun:stun2.l.google.com:19302' },
    { urls: 'stun:openrelay.metered.ca:80' },
  ];

  // Injected by recording.js so we can send back through its WS
  let _sendFn = null;

  function setSendFn(fn) { _sendFn = fn; }

  function send(data) {
    if (_sendFn) _sendFn(data);
    else console.warn('[WebRTC] No send function registered');
  }

  // ─── Init ────────────────────────────────────────────────────
  function init(stream, initiator) {
    localStream = stream;
    isInitiator = initiator;

    // Setup audio analysis for waveform
    setupLocalAnalysis();

    // Create peer connection
    createPC();

    // Add local tracks
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

    console.log('[WebRTC] Initialized. isInitiator:', isInitiator);
  }

  function createPC() {
    pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

    pc.onicecandidate = (e) => {
      if (e.candidate) {
        send({
          type: 'webrtc.ice_candidate',
          payload: { candidate: e.candidate },
        });
      }
    };

    pc.ontrack = (e) => {
      console.log('[WebRTC] Remote track received');
      remoteStream = e.streams[0];
      const remoteAudio = document.getElementById('remote-audio');
      if (remoteAudio) remoteAudio.srcObject = remoteStream;
      setupRemoteAnalysis();
      peerConnected = true;

      // Expose stream for recording
      window.webRTC.remoteStream = remoteStream;
    };

    pc.onconnectionstatechange = () => {
      console.log('[WebRTC] Connection state:', pc.connectionState);
      if (pc.connectionState === 'failed') {
        console.error('[WebRTC] Connection failed — attempting restart');
        restartIce();
      }
    };

    pc.oniceconnectionstatechange = () => {
      console.log('[WebRTC] ICE state:', pc.iceConnectionState);
    };
  }

  async function createOffer() {
    if (!pc || offerSent) return;
    try {
      const offer = await pc.createOffer({ offerToReceiveAudio: true });
      await pc.setLocalDescription(offer);
      send({ type: 'webrtc.offer', payload: { sdp: pc.localDescription } });
      offerSent = true;
      console.log('[WebRTC] Offer sent');
    } catch (e) {
      console.error('[WebRTC] createOffer error:', e);
    }
  }

  async function handleSignal(msg) {
    if (!pc) return;

    const stype = msg.signal_type;

    if (stype === 'offer') {
      console.log('[WebRTC] Received offer');
      await pc.setRemoteDescription(new RTCSessionDescription(msg.payload.sdp));
      await flushCandidates();
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      send({ type: 'webrtc.answer', payload: { sdp: pc.localDescription } });
      console.log('[WebRTC] Answer sent');
    } else if (stype === 'answer') {
      console.log('[WebRTC] Received answer');
      await pc.setRemoteDescription(new RTCSessionDescription(msg.payload.sdp));
      await flushCandidates();
    } else if (stype === 'ice_candidate' && msg.payload?.candidate) {
      if (!pc.remoteDescription) {
        pendingCandidates.push(msg.payload.candidate);
      } else {
        try {
          await pc.addIceCandidate(new RTCIceCandidate(msg.payload.candidate));
        } catch (e) {
          console.warn('[WebRTC] ICE candidate error:', e.message);
        }
      }
    }
  }

  async function flushCandidates() {
    const toAdd = [...pendingCandidates];
    pendingCandidates = [];
    for (const c of toAdd) {
      try { await pc.addIceCandidate(new RTCIceCandidate(c)); } catch (e) {}
    }
  }

  async function restartIce() {
    if (!pc || !isInitiator) return;
    try {
      const offer = await pc.createOffer({ iceRestart: true });
      await pc.setLocalDescription(offer);
      send({ type: 'webrtc.offer', payload: { sdp: pc.localDescription } });
    } catch (e) {
      console.error('[WebRTC] ICE restart failed:', e);
    }
  }

  // Called when peer.joined arrives from consumer (meaning both are in room)
  function onPeerJoined() {
    if (isInitiator && pc) {
      createOffer();
    }
  }

  // ─── Audio Analysis ──────────────────────────────────────────
  function setupLocalAnalysis() {
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') audioCtx.resume();
      const src = audioCtx.createMediaStreamSource(localStream);
      localAnalyser = audioCtx.createAnalyser();
      localAnalyser.fftSize = 256;
      src.connect(localAnalyser);
    } catch (e) { console.warn('[WebRTC] Audio analysis setup failed:', e); }
  }

  function setupRemoteAnalysis() {
    if (!remoteStream || !audioCtx) return;
    try {
      const src = audioCtx.createMediaStreamSource(remoteStream);
      remoteAnalyser = audioCtx.createAnalyser();
      remoteAnalyser.fftSize = 256;
      src.connect(remoteAnalyser);
    } catch (e) { console.warn('[WebRTC] Remote analysis setup failed:', e); }
  }

  function getLevel(analyser) {
    if (!analyser) return 0;
    const buf = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(buf);
    return Math.min(100, (buf.reduce((a, b) => a + b, 0) / buf.length) * 2);
  }

  function getLocalLevel() { return getLevel(localAnalyser); }
  function getRemoteLevel() { return getLevel(remoteAnalyser); }

  // ─── Controls ────────────────────────────────────────────────
  function setMute(muted) {
    if (localStream) {
      localStream.getAudioTracks().forEach(t => { t.enabled = !muted; });
    }
  }

  function cleanup() {
    if (localStream) localStream.getTracks().forEach(t => t.stop());
    if (pc) { pc.close(); pc = null; }
    if (audioCtx) { audioCtx.close(); audioCtx = null; }
    peerConnected = false;
  }

  return {
    init,
    handleSignal,
    onPeerJoined,
    setSendFn,
    cleanup,
    setMute,
    getLocalLevel,
    getRemoteLevel,
    get localStream() { return localStream; },
    get peerConnected() { return peerConnected; },
    get _pc() { return pc; },
  };
})();
