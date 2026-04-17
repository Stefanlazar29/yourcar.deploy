/**
 * auth.js — Mulberry · Backend-first auth
 * 1. Încearcă login/register la FastAPI (SQLite real)
 * 2. Fallback la localStorage doar dacă backend e offline
 */

(function () {
  'use strict';

  /**
   * Afișare/ascundere parolă — global imediat (înainte de restul modulului).
   * mulberry.html, partners.html etc.: onclick="togglePassVis('si-pass', this)"
   */
  window.togglePassVis = function (inputId, btn) {
    var input = inputId ? document.getElementById(inputId) : null;
    if (!input && btn && btn.previousElementSibling && btn.previousElementSibling.tagName === 'INPUT') {
      input = btn.previousElementSibling;
    }
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
    if (btn && btn.style) btn.style.opacity = input.type === 'password' ? '0.5' : '1';
  };

  async function sha256(str) {
    var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
    return Array.from(new Uint8Array(buf))
      .map(function (b) { return b.toString(16).padStart(2, '0'); })
      .join('');
  }

  var USERS_KEY   = 'mulberry_users_db';
  var SESSION_KEY = 'mulberry_session';
  var TOKEN_KEY   = 'yourcar_token';
  /** Rute FastAPI — obligatoriu slash inițial (altfel concatenarea cu baza dă URL invalid). */
  var AUTH_LOGIN_PATH = '/auth/login';
  var AUTH_REGISTER_PATH = '/auth/register';

  /**
   * Bază API cu schema obligatorie (http/https). Evită `new URL()` / fetch pe „127.0.0.1:9000” fără protocol.
   */
  function apiResolveBase() {
    var raw =
      (window.MULBERRY_API_ROOT && String(window.MULBERRY_API_ROOT).trim()) ||
      (window.CONFIG && window.CONFIG.API_BASE_URL) ||
      (window.Config && window.Config.apiBaseUrl) ||
      'http://127.0.0.1:9000';
    raw = String(raw || '')
      .trim()
      .replace(/\.+$/, '')
      .replace(/\/+$/, '');
    if (!raw) raw = 'http://127.0.0.1:9000';
    if (!/^https?:\/\//i.test(raw)) {
      raw = 'http://' + raw.replace(/^\/+/, '');
    }
    try {
      new URL(raw);
    } catch (e) {
      console.warn('[Auth] API_BASE_URL invalid, folosesc http://127.0.0.1:9000:', raw);
      raw = 'http://127.0.0.1:9000';
    }
    return raw.replace(/\/$/, '');
  }

  function abortSignalTimeout(ms) {
    try {
      if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout)
        return AbortSignal.timeout(ms);
    } catch (e) {}
    var c = new AbortController();
    setTimeout(function () { try { c.abort(); } catch (e2) {} }, ms);
    return c.signal;
  }

  /** Overlay fullscreen în mulberry.html în timpul login + sincronizare profil/vehicul. */
  function setMulberrySyncLoader(visible) {
    var el = document.getElementById('loader-wrapper');
    if (!el) return;
    if (visible) {
      el.classList.remove('hidden');
      el.setAttribute('aria-hidden', 'false');
    } else {
      el.classList.add('hidden');
      el.setAttribute('aria-hidden', 'true');
    }
  }

  /* ── LocalStorage helpers (fallback offline) ── */
  function getUsers() {
    try { return JSON.parse(localStorage.getItem(USERS_KEY) || '[]'); }
    catch (e) { return []; }
  }
  function saveUsers(arr) {
    try { localStorage.setItem(USERS_KEY, JSON.stringify(arr)); } catch (e) {}
  }
  function findUser(email) {
    var e = String(email || '').toLowerCase();
    return (
      getUsers().find(function (u) {
        return (
          (u.email || '').toLowerCase() === e ||
          (u.identifier || '').toLowerCase() === e
        );
      }) || null
    );
  }

  function jwtTabOnlyAuth() {
    try {
      return !!window.MULBERRY_TAB_SESSION_ONLY;
    } catch (e) {
      return false;
    }
  }

  /* ── Session helpers ── */
  function saveSession(user, jwtToken, role) {
    var token = jwtToken || ('local-' + Date.now() + '-' + Math.random().toString(36).slice(2));
    var session = {
      id: user.id || user.userId || ('local-' + Date.now()),
      email: user.email || user.identifier || '',
      identifier: user.email || user.identifier || '',
      name: user.name || (user.email || user.identifier || '').split('@')[0],
      role: role || user.role || 'user',
      access_token: token,
    };
    var j = JSON.stringify(session);
    var founder = session.role === 'founder' ? 'true' : 'false';
    try {
      if (jwtTabOnlyAuth()) {
        sessionStorage.setItem(SESSION_KEY, token);
        sessionStorage.setItem(TOKEN_KEY, token);
        sessionStorage.setItem('mulberry_current_session', j);
        sessionStorage.setItem('is_founder', founder);
        localStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem('mulberry_current_session');
        localStorage.removeItem('is_founder');
      } else {
        localStorage.setItem(SESSION_KEY, token);
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem('mulberry_current_session', j);
        localStorage.setItem('is_founder', founder);
        sessionStorage.removeItem(SESSION_KEY);
        sessionStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem('mulberry_current_session');
        sessionStorage.removeItem('is_founder');
      }
    } catch (e) {}
    if (window.AppDB) window.AppDB.currentUser = session;
    return session;
  }

  function clearSession() {
    try {
      [SESSION_KEY, TOKEN_KEY, 'mulberry_current_session', 'is_founder'].forEach(function (k) {
        try {
          localStorage.removeItem(k);
          sessionStorage.removeItem(k);
        } catch (e1) {}
      });
    } catch (e) {}
    if (window.AppDB) window.AppDB.currentUser = null;
  }

  function getCurrentSession() {
    try {
      var raw = null;
      if (jwtTabOnlyAuth()) raw = sessionStorage.getItem('mulberry_current_session') || localStorage.getItem('mulberry_current_session');
      else raw = localStorage.getItem('mulberry_current_session') || sessionStorage.getItem('mulberry_current_session');
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  /* ── UI helpers ── */
  function showErr(id, msg) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg || '';
    el.classList.toggle('show', !!msg);
  }
  function clearAllErrs() {
    ['si-err-email','si-err-pass','si-err-id','err-email','err-pass','err-pass2'].forEach(function(id){
      showErr(id, '');
    });
  }
  /** Stare buton login: opțional mod „Se verifică” cu puncte animate până la sfârșitul fluxului. */
  function setBtn(btn, disabled, text, loading) {
    if (!btn) return;
    btn.disabled = !!disabled;
    if (loading) {
      btn.classList.add('auth-btn-loading');
      btn.setAttribute('aria-busy', 'true');
      btn.innerHTML =
        'Se verifică<span class="auth-loading-dots" aria-hidden="true">' +
        '<span>.</span><span>.</span><span>.</span></span>';
    } else {
      btn.classList.remove('auth-btn-loading');
      btn.removeAttribute('aria-busy');
      btn.textContent = text != null ? text : 'Continuă';
    }
  }

  function goToDash() {
    if (typeof window.show === 'function') {
      if (typeof window.initDashboard === 'function') window.initDashboard();
      if (window.AppDB && window.AppDB.ui && window.AppDB.ui.syncDashboard)
        window.AppDB.ui.syncDashboard();
      if (typeof window.initMulberryNotifications === 'function')
        window.initMulberryNotifications();
      window.show('dash');
      if (typeof window.setNav === 'function') window.setNav('home');
    } else {
      window.location.href = 'mulberry.html';
    }
  }

  function hasVehicle(v) {
    return !!(v && (v.marca || v.nr || v.vin || v.plate));
  }

  function goToOnboardingOrAuth() {
    if (typeof window.goToOnboarding === 'function') window.goToOnboarding();
    else if (typeof window.show === 'function') window.show('auth');
  }

  /** După JWT: completează id numeric în sesiune (necesar pentru cheia mulberry_vehicle_<id>). */
  async function ensureSessionFromMe() {
    var token =
      (window.api && window.api.getToken && window.api.getToken()) ||
      localStorage.getItem(SESSION_KEY) ||
      localStorage.getItem(TOKEN_KEY) ||
      sessionStorage.getItem(SESSION_KEY) ||
      sessionStorage.getItem(TOKEN_KEY) ||
      '';
    if (!token || String(token).indexOf('eyJ') !== 0) return;
    if (!window.api || typeof window.api.me !== 'function') return;
    try {
      var me = await window.api.me();
      if (!me || me.id == null) return;
      saveSession(
        {
          id: String(me.id),
          identifier: me.identifier || '',
          email: me.identifier || '',
          name: (me.identifier || '').split('@')[0] || 'User',
        },
        token,
        me.role || 'user'
      );
    } catch (e) {
      console.warn('[Auth] ensureSessionFromMe:', (e && e.message) || e);
    }
  }

  /** Restaurează vehiculul din GET /me/vehicles în localStorage (AppDB). */
  async function restoreVehiclesFromBackend() {
    if (!window.api || typeof window.api.getVehicles !== 'function') return false;
    if (!window.AppDB || typeof window.AppDB.mergeVehicleFromServer !== 'function') return false;
    try {
      var vehicles = await window.api.getVehicles();
      if (!vehicles || !vehicles.length) return false;
      await window.AppDB.mergeVehicleFromServer(vehicles[0]);
      return true;
    } catch (e) {
      console.warn('[Auth] restoreVehiclesFromBackend:', (e && e.message) || e);
      return false;
    }
  }

  /* ════════════════════════════════════════════
     LOGIN — backend first, localStorage fallback
     ════════════════════════════════════════════ */
  window.submitSignIn = async function () {
    clearAllErrs();

    var emailEl = document.getElementById('si-id') || document.getElementById('si-email');
    var passEl  = document.getElementById('si-pass');
    if (!emailEl || !passEl) return;

    var email = emailEl.value.trim().toLowerCase();
    var pass  = passEl.value;

    if (!email) { showErr('si-err-id', 'Introdu emailul sau telefonul.'); return; }
    if (!pass || pass.length < 4) { showErr('si-err-pass', 'Introdu parola (minim 4 caractere).'); return; }

    /* Backdoor dev */
    if (email === 'admin@mulberry.dev' && pass === 'debug2026') {
      localStorage.setItem(SESSION_KEY, 'DEBUG_TOKEN_PROXIED');
      localStorage.setItem(TOKEN_KEY,   'DEBUG_TOKEN_PROXIED');
      localStorage.setItem('is_founder', 'true');
      window.location.href = 'dashboard.html';
      return;
    }

    var btn = document.querySelector('#s-login .btn-neon') || document.querySelector('#s-signin .btn-neon');
    setBtn(btn, true, null, true);
    setMulberrySyncLoader(true);

    try {
      /* ── 1. Încearcă backend FastAPI ── */
      var backendOk = false;
      try {
        var apiBase = apiResolveBase();
        var loginHeaders = { 'Content-Type': 'application/json' };
        try {
          if (window.MulberryDevice && window.MulberryDevice.headers) {
            var dh = window.MulberryDevice.headers();
            Object.keys(dh).forEach(function (k) {
              loginHeaders[k] = dh[k];
            });
          }
        } catch (eH) {}
        var res = await fetch(apiBase + AUTH_LOGIN_PATH, {
          method: 'POST',
          headers: loginHeaders,
          body: JSON.stringify({ identifier: email, password: pass }),
          signal: abortSignalTimeout(12000),
        });

        if (res.ok) {
          var data = await res.json();
          if (data && data.needs_phone) {
            showErr('si-err-pass', 'Introdu și numărul de telefon (Parola 2).');
            setBtn(btn, false, 'Continuă');
            return;
          }
          var jwt = data && data.access_token && String(data.access_token).trim();
          if (jwt && jwt.startsWith('eyJ')) {
            var userObj = { email: email, identifier: email, role: data.role || 'user' };
            saveSession(userObj, jwt, data.role || 'user');
            backendOk = true;
            console.log('[Auth] Login backend reușit. JWT salvat.');
          }
        } else {
          var errData = null;
          try { errData = await res.json(); } catch(e) {}
          var detail = (errData && errData.detail) ? errData.detail : ('Eroare ' + res.status);
          /* 401 de la backend = credentiale gresite, nu mai incercam local */
          if (res.status === 401) {
            showErr('si-err-pass', detail);
            setBtn(btn, false, 'Continuă');
            return;
          }
          console.warn('[Auth] Backend răspuns non-ok:', res.status, detail);
        }
      } catch (netErr) {
        console.warn('[Auth] Backend offline, încerc localStorage:', (netErr && netErr.message) || netErr);
        /* Animația butonului rămâne vizibilă minim ~800ms înainte de fallback-ul localStorage */
        await new Promise(function (resolve) { setTimeout(resolve, 800); });
      }

      /* ── 2. Fallback localStorage (backend offline) — login real, fără ERROR: BACKEND_OFFLINE dacă există cont local */
      if (!backendOk) {
        var userLocal = findUser(email);
        if (userLocal) {
          var hashL = await sha256(pass);
          if (hashL === userLocal.passwordHash) {
            saveSession(userLocal, null, userLocal.role);
            console.log('[Auth] Login local reușit (backend offline).');
            try {
              await ensureSessionFromMe();
              await restoreVehiclesFromBackend();
            } catch (e2) {
              console.warn('[Auth] post-login vehicle sync:', e2);
            }
            var vLoc = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
            if (hasVehicle(vLoc)) goToDash();
            else goToOnboardingOrAuth();
            return;
          }
          showErr('si-err-pass', 'Parolă incorectă.');
          setBtn(btn, false, 'Continuă');
          return;
        }
        showErr(
          'si-err-pass',
          '[!] SYNC_ERROR: CORE_DB_UNREACHABLE // START_LOCAL_ACCESS_MODE · Pornește uvicorn pe :9000 (vezi RUN_BACKEND.md) sau folosește cont local.'
        );
        setBtn(btn, false, 'Continuă');
        return;
      }

      try {
        if (window.api && typeof window.api.syncVehicleFromLocalStorage === 'function') {
          var syncOut = await window.api.syncVehicleFromLocalStorage();
          if (syncOut) console.log('[Auth] DATA_FIXED_IN_BACKEND', syncOut);
        }
      } catch (eSync) {
        console.warn('[Auth] cars/sync:', eSync);
      }

      try {
        await ensureSessionFromMe();
        await restoreVehiclesFromBackend();
      } catch (e2) {
        console.warn('[Auth] post-login vehicle sync:', e2);
      }
      var vAfter = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
      if (hasVehicle(vAfter)) goToDash();
      else goToOnboardingOrAuth();

    } catch (e) {
      console.error('[auth] submitSignIn error:', e);
      showErr('si-err-pass', 'Eroare internă. Încearcă din nou.');
    } finally {
      setMulberrySyncLoader(false);
      setBtn(btn, false, 'Continuă');
    }
  };

  /* ════════════════════════════════════════════
     REGISTER — backend first, localStorage fallback
     ════════════════════════════════════════════ */
  window.registerUser = async function (email, pass, extraData) {
    email = (email || '').trim().toLowerCase();
    if (!email) throw new Error('Email sau telefon invalid.');
    if (!pass || pass.length < 8) throw new Error('Parola trebuie să aibă minim 8 caractere.');

    /* ── 1. Încearcă backend ── */
    try {
      var apiBase = apiResolveBase();
      var regHeaders = { 'Content-Type': 'application/json' };
      try {
        if (window.MulberryDevice && window.MulberryDevice.headers) {
          var dh2 = window.MulberryDevice.headers();
          Object.keys(dh2).forEach(function (k) {
            regHeaders[k] = dh2[k];
          });
        }
      } catch (eH2) {}
      var res = await fetch(apiBase + AUTH_REGISTER_PATH, {
        method: 'POST',
        headers: regHeaders,
        body: JSON.stringify({ identifier: email, password: pass }),
        signal: abortSignalTimeout(12000),
      });
      if (res.ok) {
        var data = await res.json();
        var jwt  = data && data.access_token && String(data.access_token).trim();
        if (jwt && jwt.startsWith('eyJ')) {
          var userObj = { email: email, identifier: email, role: data.role || 'user' };
          saveSession(userObj, jwt, data.role || 'user');
          /* Salvăm și în localStorage ca fallback viitor */
          var hash = await sha256(pass);
          var localUser = Object.assign({
            id: 'local-' + Date.now(),
            email: email,
            identifier: email,
            passwordHash: hash,
            role: data.role || 'user',
            createdAt: new Date().toISOString(),
          }, extraData || {});
          var users = getUsers();
          if (!users.find(function (u) {
            return (u.email || '').toLowerCase() === email || (u.identifier || '').toLowerCase() === email;
          }))
            users.push(localUser);
          saveUsers(users);
          console.log('[Auth] Register backend reușit. JWT salvat.');
          return localUser;
        }
      } else {
        var errData = null;
        try { errData = await res.json(); } catch(e) {}
        var detail = (errData && errData.detail) ? errData.detail : ('Eroare ' + res.status);
        if (res.status === 409) throw new Error('Email deja înregistrat.');
        throw new Error(detail);
      }
    } catch (e) {
      if (e.message && (e.message.indexOf('deja') >= 0 || e.message.indexOf('409') >= 0))
        throw e;
      console.warn('[Auth] Register backend offline, folosesc localStorage:', e.message);
    }

    /* ── 2. Fallback localStorage ── */
    if (findUser(email)) throw new Error('Email deja înregistrat.');
    var hash = await sha256(pass);
    var user = Object.assign({
      id: 'local-' + Date.now(),
      email: email,
      identifier: email,
      passwordHash: hash,
      role: 'user',
      createdAt: new Date().toISOString(),
    }, extraData || {});
    var users = getUsers();
    users.push(user);
    saveUsers(users);
    saveSession(user, null, 'user');
    console.log('[Auth] Register local (offline) reușit.');
    return user;
  };

  /* ── Alte funcții publice ── */
  window.submitSignInStep2 = async function () {
    var session = getCurrentSession();
    if (!session) { if (typeof window.show === 'function') window.show('login'); return; }
    var btn2 = document.querySelector('#login-step2 .btn-neon');
    if (btn2) setBtn(btn2, true, null, true);
    setMulberrySyncLoader(true);
    try {
      await ensureSessionFromMe();
      await restoreVehiclesFromBackend();
    } catch (e) {
      console.warn('[Auth] submitSignInStep2 vehicle sync:', e);
    } finally {
      setMulberrySyncLoader(false);
      if (btn2) setBtn(btn2, false, 'Conectare');
    }
    var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
    if (hasVehicle(v)) goToDash();
    else goToOnboardingOrAuth();
  };

  window.showLoginStep1 = function () {
    var s1 = document.getElementById('login-step1');
    var s2 = document.getElementById('login-step2');
    if (s1) s1.style.display = '';
    if (s2) s2.style.display = 'none';
  };

  window.confirmSignOut = function () {
    if (!confirm('Ești sigur că vrei să te deconectezi?')) return;
    clearSession();
    if (typeof window.show === 'function') window.show('login');
    else window.location.href = 'mulberry.html';
  };

  /* ── Boot DOMContentLoaded ── */
  document.addEventListener('DOMContentLoaded', function () {
    if (window.__mulberry_auth_booted) return;
    window.__mulberry_auth_booted = true;

    /* mulberry.html are bootstrap inline (api.me + getVehicles); evităm cursă dublă */
    if (document.documentElement && document.documentElement.getAttribute('data-mulberry-bootstrap') === '1') {
      return;
    }

    var token =
      (window.api && window.api.getToken && window.api.getToken()) ||
      localStorage.getItem(SESSION_KEY) ||
      localStorage.getItem(TOKEN_KEY) ||
      sessionStorage.getItem(SESSION_KEY) ||
      sessionStorage.getItem(TOKEN_KEY) ||
      '';
    var session = getCurrentSession();

    if (!token) {
      if (typeof window.show === 'function') window.show('login');
      return;
    }
    if (!session) return;

    if (window.AppDB) window.AppDB.currentUser = session;

    (async function () {
      try {
        await ensureSessionFromMe();
        await restoreVehiclesFromBackend();
      } catch (e) {
        console.warn('[Auth] boot vehicle sync:', e);
      }
      var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
      if (hasVehicle(v)) {
        if (window.AppDB && window.AppDB.ui && window.AppDB.ui.syncDashboard)
          window.AppDB.ui.syncDashboard();
        if (typeof window.initMulberryNotifications === 'function')
          window.initMulberryNotifications();
        if (typeof window.show === 'function') {
          window.show('dash');
          if (typeof window.setNav === 'function') window.setNav('home');
        }
      } else {
        goToOnboardingOrAuth();
      }
    })();
  });

  window.__mulberry_auth = {
    getUsers: getUsers, findUser: findUser,
    getCurrentSession: getCurrentSession, clearSession: clearSession,
  };
})();
