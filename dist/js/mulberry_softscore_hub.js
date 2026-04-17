/**
 * SoftScore multi-factor — aceeași sursă ca Mulberry Hub (mulberry_exo_menu.js):
 * GET /me/vehicle/softscore/latest, POST /me/vehicle/softscore/refresh
 */
(function (global) {
  if (global.MulberrySoftScoreHub) return;

  var BOOT_KEY = 'mulberry_softscore_bootstrapped';

  function apiBase() {
    var b = (global.Config && global.Config.apiBaseUrl) || 'http://127.0.0.1:9000';
    return String(b || '').trim().replace(/\/+$/, '');
  }

  function getBearerHeaders() {
    var t = '';
    try {
      t =
        localStorage.getItem('mulberry_session') ||
        localStorage.getItem('yourcar_token') ||
        sessionStorage.getItem('mulberry_session') ||
        sessionStorage.getItem('yourcar_token') ||
        '';
    } catch (e) {}
    t = t != null ? String(t).trim() : '';
    if (!t || t.indexOf('eyJ') !== 0 || t.length < 51) return null;
    return { Authorization: 'Bearer ' + t };
  }

  function fetchLatest() {
    var h = getBearerHeaders();
    if (!h) return Promise.resolve(null);
    return fetch(apiBase() + '/me/vehicle/softscore/latest', { method: 'GET', headers: h })
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .catch(function () {
        return null;
      });
  }

  function postRefresh() {
    var h = getBearerHeaders();
    if (!h) return Promise.resolve(null);
    return fetch(apiBase() + '/me/vehicle/softscore/refresh', { method: 'POST', headers: h })
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .catch(function () {
        return null;
      });
  }

  /**
   * Aliniat la refreshSoftScoreGauge({ bootstrap }) din mulberry_exo_menu.js:
   * dacă latest e gol, o dată pe sesiune POST refresh.
   */
  function ensureLatestWithBootstrap(opts) {
    opts = opts || {};
    return fetchLatest().then(function (j) {
      if (j && j.softscore != null) return j;
      if (!opts.bootstrap) return j || null;
      var boot = '';
      try {
        boot = sessionStorage.getItem(BOOT_KEY) || '';
      } catch (e0) {}
      if (boot) return j || null;
      try {
        sessionStorage.setItem(BOOT_KEY, '1');
      } catch (e1) {}
      return postRefresh();
    });
  }

  /** Text scurt pentru UI — același mesaj ca banda de culoare din Hub. */
  function statusHintFromPayload(j) {
    if (!j || j.softscore == null) return '';
    var s = Number(j.softscore);
    if (s > 80) {
      return 'Profil favorabil pe uzură; valoarea estimată e apropiată de referință.';
    }
    if (s >= 50) {
      return 'Uzură obișnuită pentru vârstă și kilometraj.';
    }
    return 'Risc costuri mai mari — verificare tehnică și buget reparații recomandate.';
  }

  global.MulberrySoftScoreHub = {
    BOOT_KEY: BOOT_KEY,
    apiBase: apiBase,
    getBearerHeaders: getBearerHeaders,
    fetchLatest: fetchLatest,
    postRefresh: postRefresh,
    ensureLatestWithBootstrap: ensureLatestWithBootstrap,
    statusHintFromPayload: statusHintFromPayload,
  };
})(window);
