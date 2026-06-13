/**
 * backend_bridge.js — sincronizare date AppDB ↔ server după login.
 */
(function () {
  window.addEventListener('mulberry:screen', function (e) {
    if (!e.detail || e.detail.screen !== 'dash') return;
    var token = localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token');
    if (!token || !window.api) return;

    /* Sincronizează utilizatorul curent */
    window.api.me().then(function (user) {
      if (window.AppDB) {
        window.AppDB.saveUser({
          id: user.id,
          email: user.email,
          name: (user.email || '').split('@')[0],
          role: user.role || 'user'
        });
        if (window.AppDB.ui && window.AppDB.ui.syncDashboard) {
          window.AppDB.ui.syncDashboard();
        }
      }
    }).catch(function () {});
  });
})();
