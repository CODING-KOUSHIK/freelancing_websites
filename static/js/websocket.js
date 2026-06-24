/**
 * WebSocket Manager — Handles Presence + Notifications connections
 * AI Voice Data Marketplace
 */

class WebSocketManager {
  constructor() {
    this.presenceSocket = null;
    this.notificationSocket = null;
    this.heartbeatTimer = null;
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 30000;
  }

  init() {
    this.connectPresence();
    this.connectNotifications();
  }

  /* ─── Presence WebSocket ──────────────────────────────────── */

  connectPresence() {
    const url = `${WS_PROTOCOL}//${window.location.host}/ws/presence/`;
    this.presenceSocket = new WebSocket(url);

    this.presenceSocket.onopen = () => {
      console.log('[WS] Presence connected');
      this.reconnectDelay = 1000;
      this.startHeartbeat();
    };

    this.presenceSocket.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'presence.update' || data.type === 'presence.init') {
        this.updateOnlineUsers(data.online_users);
      } else if (data.type === 'heartbeat.ack') {
        // Heartbeat acknowledged
      }
    };

    this.presenceSocket.onclose = (e) => {
      console.log('[WS] Presence disconnected, reconnecting...');
      this.stopHeartbeat();
      setTimeout(() => this.connectPresence(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    };

    this.presenceSocket.onerror = (e) => {
      console.error('[WS] Presence error:', e);
    };
  }

  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.presenceSocket && this.presenceSocket.readyState === WebSocket.OPEN) {
        this.presenceSocket.send(JSON.stringify({ type: 'heartbeat' }));
      }
    }, 30000);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  updateOnlineUsers(users) {
    const list = document.getElementById('online-users-list');
    const mobileList = document.getElementById('mobile-online-users-list');
    const count = document.getElementById('online-count');
    const mobileCount = document.getElementById('mobile-online-count');
    const badge = document.getElementById('mobile-online-badge');

    // Update counts
    if (count) count.textContent = users.length;
    if (mobileCount) mobileCount.textContent = users.length;

    // Show/hide mobile badge
    if (badge) {
      if (users.length > 0) {
        badge.textContent = users.length;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }

    const emptyMsg = '<p class="text-sm text-gray-500 text-center py-4">No users online</p>';

    if (users.length === 0) {
      if (list) list.innerHTML = '<p class="text-xs text-gray-600 text-center py-2">No users online</p>';
      if (mobileList) mobileList.innerHTML = emptyMsg;
      return;
    }

    const userHTML = users.map(u => `
      <div class="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-800/50 cursor-pointer transition-colors group"
           onclick="sendRecordingRequest('${u.id}', '${u.name}')">
        <div class="relative flex-shrink-0">
          ${u.avatar
            ? `<img src="${u.avatar}" class="w-10 h-10 rounded-full object-cover">`
            : `<div class="w-10 h-10 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center text-white text-sm font-bold">${u.name ? u.name[0].toUpperCase() : '?'}</div>`
          }
          <span class="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-400 rounded-full border-2 border-gray-900"></span>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium truncate group-hover:text-green-400 transition-colors">${u.name}</p>
          <p class="text-xs text-gray-500 capitalize">${u.level || 'beginner'}</p>
        </div>
        <button class="bg-green-500/20 hover:bg-green-500/40 text-green-400 text-xs px-3 py-1.5 rounded-lg transition-colors font-medium">
          <i class="fas fa-microphone mr-1"></i>Record
        </button>
      </div>
    `).join('');

    // Desktop sidebar
    if (list) list.innerHTML = userHTML;
    // Mobile drawer
    if (mobileList) mobileList.innerHTML = userHTML;
  }

  async loadRecordingStats() {
    try {
      const res = await apiFetch('/api/recordings/stats/');
      if (!res.ok) return;
      const data = await res.json();
      this.renderStatsPanel(data);
    } catch (e) { /* silent */ }
  }

  renderStatsPanel(data) {
    const panel = document.getElementById('recording-stats-panel');
    if (!panel) return;
    const p = data.personal || {};
    const plat = data.platform || {};
    panel.innerHTML = `
      <div class="space-y-2">
        <p class="text-xs text-gray-500 uppercase tracking-widest font-semibold mb-3">My Recording Stats</p>
        <div class="grid grid-cols-3 gap-2 mb-3">
          <div class="bg-green-500/10 rounded-xl p-2.5 text-center border border-green-500/20">
            <p class="text-lg font-bold text-green-400">${p.completed || 0}</p>
            <p class="text-[10px] text-gray-500">Completed</p>
          </div>
          <div class="bg-red-500/10 rounded-xl p-2.5 text-center border border-red-500/20">
            <p class="text-lg font-bold text-red-400">${p.rejected || 0}</p>
            <p class="text-[10px] text-gray-500">Rejected</p>
          </div>
          <div class="bg-blue-500/10 rounded-xl p-2.5 text-center border border-blue-500/20">
            <p class="text-lg font-bold text-blue-400">${p.in_progress || 0}</p>
            <p class="text-[10px] text-gray-500">Active</p>
          </div>
        </div>
        <div class="border-t border-gray-800 pt-3">
          <p class="text-xs text-gray-500 uppercase tracking-widest font-semibold mb-2">Platform (30d)</p>
          <div class="flex items-center justify-between text-xs text-gray-400 mb-1">
            <span>Success Rate</span>
            <span class="font-bold ${plat.success_rate >= 70 ? 'text-green-400' : plat.success_rate >= 40 ? 'text-yellow-400' : 'text-red-400'}">${plat.success_rate || 0}%</span>
          </div>
          <div class="h-1.5 bg-gray-800 rounded-full overflow-hidden mb-2">
            <div class="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full" style="width:${plat.success_rate || 0}%"></div>
          </div>
          <div class="flex justify-between text-[10px] text-gray-600">
            <span>✓ ${plat.completed || 0} done</span>
            <span>✗ ${plat.rejected || 0} rejected</span>
            <span>● ${plat.in_progress || 0} live</span>
          </div>
        </div>
      </div>
    `;
  }

  /* ─── Notification WebSocket ──────────────────────────────── */

  connectNotifications() {
    const url = `${WS_PROTOCOL}//${window.location.host}/ws/notifications/`;
    this.notificationSocket = new WebSocket(url);

    this.notificationSocket.onopen = () => {
      console.log('[WS] Notifications connected');
    };

    this.notificationSocket.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === 'notification.new') {
        this.handleNewNotification(data);
      } else if (data.type === 'notification.unread_count') {
        this.updateBadge(data.count);
      }
    };

    this.notificationSocket.onclose = () => {
      console.log('[WS] Notifications disconnected, reconnecting...');
      setTimeout(() => this.connectNotifications(), 3000);
    };
  }

  handleNewNotification(data) {
    // Show toast
    showToast(data.title, data.message, data.notification_type);

    // Update badge
    const badge = document.getElementById('notif-badge');
    if (badge) {
      let count = parseInt(badge.textContent) || 0;
      badge.textContent = count + 1;
      badge.classList.remove('hidden');
    }

    // Special handling for recording request
    if (data.notification_type === 'recording_request') {
      this.showRecordingPopup(data);
      return;
    }

    if (data.notification_type === 'recording_accepted') {
      const sessionId = data.payload && data.payload.session_id;
      if (sessionId) {
        const targetUrl = `/recordings/${sessionId}/`;
        if (window.location.pathname !== targetUrl) {
          setTimeout(() => {
            window.location.href = targetUrl;
          }, 300);
        }
      }
    }
  }

  showRecordingPopup(data) {
    const popup = document.getElementById('recording-popup');
    const msg = document.getElementById('popup-message');
    if (!popup || !msg) return;

    const payload = data.payload || {};
    msg.textContent = data.message || 'Someone wants to record with you!';
    popup.classList.remove('hidden');

    const acceptBtn = document.getElementById('accept-recording-btn');
    const rejectBtn = document.getElementById('reject-recording-btn');

    const sessionId = payload.session_id;

    acceptBtn.onclick = async () => {
      try {
        await apiFetch(`/api/recordings/${sessionId}/accept/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        popup.classList.add('hidden');
        window.location.href = `/recordings/${sessionId}/`;
      } catch (e) { console.error(e); }
    };

    rejectBtn.onclick = async () => {
      try {
        await apiFetch(`/api/recordings/${sessionId}/reject/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        popup.classList.add('hidden');
      } catch (e) { console.error(e); }
    };
  }

  updateBadge(count) {
    const badge = document.getElementById('notif-badge');
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count > 9 ? '9+' : count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }

  markRead(notifId) {
    if (this.notificationSocket && this.notificationSocket.readyState === WebSocket.OPEN) {
      this.notificationSocket.send(JSON.stringify({
        type: 'notification.mark_read',
        id: notifId,
      }));
    }
  }

  markAllRead() {
    if (this.notificationSocket && this.notificationSocket.readyState === WebSocket.OPEN) {
      this.notificationSocket.send(JSON.stringify({
        type: 'notification.mark_all_read',
      }));
    }
  }
}

