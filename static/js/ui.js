/**
 * UI Manager — Dropdowns, search, dark mode toggle, global interactions
 * AI Voice Data Marketplace
 */

/* ─── Mobile Online Users Panel ─────────────────────────────── */
function toggleMobileOnlinePanel() {
  const drawer = document.getElementById('mobile-online-drawer');
  const backdrop = document.getElementById('mobile-drawer-backdrop');
  if (!drawer) return;
  const isOpen = !drawer.classList.contains('translate-y-full');
  if (isOpen) {
    drawer.classList.add('translate-y-full');
    if (backdrop) backdrop.classList.add('hidden');
    document.body.style.overflow = '';
  } else {
    drawer.classList.remove('translate-y-full');
    if (backdrop) backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
}

document.addEventListener('DOMContentLoaded', () => {

  /* ─── Notification dropdown toggle ──────────────────────── */
  const notifBtn = document.getElementById('notif-btn');
  const notifDrop = document.getElementById('notif-dropdown');
  if (notifBtn && notifDrop) {
    notifBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      notifDrop.classList.toggle('hidden');
      if (!notifDrop.classList.contains('hidden')) loadNotifDropdown();
    });
  }

  /* ─── User menu dropdown toggle ─────────────────────────── */
  const userBtn = document.getElementById('user-menu-btn');
  const userMenu = document.getElementById('user-menu');
  if (userBtn && userMenu) {
    userBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      userMenu.classList.toggle('hidden');
    });
  }

  /* ─── Close dropdowns on outside click ──────────────────── */
  document.addEventListener('click', () => {
    if (notifDrop) notifDrop.classList.add('hidden');
    if (userMenu) userMenu.classList.add('hidden');
  });

  /* ─── Mark all read button ──────────────────────────────── */
  const markAllBtn = document.getElementById('mark-all-read');
  if (markAllBtn) {
    markAllBtn.addEventListener('click', async () => {
      if (typeof wsManager !== 'undefined') wsManager.markAllRead();
      try {
        await apiFetch('/api/notifications/mark-read/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        loadNotifDropdown();
      } catch (e) { console.error(e); }
    });
  }

  /* ─── Logout ────────────────────────────────────────────── */
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        const refresh = localStorage.getItem('refresh_token');
        if (refresh) {
          await fetch('/api/auth/logout/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh }),
          });
        }
      } catch (e) {}
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login/';
    });
  }

  /* ─── User search (sidebar) ─────────────────────────────── */
  const searchInput = document.getElementById('user-search');
  const searchResults = document.getElementById('search-results');
  let searchTimer = null;

  if (searchInput && searchResults) {
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      const q = searchInput.value.trim();
      if (q.length < 2) { searchResults.innerHTML = ''; return; }
      searchTimer = setTimeout(() => searchUsers(q), 400);
    });
  }

  async function searchUsers(query) {
    try {
      const res = await apiFetch(`/api/presence/search/?q=${encodeURIComponent(query)}&online_only=true`, {
        headers: {},
      });
      const users = await res.json();
      if (searchResults) {
        searchResults.innerHTML = users.map(u => `
          <div class="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-800 cursor-pointer transition-colors"
               onclick="sendRecordingRequest('${u.id}', '${u.full_name}')">
            <div class="w-7 h-7 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              ${u.full_name ? u.full_name[0].toUpperCase() : '?'}
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm truncate">${u.full_name}</p>
              <p class="text-xs text-gray-600">${u.is_online ? '🟢 Online' : u.last_seen || 'Offline'}</p>
            </div>
          </div>
        `).join('');
      }
    } catch (e) { console.error(e); }
  }

  /* ─── Token refresh ─────────────────────────────────────── */
  setInterval(async () => {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh || refresh === 'null' || refresh === 'undefined') return;
    try {
      const res = await fetch('/api/auth/token/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ refresh }),
        credentials: 'same-origin',
      });
      if (!res.ok) {
        let payload = null;
        try {
          payload = await res.clone().json();
        } catch (jsonError) {
          try {
            payload = await res.clone().text();
          } catch (textError) {
            payload = null;
          }
        }
        const message = typeof payload === 'string' ? payload : JSON.stringify(payload || {});
        if (/Given token not valid for any token type|token is blacklisted|token is invalid or expired|token has expired/i.test(message)) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (data.access) localStorage.setItem('access_token', data.access);
      if (data.refresh) localStorage.setItem('refresh_token', data.refresh);
    } catch (e) { console.error('Token refresh failed'); }
  }, 25 * 60 * 1000); // every 25 minutes

});

/* ─── Notification dropdown loader ────────────────────────── */
async function loadNotifDropdown() {
  const list = document.getElementById('notif-list');
  if (!list) return;
  try {
    const res = await apiFetch('/api/notifications/', {
      headers: {},
    });
    const data = await res.json();
    const results = data.results || [];
    if (results.length) {
      list.innerHTML = results.slice(0, 10).map(n => `
        <div class="px-4 py-3 hover:bg-gray-800 transition-colors cursor-pointer border-b border-gray-800/50 ${n.is_read ? 'opacity-50' : ''}"
             onclick="window.location.href='${n.action_url || '/dashboard/'}'">
          <p class="text-sm font-medium">${n.title}</p>
          <p class="text-xs text-gray-500 mt-0.5 line-clamp-2">${n.message}</p>
          <p class="text-xs text-gray-600 mt-1">${timeSince(n.created_at)}</p>
        </div>
      `).join('');
    } else {
      list.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">No notifications</div>';
    }
  } catch (e) { console.error(e); }
}

function timeSince(dateStr) {
  const seconds = Math.floor((new Date() - new Date(dateStr)) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
  if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
  return Math.floor(seconds / 86400) + 'd ago';
}
