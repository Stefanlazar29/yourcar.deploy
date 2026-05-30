/* config.js — Setări globale Mulberry */
/**
 * Frontend (Vercel, https://mulberry.autos) → Backend (Railway).
 * URL-ul de mai jos trebuie să fie EXACT cel din Railway (Settings → Networking → Public URL),
 * cu https:// și fără slash final — altfel: Mixed Content sau CORS greșit.
 *
 * Local: 127.0.0.1 / localhost → http://127.0.0.1:9000 (sau același origin pe :9000).
 * Override: ?api=https://alt-backend.example (doar http/https).
 *
 * Test backend: (Railway public URL)/api/health
 */
/** Global imediat — primul lucru util; mulberry.html: onclick pe ochiul parolei */
window.togglePassVis = function (id, btn) {
  var input = (id && document.getElementById(id)) || (btn && btn.previousElementSibling);
  if (!input || typeof input.type !== 'string') return;
  input.type = input.type === 'password' ? 'text' : 'password';
  if (btn && btn.style) btn.style.opacity = input.type === 'password' ? '0.5' : '1';
};

/**
 * Înlocuiește cu URL-ul real din Railway (ex. mulberry-production-xxxx.up.railway.app).
 * Nu folosi http:// aici pe producție — browserul blochează Mixed Content de pe https://mulberry.autos.
 */
const API_BASE_URL = 'https://mulberry-production-d9db.up.railway.app'.replace(/\/+$/, '');

var MULBERRY_API_LOCAL = 'http://127.0.0.1:9000';
var MULBERRY_API_PRODUCTION = API_BASE_URL;

/** Live Server „Go Live” pe IP LAN: același host, port Uvicorn 9000 (nu Railway). */
function _isPrivateLanHost(host) {
  if (!host) return false;
  host = String(host).toLowerCase();
  if (/^192\.168\.\d{1,3}\.\d{1,3}$/.test(host)) return true;
  if (/^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host)) return true;
  var m = host.match(/^172\.(\d{1,3})\./);
  if (m) {
    var n = parseInt(m[1], 10);
    if (n >= 16 && n <= 31) return true;
  }
  return false;
}

function resolveMulberryApiBase() {
  try {
    var l = window.location;
    if (!l) return MULBERRY_API_LOCAL;

    var qp;
    try {
      qp = new URLSearchParams(l.search || '');
    } catch (e0) {
      qp = null;
    }
    if (qp) {
      var forced = (qp.get('api') || '').replace(/\/+$/, '');
      if (forced && /^https?:\/\//i.test(forced)) {
        return forced;
      }
    }

    if (l.protocol === 'file:') return MULBERRY_API_LOCAL;

    var host = (l.hostname || '').toLowerCase();
    var isLocal =
      host === '127.0.0.1' ||
      host === 'localhost' ||
      host === '[::1]' ||
      host === '0.0.0.0';

    if (isLocal) {
      var port = l.port || (l.protocol === 'https:' ? '443' : l.protocol === 'http:' ? '80' : '');
      if (String(port) === '9000' && l.origin && l.origin !== 'null') {
        return String(l.origin).replace(/\/+$/, '');
      }
      return MULBERRY_API_LOCAL;
    }

    if (_isPrivateLanHost(host)) {
      return ('http://' + host + ':9000').replace(/\/+$/, '');
    }

    // Producție (mulberry.autos pe Vercel): backend pe Railway
    if (host === 'mulberry.autos' || host === 'www.mulberry.autos') {
      return MULBERRY_API_PRODUCTION;
    }
    
    // Alte domenii (preview Vercel, etc.): încearcă same-origin, fallback Railway
    if (l.origin && l.origin !== 'null') {
      return String(l.origin).replace(/\/+$/, '');
    }
    return MULBERRY_API_PRODUCTION;
  } catch (e) {
    return MULBERRY_API_LOCAL;
  }
}

var MULBERRY_API_BASE = resolveMulberryApiBase();

window.Config = {
  appName: 'Mulberry',
  apiBaseUrl: MULBERRY_API_BASE,
  API_BASE_URL: MULBERRY_API_BASE,
  storageKey: 'mulberry_v1_db',
  mlbrPublicBase: MULBERRY_API_BASE,
  mlbrFilePath: 'mlbr_file.html',
  /** QR dashboard / orice telefon — prezentare din baza MLBR publică */
  mlbrScanPage: 'vehicle_present.html',
};

window.CONFIG = window.Config;
window.API_BASE = MULBERRY_API_BASE;
window.API_BASE_URL = MULBERRY_API_BASE;

/**
 * Miniatură QR: tap / Enter deschide profilul public (vehicle_present) în tab nou.
 */
window.mulberryBindQrTapOpen = function (wrap, url) {
  if (!wrap) return;
  var u = (url && String(url).trim()) || '';
  if (!/^https?:\/\//i.test(u)) {
    wrap.classList.remove('mulberry-qr-tap-open');
    wrap.removeAttribute('role');
    wrap.removeAttribute('tabindex');
    wrap.removeAttribute('title');
    if (wrap.style) wrap.style.cursor = '';
    wrap.onclick = null;
    wrap.onkeydown = null;
    return;
  }
  wrap.classList.add('mulberry-qr-tap-open');
  wrap.setAttribute('role', 'button');
  wrap.setAttribute('tabindex', '0');
  wrap.setAttribute('title', 'Deschide profilul public al vehiculului');
  wrap.style.cursor = 'pointer';
  function go(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    window.open(u, '_blank', 'noopener,noreferrer');
  }
  wrap.onclick = go;
  wrap.onkeydown = function (ev) {
    if (ev.key === 'Enter' || ev.key === ' ') go(ev);
  };
};

if (typeof window.MULBERRY_WS_NOTIFICATIONS === 'undefined') {
  window.MULBERRY_WS_NOTIFICATIONS = false;
}
if (typeof window.MULBERRY_TAB_SESSION_ONLY === 'undefined') {
  window.MULBERRY_TAB_SESSION_ONLY = false;
}

document.addEventListener('DOMContentLoaded', function () {
  var titleEl = document.getElementById('app-title');
  if (titleEl) titleEl.textContent = window.Config.appName;
});
