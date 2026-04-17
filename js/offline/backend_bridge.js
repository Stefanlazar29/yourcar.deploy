/* offline/backend_bridge.js — trimitere generică către backend (LocalBase) */

(function() {
  window.trimiteLaServer = async function(provider) {
    try {
      await window.AppDB.insert('form_submit', { provider: provider || 'email' });
      window.AppDB.ui.goTo('yourcar_id.html');
    } catch (e) {
      window.showToast((e && e.message) ? e.message : 'Eroare la trimitere.');
    }
  };

  document.addEventListener('DOMContentLoaded', function() {
    var b1 = document.getElementById('btn-auth-email');
    if (b1) b1.addEventListener('click', function() { window.trimiteLaServer('email'); });
  });
})();

