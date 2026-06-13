/**
 * core.js — navigare ecrane, bootApp, utilități globale.
 * Ecrane: s-login, s-auth, s-dash, s-profile-settings
 */
(function () {
  /* ── show(screenId) ─────────────────────────────────────── */
  window.show = function (name) {
    var id = name.startsWith('s-') ? name : 's-' + name;
    document.querySelectorAll('.screen').forEach(function (el) {
      el.classList.toggle('active', el.id === id);
    });
    window.dispatchEvent(new CustomEvent('mulberry:screen', { detail: { screen: name } }));
  };

  /* ── bootApp — apelat după login reușit ─────────────────── */
  window.bootApp = function () {
    var token = localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '';
    if (!token) { window.show('login'); return; }

    if (window.AppDB && window.AppDB.ui && typeof window.AppDB.ui.syncDashboard === 'function') {
      try { window.AppDB.ui.syncDashboard(); } catch (e) {}
    }
    window.show('dash');
  };

  /* ── showSuccessAuth — toast după autentificare ─────────── */
  window.showSuccessAuth = function () {
    var el = document.getElementById('verify-toast');
    if (!el) return;
    el.classList.add('visible');
    setTimeout(function () { el.classList.remove('visible'); }, 3000);
  };

  /* ── initMulberryNotifications — stub ───────────────────── */
  window.initMulberryNotifications = function () {};

  /* ── closeMulberryReminderSheet / LibrarySheet ───────────── */
  window.closeMulberryReminderSheet = function () {
    var el = document.getElementById('reminder-sheet');
    if (el) el.classList.remove('open');
  };
  window.openMulberryLibrarySheet = function () {
    var el = document.getElementById('library-sheet');
    if (el) el.classList.add('open');
  };
  window.closeMulberryLibrarySheet = function () {
    var el = document.getElementById('library-sheet');
    if (el) el.classList.remove('open');
  };

  /* ── openSoftScoreModal ──────────────────────────────────── */
  window.openSoftScoreModal = function () {
    var el = document.getElementById('softscore-modal');
    if (el) el.classList.add('open');
  };
})();
