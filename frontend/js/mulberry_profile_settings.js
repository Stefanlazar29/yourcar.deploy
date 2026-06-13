/** mulberry_profile_settings.js — ecran setări profil utilizator. */
(function () {
  window.addEventListener('mulberry:screen', function (e) {
    if (!e.detail || e.detail.screen !== 'profile-settings') return;
    var user = window.AppDB ? window.AppDB.getUser() : null;
    var emailEl = document.getElementById('profile-email');
    if (emailEl && user) emailEl.textContent = user.email || '—';
  });

  window.logoutFromProfile = function () {
    if (window.api && typeof window.api.clearToken === 'function') window.api.clearToken();
    localStorage.removeItem('mulberry_session');
    localStorage.removeItem('yourcar_token');
    if (typeof window.show === 'function') window.show('login');
  };
})();
