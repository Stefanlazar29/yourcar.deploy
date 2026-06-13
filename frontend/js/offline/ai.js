/** ai.js — wrapper asistent AI Mulberry. */
(function () {
  window.MulberryAI = {
    chat: function (message, threadId) {
      var apiBase = (window.Config && window.Config.apiBaseUrl) || 'http://46.225.100.151:8080';
      var token   = localStorage.getItem('mulberry_session') || '';
      return fetch(apiBase + '/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ message: message, thread_id: threadId || null })
      }).then(function (r) { return r.json(); });
    },
    report: function (vin) {
      var apiBase = (window.Config && window.Config.apiBaseUrl) || 'http://46.225.100.151:8080';
      var token   = localStorage.getItem('mulberry_session') || '';
      return fetch(apiBase + '/assistant/report?vin=' + encodeURIComponent(vin || ''), {
        headers: { 'Authorization': 'Bearer ' + token }
      }).then(function (r) { return r.json(); });
    }
  };
})();