function getAccessToken() {
  const token = localStorage.getItem('access_token');
  if (!token || token === 'null' || token === 'undefined') return '';
  return token;
}

function decodeJwtPayload(token) {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized + '='.repeat((4 - (normalized.length % 4 || 4)) % 4);
    return JSON.parse(atob(padded));
  } catch (error) {
    return null;
  }
}

function isUsableAccessToken(token) {
  if (!token) return false;
  const parts = token.split('.');
  if (parts.length !== 3) return false;
  const payload = decodeJwtPayload(token);
  if (!payload || payload.token_type !== 'access') return false;
  if (payload.exp && Date.now() >= payload.exp * 1000) return false;
  return true;
}

function clearStoredTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

function normalizeHeaders(extraHeaders = {}) {
  const headers = {};
  if (extraHeaders instanceof Headers) {
    extraHeaders.forEach((value, key) => {
      if (value !== undefined && value !== null && value !== '') {
        headers[key] = value;
      }
    });
    return headers;
  }

  Object.entries(extraHeaders || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      headers[key] = value;
    }
  });
  return headers;
}

function buildAuthHeaders(extraHeaders = {}) {
  const headers = normalizeHeaders(extraHeaders);
  const token = getAccessToken();
  if (isUsableAccessToken(token)) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function isJwtAuthError(payload) {
  const message = typeof payload === 'string'
    ? payload
    : JSON.stringify(payload || {});
  return /Given token not valid for any token type|token is blacklisted|token is invalid or expired|token has expired/i.test(message);
}

async function apiFetch(url, options = {}) {
  const {
    auth = true,
    retryOnAuthFailure = true,
    headers = {},
    credentials = 'same-origin',
    ...rest
  } = options;

  if (auth) {
    await ensureAccessToken();
  }

  let response = await fetch(url, {
    ...rest,
    headers: auth ? buildAuthHeaders(headers) : normalizeHeaders(headers),
    credentials,
  });

  if (!auth || !retryOnAuthFailure || (response.status !== 401 && response.status !== 403)) {
    return response;
  }

  let payload = null;
  try {
    payload = await response.clone().json();
  } catch (jsonError) {
    try {
      payload = await response.clone().text();
    } catch (textError) {
      payload = null;
    }
  }

  if (!isJwtAuthError(payload)) {
    return response;
  }

  localStorage.removeItem('access_token');
  await ensureAccessToken({ forceRefresh: true });
  response = await fetch(url, {
    ...rest,
    headers: auth ? buildAuthHeaders(headers) : normalizeHeaders(headers),
    credentials,
  });
  return response;
}

async function ensureAccessToken(options = {}) {
  const { forceRefresh = false } = options;
  const token = getAccessToken();
  if (!forceRefresh && isUsableAccessToken(token)) return token;

  if (token && (!isUsableAccessToken(token) || forceRefresh)) {
    localStorage.removeItem('access_token');
  }

  try {
    const refresh = localStorage.getItem('refresh_token');
    if (refresh && refresh !== 'null' && refresh !== 'undefined') {
      const refreshRes = await fetch('/api/auth/token/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ refresh }),
        credentials: 'same-origin',
      });
      if (refreshRes.ok) {
        const refreshData = await refreshRes.json().catch(() => ({}));
        if (refreshData.access) localStorage.setItem('access_token', refreshData.access);
        if (refreshData.refresh) localStorage.setItem('refresh_token', refreshData.refresh);
        if (isUsableAccessToken(refreshData.access)) return refreshData.access;
      } else {
        let refreshPayload = null;
        try {
          refreshPayload = await refreshRes.clone().json();
        } catch (jsonError) {
          try {
            refreshPayload = await refreshRes.clone().text();
          } catch (textError) {
            refreshPayload = null;
          }
        }
        if (isJwtAuthError(refreshPayload)) {
          localStorage.removeItem('refresh_token');
        }
      }
    }

    const res = await fetch('/api/auth/session-token/', {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
    });
    if (!res.ok) return '';

    const data = await res.json().catch(() => ({}));
    if (data.access && isUsableAccessToken(data.access)) localStorage.setItem('access_token', data.access);
    if (data.refresh) localStorage.setItem('refresh_token', data.refresh);
    return isUsableAccessToken(data.access) ? data.access : '';
  } catch (error) {
    return '';
  }
}

