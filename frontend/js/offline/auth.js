/**
 * Mulberry auth — implementează window.api și submitSignIn/submitSignInStep2.
 * Token stocat în localStorage ca 'mulberry_session'.
 * Backend: POST /auth/login → {token, email} | GET /me → {id, email}
 */
(function () {
  var apiBase = (window.Config && window.Config.apiBaseUrl) || 'http://46.225.100.151:8080';
  var TOKEN_KEY = 'mulberry_session';

  /* ── helpers UI ─────────────────────────────────────────── */
  function setErr(id, msg) {
    var el = document.getElementById(id);
    if (el) el.textContent = msg || '';
  }
  function clearErrs() {
    ['si-err-id', 'si-err-pass', 'si-err-phone'].forEach(function (id) { setErr(id, ''); });
  }
  function val(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }
  function showStep2(hint) {
    var s1 = document.getElementById('login-step1');
    var s2 = document.getElementById('login-step2');
    if (s1) s1.style.display = 'none';
    if (s2) s2.style.display = '';
    if (hint) {
      var h = document.getElementById('login-step2-hint');
      if (h) h.textContent = hint;
    }
  }

  /* ── token storage ──────────────────────────────────────── */
  function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem('yourcar_token', token);
  }
  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || localStorage.getItem('yourcar_token') || '';
  }
  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('yourcar_token');
  }

  /* ── API calls ──────────────────────────────────────────── */
  async function apiFetch(path, opts) {
    var token = getToken();
    var headers = Object.assign({ 'Content-Type': 'application/json' }, opts && opts.headers || {});
    if (token) headers['Authorization'] = 'Bearer ' + token;
    var res = await fetch(apiBase + path, Object.assign({}, opts, { headers: headers }));
    if (!res.ok) {
      var err = {};
      try { err = await res.json(); } catch (_) {}
      throw Object.assign(new Error(err.detail || 'Eroare ' + res.status), { status: res.status });
    }
    return res.json();
  }

  /* ── window.api ─────────────────────────────────────────── */
  window.api = {
    getToken: getToken,
    clearToken: clearToken,

    me: function () {
      return apiFetch('/me');
    },

    login: function (email, password) {
      return apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ identifier: email, password: password })
      });
    },

    getVehicles: function () {
      return apiFetch('/cloud/list').catch(function () { return []; });
    }
  };

  /* ── Step 1: email + parolă ─────────────────────────────── */
  window.submitSignIn = async function () {
    clearErrs();
    var email = val('si-id');
    var pass  = val('si-pass');

    if (!email) { setErr('si-err-id', 'Introdu adresa de email.'); return; }
    if (!pass)  { setErr('si-err-pass', 'Introdu parola.'); return; }

    var btn = document.querySelector('#login-step1 .btn-neon');
    if (btn) { btn.disabled = true; btn.textContent = 'Se conectează…'; }

    try {
      var data = await window.api.login(email, pass);
      saveToken(data.token);
      /* step 2 e opțional (cod telefon) — sărim direct la boot */
      if (typeof window.bootApp === 'function') {
        window.bootApp();
      } else if (typeof window.show === 'function') {
        window.show('dash');
      }
    } catch (err) {
      if (err.status === 401) {
        setErr('si-err-pass', 'Parolă incorectă.');
      } else if (err.message && err.message.toLowerCase().includes('fetch')) {
        setErr('si-err-pass', 'Backend offline — serverul nu răspunde.');
      } else {
        setErr('si-err-pass', err.message || 'Eroare necunoscută.');
      }
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Continuă'; }
    }
  };

  /* ── Step 2: cod telefon (secundar) ─────────────────────── */
  window.submitSignInStep2 = async function () {
    clearErrs();
    var phone = val('si-phone');
    if (!phone) { setErr('si-err-phone', 'Introdu numărul de telefon.'); return; }
    /* Cod telefon = al doilea factor vizual; tokenul există deja din step 1.
       Dacă backend-ul implementează verificare telefon, apelează-l aici.
       Deocamdată continuăm direct. */
    if (typeof window.bootApp === 'function') {
      window.bootApp();
    } else if (typeof window.show === 'function') {
      window.show('dash');
    }
  };

  /* ── logout global ──────────────────────────────────────── */
  window.logoutMulberry = function () {
    clearToken();
    if (typeof window.show === 'function') window.show('login');
  };

  /* ── Google OAuth callback handler ─────────────────────── */
  (function handleOAuthCallback() {
    var hash = window.location.hash;
    if (hash.includes('access_token=')) {
      var params = new URLSearchParams(hash.substring(1));
      var supabaseToken = params.get('access_token');
      if (supabaseToken) {
        fetch(apiBase + '/auth/google/exchange', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({access_token: supabaseToken})
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.access_token) {
            saveToken(data.access_token);
            history.replaceState(null, '', window.location.pathname);
            if (typeof window.bootApp === 'function') window.bootApp();
            else if (typeof window.show === 'function') window.show('dash');
          }
        })
        .catch(function(e) { console.error('Google exchange error:', e); });
      }
    }
  })();
})();
