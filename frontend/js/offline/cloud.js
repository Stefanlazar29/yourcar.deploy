/**
 * cloud.js — upload și listare documente în cloud.
 */
(function () {
  var apiBase = function () {
    return (window.Config && window.Config.apiBaseUrl) || 'http://46.225.100.151:8080';
  };
  function authHeader() {
    var t = localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '';
    return t ? { 'Authorization': 'Bearer ' + t } : {};
  }

  window.MulberryCloud = {
    list: function (vin) {
      var url = apiBase() + (vin ? '/cloud/list?vin=' + encodeURIComponent(vin) : '/me/cloud/list');
      return fetch(url, { headers: authHeader() }).then(function (r) { return r.json(); }).catch(function () { return []; });
    },
    upload: function (docType, file) {
      var form = new FormData();
      form.append('file', file);
      return fetch(apiBase() + '/cloud/upload/v2/' + encodeURIComponent(docType), {
        method: 'POST',
        headers: authHeader(),
        body: form
      }).then(function (r) { return r.json(); });
    }
  };
})();