function extractApiError(data, fallback) {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  if (data.error) return data.error;
  if (data.non_field_errors) {
    return Array.isArray(data.non_field_errors) ? data.non_field_errors.join(' ') : data.non_field_errors;
  }
  const values = Object.values(data).flat().filter(Boolean);
  return values.length ? values.join(' ') : fallback;
}

/* ─── Global helpers ──────────────────────────────────────── */

function showToast(title, message, type = 'system') {
  const colors = {
    recording_request: 'border-l-4 border-green-500',
    earnings_credited: 'border-l-4 border-emerald-500',
    warning: 'border-l-4 border-red-500',
    default: 'border-l-4 border-blue-500',
  };
  const borderClass = colors[type] || colors.default;

  const toast = document.createElement('div');
  toast.className = `toast ${borderClass}`;
  toast.innerHTML = `
    <div class="flex items-start gap-3">
      <div class="flex-1">
        <p class="font-semibold text-sm">${title}</p>
        <p class="text-xs text-gray-400 mt-0.5">${message}</p>
      </div>
      <button onclick="this.closest('.toast').remove()" class="text-gray-500 hover:text-white text-xs mt-0.5">✕</button>
    </div>
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 8000);
}

async function sendRecordingRequest(targetUserId, targetName) {
  if (!confirm(`Send recording request to ${targetName}?`)) return;
  try {
    const res = await apiFetch('/api/recordings/request/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_user_id: targetUserId,
        sample_rate: '48kHz',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok || res.status === 201) {
      showToast('Request Sent', `Recording request sent to ${targetName}`, 'recording_request');
      // If auto-accepted, redirect
      if (data.status === 'accepted') {
        window.location.href = `/recordings/${data.session_id}/`;
      }
    } else {
      showToast('Error', extractApiError(data, 'Could not send request'), 'warning');
    }
  } catch (e) {
    showToast('Error', 'Network error', 'warning');
  }
}

/* ─── Init on page load ──────────────────────────────────── */
const wsManager = new WebSocketManager();
document.addEventListener('DOMContentLoaded', () => {
  if (typeof CURRENT_USER_ID !== 'undefined') {
    wsManager.init();
    // Load recording stats on pages that have the stats panel
    if (document.getElementById('recording-stats-panel')) {
      wsManager.loadRecordingStats();
      setInterval(() => wsManager.loadRecordingStats(), 60000);
    }
  }
});
