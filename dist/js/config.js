/* config.js — Setări globale Mulberry */
/**
 * API: local vs producție după hostname (fără să cauți laptopul vizitatorilor pe mulberry.autos).
 *
 * Local (Cursor, Live Server, etc.): hostname 127.0.0.1 / localhost → backend http://127.0.0.1:9000
 *   (dacă pagina e servită direct de Uvicorn pe :9000, folosim același origin).
 *
 * Producție (ex. mulberry.autos): → https://mulberry-backend.up.railway.app
 *
 * Override manual: adaugă ?api=https://alt-backend.example/health la URL (doar http/https).
 *
 * Pornire locală:
 *   uvicorn backend.main:app --host 127.0.0.1 --port 9000 --reload
 *   browser: http://127.0.0.1:9000/
 */
/** Global imediat — primul lucru util; mulberry.html: onclick pe ochiul parolei */
window.togglePassVis = function (id, btn) {
  var input = (id && document.getElementById(id)) || (btn && btn.previousElementSibling);
  if (!input || typeof input.type !== 'string') return;
  input.type = input.type === 'password' ? 'text' : 'password';
  if (btn && btn.style) btn.style.opacity = input.type === 'password' ? '0.5' : '1';
};

var MULBERRY_API_LOCAL = 'http://127.0.0.1:9000';
/** Fără slash final — același string ca Public URL din Railway */
var MULBERRY_API_PRODUCTION = 'https://mulberry-backend.up.railway.app'.replace(/\/+$/, '');

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
