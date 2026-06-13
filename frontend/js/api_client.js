/**
 * api_client.js — client HTTP centralizat pentru Mulberry.
 * Extinde window.api cu metode suplimentare.
 */
(function () {
  var base = function () {
    return (window.Config && window.Config.apiBaseUrl) || 'http://46.225.100.151:8080';
  };
  function token() {
    return localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '';
  }
  function headers(extra) {
    var h = Object.assign({ 'Content-Type': 'application/json' }, extra || {});
    var t = token();
    if (t) h['Authorization'] = 'Bearer ' + t;
    return h;
  }
  function req(method, path, body) {
    var opts = { method: method, headers: headers() };
    if (body) opts.body = JSON.stringify(body);
    return fetch(base() + path, opts).then(function (r) {
      if (!r.ok) return r.json().then(function (e) { throw new Error(e.detail || r.status); });
      return r.json();
    });
  }

  window.api = Object.assign(window.api || {}, {
    get:    function (path)       { return req('GET',    path); },
    post:   function (path, body) { return req('POST',   path, body); },
    put:    function (path, body) { return req('PUT',    path, body); },
    delete: function (path)       { return req('DELETE', path); },

    sessionProbe: function () { return req('GET', '/auth/session-probe'); },
    deviceApprove: function (code) { return req('POST', '/auth/device/approve', { code: code }); },
    getVehicles:   function () { return req('GET', '/me/cloud/list').catch(function () { return []; }); }
  });
})();
