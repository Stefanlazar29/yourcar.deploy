/* offline/core.js — navigație + notificări proactive + helper-e */

(function() {
  // Safe-guards (previne ReferenceError dacă un modul nu s-a încărcat)
  if (typeof window.clearSiErr === 'undefined') window.clearSiErr = function() {};
  if (typeof window.clearErr === 'undefined') window.clearErr = function() {};
  if (typeof window.validateVIN === 'undefined') window.validateVIN = function() {};
  if (typeof window.confirmSignOut === 'undefined') window.confirmSignOut = function() {};

  function byId(id) { return document.getElementById(id); }

  function allScreens() {
    return Array.prototype.slice.call(document.querySelectorAll('.screen'));
  }

  function normalizeKey(key) {
    if (!key) return '';
    key = String(key).trim();
    return key.startsWith('s-') ? key : ('s-' + key);
  }

  window.show = function(key) {
    var id = normalizeKey(key);
    allScreens().forEach(function(s) { s.classList.remove('active'); });
    var el = byId(id);
    if (el) {
      try {
        el.removeAttribute('hidden');
        el.style.removeProperty('display');
      } catch (eShow) {}
      el.classList.add('active');
      if (id === 's-profile-settings' && typeof window.refreshProfileSettingsPreview === 'function') {
        try { window.refreshProfileSettingsPreview(); } catch (eR) {}
      }
    } else window.showToast('Ecran inexistent: ' + id);
  };

  window.setNav = function(which) {
    ['home','engine','ai'].forEach(function(k) {
      var el = byId('nav-' + k);
      if (el) el.classList.toggle('active', k === which);
    });
  };

  window.navClick = function(which) {
    if (which === 'engine') { window.show('engine'); window.setNav('engine'); return; }
    if (which === 'ai') { window.show('ai'); window.setNav('ai'); return; }
    window.show('dash'); window.setNav('home');
  };

  window.goPanel = function(which) {
    window.navClick(which);
  };

  window.panelBack = function() {
    window.show('dash');
    window.setNav('home');
  };

  window.showToast = function(msg) {
    try { console.log('[Mulberry]', msg); } catch (e) {}
  };

  // UX: Toast "Verificat cu succes" după login, pe pagina Mulberry ID
  window.showSuccessAuth = function() {
    var toast = document.getElementById('verify-toast');
    if (!toast) return;

    // Reset stări pentru re-apelare
    toast.classList.remove('fade-out');
    toast.classList.add('show');
    toast.style.display = 'flex';
    toast.classList.add('slide-down');

    setTimeout(function() {
      toast.classList.remove('slide-down');
      toast.classList.add('fade-out');
    }, 2000);

    setTimeout(function() {
      toast.classList.remove('fade-out');
      toast.classList.remove('show');
      toast.style.display = 'none';
    }, 2600);
  };

  // ─── Notificare proactivă (WebSocket) — card negru, neon, jos peste nav ───
  window.showProactiveNotification = function(title, message, ntype) {
    var existing = byId('mulberry-proactive-toast');
    if (existing) existing.remove();

    var wrap = document.createElement('div');
    wrap.id = 'mulberry-proactive-toast';
    wrap.className = 'proactive-toast proactive-toast-show';

    var icon = '&#9888;';
    if (ntype === 'info') icon = '&#8505;';
    else if (ntype === 'success') icon = '&#10003;';

    wrap.innerHTML = '<div class="proactive-toast-icon">' + icon + '</div>' +
      '<div class="proactive-toast-body">' +
        '<div class="proactive-toast-title">' + (title || 'Mulberry') + '</div>' +
        '<div class="proactive-toast-message">' + (message || '') + '</div>' +
      '</div>' +
      '<button type="button" class="proactive-toast-close" aria-label="Închide">&times;</button>';

    wrap.querySelector('.proactive-toast-close').onclick = function() {
      wrap.classList.remove('proactive-toast-show');
      wrap.classList.add('proactive-toast-hide');
      setTimeout(function() { wrap.remove(); }, 300);
    };

    document.body.appendChild(wrap);

    setTimeout(function() {
      if (wrap.parentNode) {
        wrap.classList.remove('proactive-toast-show');
        wrap.classList.add('proactive-toast-hide');
        setTimeout(function() { if (wrap.parentNode) wrap.remove(); }, 300);
      }
    }, 8000);
  };

  // ─── WebSocket: notificări proactive Mulberry Brain ───
  // Dezactivat implicit — conexiuni eșuate + reconnect declanșau zgomot în consolă și uneori interferențe cu sesiunea.
  // Pentru live: în consolă rulează `window.MULBERRY_WS_NOTIFICATIONS = true` apoi reîncarcă pagina.
  var WS_NOTIFICATIONS_ENABLED =
    typeof window.MULBERRY_WS_NOTIFICATIONS !== 'undefined' ? !!window.MULBERRY_WS_NOTIFICATIONS : false;

  var wsNotify = null;
  var wsReconnectTimer = null;
  var wsConnectTimeoutId = null;
  var wsReconnectAttempts = 0;
  var WS_MAX_RECONNECT = 8;
  var wsConnecting = false;

  function wsBase() {
    var raw = (window.Config && window.Config.apiBaseUrl) || window.API_BASE || 'http://127.0.0.1:9000';
    raw = String(raw || '').trim().replace(/\/+$/, '');
    if (!raw || raw === 'undefined' || raw === 'null') raw = 'http://127.0.0.1:9000';
    if (!/^https?:\/\//i.test(raw)) raw = 'http://' + raw.replace(/^\/+/, '');
    try {
      new URL(raw);
    } catch (e) {
      raw = 'http://127.0.0.1:9000';
    }
    if (raw.indexOf('https://') === 0) return 'wss://' + raw.slice(8);
    if (raw.indexOf('http://') === 0) return 'ws://' + raw.slice(7);
    return 'ws://127.0.0.1:9000';
  }

  function getJwtForWs() {
    try {
      return String(localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '').trim();
    } catch (e) {
      return '';
    }
  }

  function wsReconnectDelayMs(attemptIndex) {
    var n = Math.max(0, (attemptIndex || 1) - 1);
    return Math.min(60000, 5000 * Math.pow(2, n));
  }

  function connectProactiveWs(userId) {
    if (!WS_NOTIFICATIONS_ENABLED) return;
    if (!userId) return;
    if (wsConnecting) return;
    var token = getJwtForWs();
    if (!token || token.indexOf('eyJ') !== 0) {
      console.warn('[WS] Fără token JWT valid — sar peste WebSocket notificări.');
      return;
    }
    try {
      wsConnecting = true;
      if (wsConnectTimeoutId) {
        try { clearTimeout(wsConnectTimeoutId); } catch (e0) {}
        wsConnectTimeoutId = null;
      }
      if (wsNotify) {
        try { wsNotify.close(); } catch (e1) {}
        wsNotify = null;
      }
      var wsUrl = wsBase() + '/ws/notifications/' + userId;
      var ws = new WebSocket(wsUrl);
      wsNotify = ws;
      wsConnectTimeoutId = setTimeout(function() {
        wsConnectTimeoutId = null;
        if (ws && ws.readyState !== WebSocket.OPEN) {
          try { ws.close(); } catch (e2) {}
          console.warn('[WS] Timeout conectare (5s), backend probabil oprit.');
        }
      }, 5000);
      ws.onopen = function() {
        wsConnecting = false;
        wsReconnectAttempts = 0;
        if (wsConnectTimeoutId) {
          try { clearTimeout(wsConnectTimeoutId); } catch (e3) {}
          wsConnectTimeoutId = null;
        }
      };
      ws.onerror = function() {
        console.warn('[WS] Eroare conexiune (probabil backend oprit); backoff activ la închidere.');
      };
      ws.onmessage = function(ev) {
        try {
          var d = JSON.parse(ev.data);
          if (window.showProactiveNotification) {
            window.showProactiveNotification(d.title || 'Mulberry', d.message || '', d.type || 'info');
          }
        } catch (e) {}
      };
      ws.onclose = function() {
        wsConnecting = false;
        if (wsConnectTimeoutId) {
          try { clearTimeout(wsConnectTimeoutId); } catch (e4) {}
          wsConnectTimeoutId = null;
        }
        if (wsNotify === ws) wsNotify = null;
        if (userId && !wsReconnectTimer && WS_NOTIFICATIONS_ENABLED && wsReconnectAttempts < WS_MAX_RECONNECT) {
          wsReconnectAttempts++;
          var delay = wsReconnectDelayMs(wsReconnectAttempts);
          console.warn('[WS] Închis — următoarea încercare în ' + Math.round(delay / 1000) + 's (backoff exponențial, max 60s).');
          wsReconnectTimer = setTimeout(function() {
            wsReconnectTimer = null;
            connectProactiveWs(userId);
          }, delay);
        }
      };
    } catch (e) {
      wsConnecting = false;
    }
  }

  window.connectMulberryNotifications = function(userId) {
    connectProactiveWs(userId);
  };

  // Obține user ID numeric din API (după login) pentru WebSocket
  window.initMulberryNotifications = function() {
    var uid = (window.AppDB && window.AppDB.currentUser) ? window.AppDB.currentUser.id : null;
    if (uid && String(uid).match(/^\d+$/)) {
      connectProactiveWs(uid);
      return;
    }
    if (window.api && window.api.me) {
      window.api
        .me()
        .then(function(me) {
          if (me && me.id) connectProactiveWs(String(me.id));
        })
        .catch(function() {
          console.warn('[Core] /me indisponibil — notificări WebSocket omise.');
        });
    }
  };

  document.addEventListener('DOMContentLoaded', function() {
    if (window.AppDB && window.AppDB.currentUser && typeof window.initMulberryNotifications === 'function') {
      window.initMulberryNotifications();
    }
  });

  // ─── Scan QR /p/{VIN} — modal profil BIOS (GET /me/vehicles/profile/{VIN}) ───
  function apiBaseForProfile() {
    var raw =
      (window.CONFIG && window.CONFIG.API_BASE_URL) ||
      (window.Config && window.Config.apiBaseUrl) ||
      window.API_BASE ||
      'http://127.0.0.1:9000';
    raw = String(raw || '').trim().replace(/\/+$/, '');
    if (!raw || raw === 'undefined' || raw === 'null') raw = 'http://127.0.0.1:9000';
    return raw;
  }

  window.parseMulberryPublicProfileVin = function() {
    var path = window.location.pathname || '';
    var m = path.match(/\/p\/([A-HJ-NPR-Z0-9]{17})\/?$/i);
    if (m) return m[1].toUpperCase();
    var h = (window.location.hash || '').replace(/^#\/?/, '');
    if (/^p\//i.test(h)) {
      var seg = h.slice(2).split('/')[0].replace(/\s/g, '');
      if (/^[A-HJ-NPR-Z0-9]{17}$/i.test(seg)) return seg.toUpperCase();
    }
    var q = new URLSearchParams(window.location.search).get('p');
    if (q && /^[A-HJ-NPR-Z0-9]{17}$/i.test(String(q).trim())) return String(q).trim().toUpperCase();
    return null;
  };

  function escProfile(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderMulberryProfileModal(data) {
    var root = document.getElementById('mulberry-profile-modal-root');
    if (!root) return;
    var mlbrLine = data.mlbr_id ? '<div class="mlbr-id hdd-mlbr-sub">' + escProfile(data.mlbr_id) + '</div>' : '';
    root.innerHTML =
      '<div class="mulberry-profile-modal hdd-label-style">' +
      '<div class="profile-header hdd-section">' +
      '<div class="status-line">' +
      escProfile(data.status_line || '') +
      '</div>' +
      '<div class="mlbr-id">' +
      escProfile(data.model_line || '') +
      '</div>' +
      mlbrLine +
      '</div>' +
      '<div class="profile-body hdd-section">' +
      '<div class="tech-spec"><span class="label">OWNER:</span> <span class="value">' +
      escProfile(data.owner || '') +
      '</span></div>' +
      '<div class="tech-spec"><span class="label">LOCATION:</span> <span class="value">' +
      escProfile(data.location || '') +
      '</span></div>' +
      '<div class="tech-spec"><span class="label">VIN:</span> <span class="value">' +
      escProfile(data.vin || '') +
      '</span></div>' +
      '</div>' +
      '<div class="profile-interactions hdd-section">' +
      '<div class="section-label">03 // INTERACTION</div>' +
      '<button type="button" class="hdd-btn pulse-accent" data-mulberry-profile-action="chat">' +
      '<span class="icon">[ ]</span> MESSAGE_OWNER</button>' +
      '<button type="button" class="hdd-btn warn-accent" data-mulberry-profile-action="report">' +
      '<span class="icon">[!]</span> REPORT_OBSTRUCTION</button>' +
      '</div>' +
      '<div class="profile-footer hdd-section">' +
      '<span class="co-fo">MULBERRY HUB</span>' +
      '<span class="warranty">MADE IN CONTRAST WITH LOVE</span>' +
      '</div></div>';

    var btns = root.querySelectorAll('[data-mulberry-profile-action]');
    for (var bi = 0; bi < btns.length; bi++) {
      (function(btn) {
        btn.addEventListener('click', function() {
          var a = btn.getAttribute('data-mulberry-profile-action');
          if (a === 'chat' && typeof window.startChat === 'function') window.startChat('founder');
          if (a === 'report' && typeof window.reportIssue === 'function') window.reportIssue();
        });
      })(btns[bi]);
    }
  }

  window.startChat = function(mode) {
    var v = window.__mulberryProfileVin || '';
    var q = mode ? 'mode=' + encodeURIComponent(mode) : '';
    if (v) q += (q ? '&' : '') + 'vin=' + encodeURIComponent(v);
    window.location.href = 'mulberry_chat.html' + (q ? '?' + q : '');
  };

  window.reportIssue = function() {
    var v = window.__mulberryProfileVin || '';
    var sub = 'REPORT_OBSTRUCTION' + (v ? '%20' + encodeURIComponent(v) : '');
    window.location.href = 'mailto:contact@mulberry.ro?subject=' + sub;
  };

  window.openMulberryPublicProfile = function(vin) {
    return new Promise(function(resolve, reject) {
      if (!vin || String(vin).length !== 17) {
        reject(new Error('VIN invalid'));
        return;
      }
      window.__mulberryProfileVin = String(vin).toUpperCase();
      var loadEl = document.getElementById('mulberry-profile-loading');
      var errEl = document.getElementById('mulberry-profile-error');
      var root = document.getElementById('mulberry-profile-modal-root');
      if (typeof window.show === 'function') window.show('profile-scan');
      if (loadEl) {
        loadEl.hidden = false;
        try {
          loadEl.style.removeProperty('display');
        } catch (eD) {}
      }
      if (errEl) {
        errEl.hidden = true;
        errEl.textContent = '';
      }
      if (root) root.innerHTML = '';

      var tok = '';
      try {
        tok = localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '';
      } catch (e0) {}
      var headers = { Accept: 'application/json' };
      if (tok && tok.indexOf('eyJ') === 0) headers.Authorization = 'Bearer ' + tok;
      try {
        if (window.MulberryDevice && typeof window.MulberryDevice.headers === 'function') {
          var dh = window.MulberryDevice.headers();
          Object.keys(dh).forEach(function (k) {
            headers[k] = dh[k];
          });
        }
      } catch (eH) {}

      var url = apiBaseForProfile() + '/me/vehicles/profile/' + encodeURIComponent(vin);
      fetch(url, { headers: headers, mode: 'cors', cache: 'no-store' })
        .then(function(r) {
          if (!r.ok) return r.text().then(function(t) {
            throw new Error(t || 'HTTP ' + r.status);
          });
          return r.json();
        })
        .then(function(data) {
          if (loadEl) loadEl.hidden = true;
          renderMulberryProfileModal(data);
          resolve(data);
        })
        .catch(function(e) {
          if (loadEl) loadEl.hidden = true;
          if (errEl) {
            errEl.hidden = false;
            var msg = e && e.message ? String(e.message) : 'NETWORK';
            var unreachable =
              /failed to fetch|networkerror|load failed|aborted|timeout/i.test(msg) ||
              msg === 'NETWORK';
            errEl.textContent = unreachable
              ? '[!] SYNC_ERROR: PROFILE_UNREACHABLE'
              : 'PROFILE_LOAD_ERR // ' + msg;
          }
          reject(e);
        });
    });
  };

  window.openCarProfile = window.openMulberryPublicProfile;

  window.closeMulberryPublicProfile = function() {
    window.location.href = 'mulberry.html';
  };

  document.addEventListener('DOMContentLoaded', function() {
    var closeBtn = document.getElementById('mulberry-profile-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function() {
        window.closeMulberryPublicProfile();
      });
    }
    var bd = document.getElementById('profile-scan-backdrop');
    if (bd) {
      bd.addEventListener('click', function() {
        window.closeMulberryPublicProfile();
      });
    }
    document.addEventListener('keydown', function(ev) {
      if (ev.key !== 'Escape') return;
      var scan = document.getElementById('s-profile-scan');
      if (scan && scan.classList.contains('active')) window.closeMulberryPublicProfile();
    });
  });

  /** Audit la închiderea tab-ului: JWT doar în header (nu în body), keepalive pentru fiabilitate. */
  window.addEventListener('beforeunload', function() {
    try {
      var token = (window.api && window.api.getToken && window.api.getToken()) || '';
      if (!token || String(token).indexOf('eyJ') !== 0) return;
      var base =
        (window.CONFIG && window.CONFIG.API_BASE_URL) ||
        (window.Config && window.Config.apiBaseUrl) ||
        'http://127.0.0.1:9000';
      base = String(base)
        .trim()
        .replace(/\.+$/, '')
        .replace(/\/+$/, '');
      var url = base + '/auth/client-tab-close';
      var headers = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' };
      try {
        if (window.MulberryDevice && window.MulberryDevice.headers) {
          var d = window.MulberryDevice.headers();
          Object.keys(d).forEach(function(k) {
            headers[k] = d[k];
          });
        }
      } catch (eH) {}
      fetch(url, {
        method: 'POST',
        headers: headers,
        body: '{}',
        keepalive: true,
      }).catch(function() {});
    } catch (e) {}
  });

  /** Bara de jos (mulberry.html): la scroll se retrage; revine după pauză (citire). */
  (function initBottomTabBarScrollHide() {
    var SCROLL_IDLE_MS = 260;
    function bind() {
      var bar = document.querySelector('.bottom-tab-bar');
      var scrollEl = document.querySelector('#s-dash .scroll-body');
      if (!bar || !scrollEl) return;
      var idleTimer = null;
      function hideBar() {
        bar.classList.add('bottom-tab-bar--hidden');
      }
      function showBar() {
        bar.classList.remove('bottom-tab-bar--hidden');
      }
      function onScroll() {
        hideBar();
        if (idleTimer) clearTimeout(idleTimer);
        idleTimer = setTimeout(function() {
          idleTimer = null;
          showBar();
        }, SCROLL_IDLE_MS);
      }
      scrollEl.addEventListener('scroll', onScroll, { passive: true });
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bind);
    } else {
      bind();
    }
  })();

  console.log('Mulberry Core a fost încărcat cu succes!');
})();

