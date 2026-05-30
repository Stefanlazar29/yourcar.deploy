/* api_client.js — toate fetch-urile către FastAPI
 * Retry + exponential backoff (rețea / timeout / 5xx) prin fetchWithBackoff;
 * window.API (GET/POST/PUT/DELETE/authenticatedRequest) pentru apeluri noi. */

(function() {
  var DEFAULT_API = 'http://127.0.0.1:9000';

  function jwtTabOnly() {
    try {
      return !!window.MULBERRY_TAB_SESSION_ONLY;
    } catch (e) {
      return false;
    }
  }

  function jwtReadKey(key) {
    try {
      if (jwtTabOnly()) {
        var s = sessionStorage.getItem(key);
        if (s) return s;
        return localStorage.getItem(key) || '';
      }
      var l = localStorage.getItem(key);
      if (l) return l;
      return sessionStorage.getItem(key) || '';
    } catch (e) {
      return '';
    }
  }

  function jwtWriteKey(key, val) {
    try {
      if (jwtTabOnly()) {
        if (val) sessionStorage.setItem(key, String(val).trim());
        else sessionStorage.removeItem(key);
        localStorage.removeItem(key);
      } else {
        if (val) localStorage.setItem(key, String(val).trim());
        else localStorage.removeItem(key);
      }
    } catch (e) {}
  }

  function jwtClearAll() {
    ['mulberry_session', 'yourcar_token'].forEach(function (k) {
      try {
        localStorage.removeItem(k);
        sessionStorage.removeItem(k);
      } catch (e) {}
    });
  }

  (function clearInvalidTokenOnLoad() {
    try {
      var ms = jwtReadKey('mulberry_session');
      var yt = jwtReadKey('yourcar_token');
      var bad = function(v) {
        if (!v || typeof v !== 'string') return true;
        var s = v.trim();
        if (s === 'DEBUG_TOKEN_PROXIED') return false;
        if (s.indexOf('local-') === 0 && s.length >= 20) return false;
        return s === 'String' || s === 'undefined' || s === 'null' || s.length < 20;
      };
      if (bad(ms) || bad(yt)) jwtClearAll();
    } catch (e) {}
  })();

  function ephemeralDeviceId() {
    try {
      var k = 'mulberry_device_ephemeral_v1';
      var s = sessionStorage.getItem(k);
      if (s && String(s).length >= 16) return String(s);
      s = 'mdev_sess_' + Math.random().toString(36).slice(2, 14) + '_' + Date.now().toString(36);
      sessionStorage.setItem(k, s);
      return s;
    } catch (e) {
      return 'mdev_sess_' + String(Date.now());
    }
  }

  /** Hub: overlay BIOS la 403 (HWID / politică), fără redirect. */
  function tryHubSecurityHalt403(detailStr) {
    try {
      var h = String(window.location.href || '');
      if (h.indexOf('mulberry_menu') < 0) return;
      var root = document.getElementById('exo-security-halt');
      if (!root) return;
      var det = document.getElementById('exo-halt-detail');
      if (det) det.textContent = detailStr ? String(detailStr) : '';
      root.hidden = false;
      root.setAttribute('aria-hidden', 'false');
    } catch (e) {}
  }

  function mergeAuthDeviceHeaders(base) {
    var h = Object.assign({}, base || {});
    try {
      if (window.MulberryDevice && window.MulberryDevice.headers) {
        var d = window.MulberryDevice.headers();
        Object.keys(d).forEach(function (k) {
          if (d[k] != null && String(d[k]).trim().length) h[k] = d[k];
        });
      }
    } catch (e) {}
    var dev = h['X-Mulberry-Device-Id'];
    if (!dev || String(dev).trim().length < 8) {
      h['X-Mulberry-Device-Id'] = ephemeralDeviceId();
    }
    return h;
  }

  function apiBase() {
    var raw =
      (window.MULBERRY_API_ROOT && String(window.MULBERRY_API_ROOT).trim()) ||
      (window.CONFIG && window.CONFIG.API_BASE_URL) ||
      (window.Config && window.Config.apiBaseUrl) ||
      '';
    raw = String(raw)
      .trim()
      .replace(/\.+$/, '')
      .replace(/\/+$/, '');
    if (!raw || raw === 'undefined' || raw === 'null') return DEFAULT_API;
    if (!/^https?:\/\//i.test(raw)) {
      raw = 'http://' + String(raw).replace(/^\/+/, '');
    }
    try {
      new URL(raw);
    } catch (e) {
      console.warn('[api] API_BASE_URL invalid, folosesc', DEFAULT_API, raw);
      return DEFAULT_API;
    }
    return String(raw).replace(/\/+$/, '');
  }

  /**
   * URL final pentru fetch: root validat + cale cu slash inițial.
   * Evită new URL() pe valori goale și concatări gen "http://host:9000auth/login".
   */
  function buildApiUrl(pathOrAbsolute) {
    var root = apiBase();
    var p = pathOrAbsolute == null ? '' : String(pathOrAbsolute).trim();
    if (!p) return root;
    if (p.indexOf('http://') === 0 || p.indexOf('https://') === 0) {
      try {
        new URL(p);
        return p;
      } catch (err) {
        try {
          return new URL(p, root + '/').href;
        } catch (err2) {
          var tail = p.replace(/^https?:\/\/[^/?#]+/i, '') || '/';
          if (tail.charAt(0) !== '/') tail = '/' + tail;
          return root + tail;
        }
      }
    }
    if (p.charAt(0) !== '/') p = '/' + p;
    return root + p;
  }

  function getToken() {
    try {
      var t = jwtReadKey('mulberry_session') || jwtReadKey('yourcar_token') || '';
      if (!t) {
        var sess = null;
        try {
          if (jwtTabOnly()) sess = sessionStorage.getItem('mulberry_current_session') || localStorage.getItem('mulberry_current_session');
          else sess = localStorage.getItem('mulberry_current_session') || sessionStorage.getItem('mulberry_current_session');
        } catch (e0) {
          sess = localStorage.getItem('mulberry_current_session');
        }
        if (sess) {
          try {
            var obj = JSON.parse(sess);
            if (obj && obj.access_token && isValidToken(obj.access_token)) t = obj.access_token;
          } catch (e) {}
        }
      }
      if (t && !isValidToken(t)) {
        jwtClearAll();
        return '';
      }
      return t ? String(t).trim() : '';
    } catch (e) { return ''; }
  }

  function isValidToken(val) {
    var s = (val && typeof val === 'string') ? String(val).trim() : '';
    if (!s) return false;
    if (s === 'DEBUG_TOKEN_PROXIED') return true;
    if (s.indexOf('local-') === 0 && s.length >= 20) return true;
    if (s.length < 20) return false;
    if (s === 'String' || s === 'undefined' || s === 'null') return false;
    if (s.indexOf('eyJ') === 0) return true;
    return s.length > 30;
  }

  function setToken(token) {
    try {
      if (token && isValidToken(token)) {
        var t = String(token).trim();
        jwtWriteKey('mulberry_session', t);
        jwtWriteKey('yourcar_token', t);
      } else {
        jwtWriteKey('mulberry_session', '');
        jwtWriteKey('yourcar_token', '');
      }
    } catch (e) {}
  }

  function setSession(token, role) {
    try {
      if (token && isValidToken(token)) {
        var t = String(token).trim();
        jwtWriteKey('mulberry_session', t);
        jwtWriteKey('yourcar_token', t);
      }
      var f = role === 'founder' ? 'true' : 'false';
      try {
        if (jwtTabOnly()) {
          sessionStorage.setItem('is_founder', f);
          localStorage.removeItem('is_founder');
        } else {
          localStorage.setItem('is_founder', f);
          sessionStorage.removeItem('is_founder');
        }
      } catch (e2) {}
    } catch (e) {}
  }

  function isFounder() {
    try {
      if (jwtTabOnly()) {
        var sf = sessionStorage.getItem('is_founder');
        if (sf === 'true' || sf === 'false') return sf === 'true';
      }
      return localStorage.getItem('is_founder') === 'true';
    } catch (e) {
      return false;
    }
  }

  function notifyBackendDown(err) {
    var msg = (err && err.message) ? String(err.message) : '';
    if (msg.indexOf('Failed to fetch') >= 0 || msg.indexOf('NetworkError') >= 0 || msg.indexOf('CONNECTION_REFUSED') >= 0) {
      msg = '[!] SYNC_ERROR: CORE_DB_UNREACHABLE // START_LOCAL_ACCESS_MODE · http://127.0.0.1:9000/health';
    }
    try {
      if (typeof window.showToast === 'function') window.showToast(msg);
    } catch (e) {}
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function mergeApiConfig(retryConfig) {
    var g = window.API_CONFIG || {};
    var rc = retryConfig || {};
    return {
      maxRetries: rc.maxRetries != null ? rc.maxRetries : (g.MAX_RETRIES != null ? g.MAX_RETRIES : 3),
      backoffBase: rc.backoffBase != null ? rc.backoffBase : (g.BACKOFF_BASE != null ? g.BACKOFF_BASE : 1000),
      backoffMax: rc.backoffMax != null ? rc.backoffMax : (g.BACKOFF_MAX != null ? g.BACKOFF_MAX : 10000),
      timeout: rc.timeout != null ? rc.timeout : (g.TIMEOUT != null ? g.TIMEOUT : 10000),
      retryOn: rc.retryOn != null ? rc.retryOn : (g.RETRY_ON != null ? g.RETRY_ON : [408, 429, 500, 502, 503, 504]),
      logPrefix: rc.logPrefix != null ? rc.logPrefix : '[API]'
    };
  }

  /**
   * Fetch cu timeout, retry pe erori de rețea / timeout și pe status-uri din retryOn (5xx etc.).
   * Nu reîncearcă la 4xx (inclusiv 401) — returnează Response-ul.
   * @param {string} endpoint - cale relativă la API (ex. "/me") sau URL absolut
   * @param {RequestInit} [options]
   * @param {object} [retryConfig]
   * @returns {Promise<Response>}
   */
  async function fetchWithBackoff(endpoint, options, retryConfig) {
    var cfg = mergeApiConfig(retryConfig);
    var url = buildApiUrl(endpoint);
    var lastError;
    var attempt;

    for (attempt = 0; attempt <= cfg.maxRetries; attempt++) {
      var controller = null;
      var timeoutId = null;
      var opts = Object.assign({}, options || {});
      try {
        if (!opts.signal) {
          controller = new AbortController();
          opts.signal = controller.signal;
          timeoutId = setTimeout(function () {
            try {
              controller.abort();
            } catch (e) {}
          }, cfg.timeout);
        }

        var response = await fetch(url, opts);

        if (timeoutId) clearTimeout(timeoutId);

        if (response.ok || (response.status >= 400 && response.status < 500)) {
          if (attempt > 0) {
            console.log(cfg.logPrefix + ' Success after ' + attempt + ' retries:', endpoint);
          }
          return response;
        }

        if (cfg.retryOn.indexOf(response.status) >= 0) {
          lastError = new Error('HTTP ' + response.status + ': ' + (response.statusText || ''));
          if (attempt < cfg.maxRetries) {
            var delay1 = Math.min(cfg.backoffBase * Math.pow(2, attempt), cfg.backoffMax);
            console.warn(
              cfg.logPrefix + ' ' + endpoint + ' failed (' + response.status + '). Retry ' +
                (attempt + 1) + '/' + cfg.maxRetries + ' in ' + delay1 + 'ms'
            );
            await sleep(delay1);
            continue;
          }
        }

        return response;
      } catch (error) {
        if (timeoutId) clearTimeout(timeoutId);
        lastError = error;
        if (attempt < cfg.maxRetries) {
          var delay2 = Math.min(cfg.backoffBase * Math.pow(2, attempt), cfg.backoffMax);
          var errorType = error && error.name === 'AbortError' ? 'Timeout' : 'Network error';
          console.warn(
            cfg.logPrefix + ' ' + endpoint + ' ' + errorType + '. Retry ' +
              (attempt + 1) + '/' + cfg.maxRetries + ' in ' + delay2 + 'ms'
          );
          await sleep(delay2);
          continue;
        }
      }
    }

    console.error(cfg.logPrefix + ' ' + endpoint + ' failed after ' + cfg.maxRetries + ' retries:', lastError);
    throw lastError || new Error('Request failed');
  }

  window.API_CONFIG = Object.assign(
    {
      TIMEOUT: 10000,
      MAX_RETRIES: 3,
      BACKOFF_BASE: 1000,
      BACKOFF_MAX: 10000,
      RETRY_ON: [408, 429, 500, 502, 503, 504]
    },
    window.API_CONFIG || {}
  );

  var API = {
    get: async function (endpoint, retryConfig) {
      var response = await fetchWithBackoff(
        endpoint,
        { method: 'GET' },
        Object.assign({ logPrefix: '[API GET]' }, retryConfig || {})
      );
      if (!response.ok) {
        throw new Error('GET ' + endpoint + ' failed: ' + response.status);
      }
      return response.json();
    },
    post: async function (endpoint, data, retryConfig) {
      var response = await fetchWithBackoff(
        endpoint,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data != null ? data : {})
        },
        Object.assign({ logPrefix: '[API POST]' }, retryConfig || {})
      );
      if (!response.ok) {
        throw new Error('POST ' + endpoint + ' failed: ' + response.status);
      }
      return response.json();
    },
    put: async function (endpoint, data, retryConfig) {
      var response = await fetchWithBackoff(
        endpoint,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data != null ? data : {})
        },
        Object.assign({ logPrefix: '[API PUT]' }, retryConfig || {})
      );
      if (!response.ok) {
        throw new Error('PUT ' + endpoint + ' failed: ' + response.status);
      }
      return response.json();
    },
    delete: async function (endpoint, retryConfig) {
      var response = await fetchWithBackoff(
        endpoint,
        { method: 'DELETE' },
        Object.assign({ logPrefix: '[API DELETE]' }, retryConfig || {})
      );
      if (!response.ok) {
        throw new Error('DELETE ' + endpoint + ' failed: ' + response.status);
      }
      return response.json();
    },
    /**
     * Cerere autentificată (Bearer din getToken — mulberry_session / yourcar_token).
     * La 401 golește token-urile Mulberry (nu auth_token generic).
     */
    authenticatedRequest: async function (endpoint, options, retryConfig) {
      var token = getToken();
      if (!token) {
        console.warn('[API] No auth token (mulberry_session / yourcar_token)');
        throw new Error('Authentication required');
      }
      var opt = Object.assign({}, options || {});
      var headers = Object.assign({ Authorization: 'Bearer ' + String(token).trim() }, opt.headers || {});
      opt.headers = headers;
      var response = await fetchWithBackoff(
        endpoint,
        opt,
        Object.assign({ logPrefix: '[API AUTH]' }, retryConfig || {})
      );
      if (response.status === 401) {
        console.warn('[API] Token invalid/expired — clearing session');
        jwtClearAll();
        throw new Error('Authentication failed - token invalid');
      }
      return response;
    }
  };

  window.API = API;
  window.fetchWithBackoff = fetchWithBackoff;

  /**
   * @param {string} path - ex. "/me"
   * @param {RequestInit} [opts]
   * @param {object} [retryConfig] - merge în fetchWithBackoff (ex. { maxRetries: 0, timeout: 3000 })
   */
  /**
   * Refactor cod via POST /system/utils/clean-code (JWT + Fondator). Timeout mare (LLM).
   */
  async function cleanCodeSnippet(code, includeRequirements) {
    return await apiFetch(
      '/system/utils/clean-code',
      {
        method: 'POST',
        body: JSON.stringify({
          code: code != null ? String(code) : '',
          include_requirements: !!includeRequirements,
        }),
      },
      {
        timeout: 120000,
        maxRetries: 0,
        logPrefix: '[API·clean-code]',
      }
    );
  }

  async function apiFetch(path, opts, retryConfig) {
    var base = apiBase();
    var token = getToken();
    // Dev backdoor: fără apel real la API pentru rute critice UI
    try {
      var rawTok = (function() {
        try {
          return String(localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '').trim();
        } catch (e) { return ''; }
      })();
      if (rawTok === 'DEBUG_TOKEN_PROXIED') {
        if (path === '/me' || path.indexOf('/me?') === 0) {
          return { id: 0, identifier: 'admin@mulberry.dev', role: 'founder' };
        }
        if (path === '/me/vehicles' || path.indexOf('/me/vehicles?') === 0) {
          return { vehicles: [] };
        }
      }
      if (rawTok.indexOf('local-') === 0) {
        var pathOnly = path.split('?')[0];
        if (pathOnly === '/me') {
          try {
            var rawSess = null;
            try {
              if (jwtTabOnly()) rawSess = sessionStorage.getItem('mulberry_current_session') || localStorage.getItem('mulberry_current_session');
              else rawSess = localStorage.getItem('mulberry_current_session') || sessionStorage.getItem('mulberry_current_session');
            } catch (eS) {
              rawSess = localStorage.getItem('mulberry_current_session');
            }
            if (rawSess) {
              var o = JSON.parse(rawSess);
              var nid = o.id;
              if (typeof nid === 'string' && /^\d+$/.test(nid)) nid = parseInt(nid, 10);
              else if (typeof nid !== 'number') nid = 0;
              return {
                id: nid,
                identifier: o.identifier || o.email || '',
                role: o.role || 'user',
              };
            }
          } catch (e2) {}
          return { id: 0, identifier: '', role: 'user' };
        }
        if (pathOnly === '/me/vehicles') {
          return { vehicles: [] };
        }
      }
    } catch (e) {}
    var base = apiBase();
    var headers = (opts && opts.headers) ? opts.headers : {};
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    if (token) {
      headers['Authorization'] = 'Bearer ' + String(token).trim();
      headers = mergeAuthDeviceHeaders(headers);
    } else {
      console.warn('[api] Niciun token in localStorage (mulberry_session/yourcar_token). Cererea poate primi 401.');
    }
    var url = buildApiUrl(path);
    var res;
    try {
      res = await fetchWithBackoff(
        url,
        Object.assign({}, opts || {}, { headers: headers }),
        Object.assign(
          {
            maxRetries: 3,
            logPrefix: '[apiFetch]',
            retryOn: [408, 429, 500, 502, 503, 504]
          },
          retryConfig || {}
        )
      );
    } catch (netErr) {
      notifyBackendDown(netErr);
      throw new Error('[!] SYNC_ERROR: CORE_DB_UNREACHABLE // START_LOCAL_ACCESS_MODE');
    }
    var text = await res.text();
    var data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
    if (!res.ok) {
      var msg = (data && data.detail) ? data.detail : ('Eroare API (' + res.status + ')');
      var msgStr = typeof msg === 'string' ? msg : JSON.stringify(msg);
      // 403 (politică dispozitiv / fondator / VIN): nu curățăm JWT și nu apelăm redirect 401.
      if (res.status === 403) {
        try {
          var href403 = String(window.location.href || '');
          if (href403.indexOf('mulberry_menu') >= 0) {
            tryHubSecurityHalt403(msgStr);
            console.error(
              '[!] SECURITY_HALT: HWID_MISMATCH // ACCESS_RESTRICTED — vezi POST /auth/device/approve sau MULBERRY_SINGLE_DEVICE=0 în dev.'
            );
          } else if (href403.indexOf('mulberry.html') < 0) {
            console.error(
              '[!] HWID_MISMATCH: Verifică amprenta digitală (X-Mulberry-Device-Id) înainte de logout; vezi POST /auth/device/approve sau MULBERRY_SINGLE_DEVICE=0 în dev.'
            );
            var t403 = msgStr;
            if (t403.length > 180) t403 = t403.slice(0, 177) + '…';
            if (typeof window.showToast === 'function') window.showToast(t403);
          }
        } catch (e403) {}
      } else if (res.status === 401) {
        try {
          fetch(base + '/log-error', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msgStr, status: 401, url: url, detail: (data && data.detail) ? String(data.detail) : null }),
          }).catch(function() {});
        } catch (e) {}
        // Token JWT expirat / invalid — un singur redirect (guard în AppDB)
        try {
          var jwtSent = token && String(token).trim().indexOf('eyJ') === 0;
          if (jwtSent && typeof window.__appdb_handle401 === 'function') {
            window.__appdb_handle401();
          }
        } catch (e2) {}
      }
      var apiErr = new Error(msgStr);
      apiErr.httpStatus = res.status;
      throw apiErr;
    }
    return data;
  }

  async function loginFromInputs() {
    var idEl = document.getElementById('si-id');
    var passEl = document.getElementById('si-pass');
    var identifier = (idEl && idEl.value.trim()) || '';
    var password = (passEl && passEl.value) || '';
    return await login(identifier, password);
  }

  async function registerFromInputs() {
    var idEl = document.getElementById('si-id');
    var passEl = document.getElementById('si-pass');
    var identifier = (idEl && idEl.value.trim()) || '';
    var password = (passEl && passEl.value) || '';
    return await register(identifier, password);
  }

  function saveTokenFromResponse(out) {
    if (!out) return;
    if (out.needs_phone) return;
    var raw = out.access_token;
    if (raw && typeof raw === 'string' && raw.trim().startsWith('eyJ')) {
      var t = raw.trim();
      setSession(t, out.role || 'user');
      console.log('[api] Token JWT salvat (eyJ…, len=' + t.length + ')');
      return;
    }
    console.error('Eroare: Serverul nu a trimis un token valid (așteptat JWT eyJ…)!');
  }

  /** Login fără Bearer pe cerere — imun la token-uri „String” / gunoi din localStorage. */
  async function login(identifier, password, phoneNumber) {
    try {
      var ident = String(identifier || '').trim();
      if (ident.indexOf('@') >= 0) ident = ident.toLowerCase();
      var body = { identifier: ident, password: password };
      if (phoneNumber && phoneNumber.trim()) body.phone_number = phoneNumber.trim();

      var response = await fetchWithBackoff(
        '/auth/login',
        {
          method: 'POST',
          headers: mergeAuthDeviceHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(body)
        },
        {
          maxRetries: 1,
          retryOn: [500, 502, 503, 504],
          logPrefix: '[Auth·Login]',
          timeout: 15000
        }
      );
      var text = await response.text();
      var data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch (e) {
        data = text;
      }
      if (!response.ok) {
        var detail =
          typeof data === 'object' && data && data.detail != null
            ? data.detail
            : 'Login eșuat (' + response.status + ')';
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
      if (data && data.needs_phone) return data;
      var tok = data && data.access_token;
      if (tok && typeof tok === 'string' && tok.trim().startsWith('eyJ')) {
        setSession(tok.trim(), data.role || 'user');
        console.log('[Auth] Login reușit. Token salvat.');
        return data;
      }
      throw new Error('Serverul a trimis un format de token invalid');
    } catch (err) {
      notifyBackendDown(err);
      console.error('[Auth Error]', err && err.message);
      try {
        if (typeof window.logErrorToExo === 'function') {
          window.logErrorToExo(String((err && err.message) || err), 'auth_login');
        }
      } catch (e) {}
      throw err;
    }
  }

  /** Contract simplu email+parolă → același backend `identifier` (FastAPI). */
  async function loginUser(email, password) {
    try {
      var out = await login(String(email || '').toLowerCase().trim(), password);
      return out;
    } catch (e) {
      return false;
    }
  }

  async function register(identifier, password, phoneNumber) {
    try {
      var ident = String(identifier || '').trim();
      if (ident.indexOf('@') >= 0) ident = ident.toLowerCase();
      var body = { identifier: ident, password: password };
      if (phoneNumber && phoneNumber.trim()) body.phone_number = phoneNumber.trim();

      var response = await fetchWithBackoff(
        '/auth/register',
        {
          method: 'POST',
          headers: mergeAuthDeviceHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(body)
        },
        {
          maxRetries: 1,
          retryOn: [500, 502, 503, 504],
          logPrefix: '[Auth·Register]',
          timeout: 15000
        }
      );
      var text = await response.text();
      var data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch (e) {
        data = text;
      }
      if (!response.ok) {
        var detail =
          typeof data === 'object' && data && data.detail != null
            ? data.detail
            : 'Înregistrare eșuată (' + response.status + ')';
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
      console.log('[api] Register response:', data);
      saveTokenFromResponse(data);
      return data;
    } catch (err) {
      notifyBackendDown(err);
      console.error('[Auth Error]', err && err.message);
      try {
        if (typeof window.logErrorToExo === 'function') {
          window.logErrorToExo(String((err && err.message) || err), 'auth_register');
        }
      } catch (e) {}
      throw err;
    }
  }

  /** Verificare identitate — timeout generos + 1 retry la Abort/rețea (evită bucla login). */
  async function me() {
    return await apiFetch(
      '/me',
      { method: 'GET' },
      { maxRetries: 1, timeout: 20000, logPrefix: '[apiFetch·/me]' }
    );
  }

  async function getVehicles() {
    var data = await apiFetch(
      '/me/vehicles',
      { method: 'GET' },
      { maxRetries: 0, timeout: 8000, logPrefix: '[apiFetch·/vehicles]' }
    );
    return (data && data.vehicles) ? data.vehicles : [];
  }

  async function upsertCar(payload) {
    return await apiFetch('/cars', { method: 'PUT', body: JSON.stringify({ payload: payload || {} }) });
  }

  /**
   * Împinge vehiculul din localStorage (mulberry_vehicle_*) către POST /cars/sync (JWT).
   */
  async function listSystemArchives() {
    return await apiFetch(
      '/system/archives',
      { method: 'GET' },
      { maxRetries: 0, timeout: 20000, logPrefix: '[apiFetch·/system/archives]' }
    );
  }

  async function generateDailyArchive() {
    return await apiFetch(
      '/system/archives/generate',
      { method: 'POST', body: '{}' },
      { maxRetries: 0, timeout: 120000, logPrefix: '[apiFetch·/archives/gen]' }
    );
  }

  async function downloadArchiveFile(relPath) {
    var token = getToken();
    if (!token || String(token).indexOf('eyJ') !== 0) throw new Error('JWT lipsă');
    var url =
      apiBase() +
      '/system/archives/download/' +
      String(relPath || '')
        .split('/')
        .map(function (s) {
          return encodeURIComponent(s);
        })
        .join('/');
    var r = await fetch(url, {
      method: 'GET',
      headers: { Authorization: 'Bearer ' + String(token).trim() },
    });
    if (!r.ok) throw new Error('Download ' + r.status);
    var blob = await r.blob();
    var name = String(relPath || 'archive.json').split('/').pop() || 'archive.json';
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(function () {
      try {
        URL.revokeObjectURL(a.href);
      } catch (e) {}
    }, 400);
  }

  async function syncVehicleFromLocalStorage() {
    var token = getToken();
    if (!token || String(token).indexOf('eyJ') !== 0) return null;
    var key = null;
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && k.indexOf('mulberry_vehicle_') === 0) {
        key = k;
        break;
      }
    }
    if (!key) return null;
    var raw = localStorage.getItem(key);
    if (!raw) return null;
    var vehicleData;
    try {
      vehicleData = JSON.parse(raw);
    } catch (e) {
      return null;
    }
    var vin = vehicleData && vehicleData.vin ? String(vehicleData.vin).trim().toUpperCase() : '';
    if (vin.length !== 17) return null;
    return await apiFetch(
      '/cars/sync',
      { method: 'POST', body: JSON.stringify(vehicleData) },
      { maxRetries: 0, timeout: 20000, logPrefix: '[apiFetch·/cars/sync]' }
    );
  }

  async function sendMessageToExo(message, includeErrorLog) {
    var body = { message: String(message || '').trim(), include_error_log: includeErrorLog !== false };
    return await apiFetch('/chat', { method: 'POST', body: JSON.stringify(body) });
  }

  /**
   * Simulare „streaming” în UI: completează elementul progresiv (fără SSE).
   * Folosește pentru răspunsuri assistant în dashboard / card mic.
   */
  function streamTypeText(element, fullText, opts) {
    return new Promise(function (resolve) {
      if (!element) {
        resolve();
        return;
      }
      opts = opts || {};
      var delay = opts.delayMs != null ? opts.delayMs : 12;
      var chunk = opts.chunk != null ? opts.chunk : 3;
      var text = String(fullText || '');
      var i = 0;
      element.textContent = '';
      function step() {
        if (i >= text.length) {
          resolve();
          return;
        }
        i = Math.min(i + chunk, text.length);
        element.textContent = text.slice(0, i);
        setTimeout(step, delay);
      }
      step();
    });
  }

  window.api = {
    apiFetch: apiFetch,
    fetchWithBackoff: fetchWithBackoff,
    login: login,
    loginUser: loginUser,
    register: register,
    setSession: setSession,
    isFounder: isFounder,
    loginFromInputs: loginFromInputs,
    registerFromInputs: registerFromInputs,
    me: me,
    getVehicles: getVehicles,
    upsertCar: upsertCar,
    syncVehicleFromLocalStorage: syncVehicleFromLocalStorage,
    listSystemArchives: listSystemArchives,
    generateDailyArchive: generateDailyArchive,
    downloadArchiveFile: downloadArchiveFile,
    sendMessageToExo: sendMessageToExo,
    streamTypeText: streamTypeText,
    getToken: getToken,
    setToken: setToken,
    cleanCodeSnippet: cleanCodeSnippet
  };

  try {
    console.log('[API Client] fetchWithBackoff + window.API ready (base:', apiBase() + ')');
  } catch (e) {}
})();

