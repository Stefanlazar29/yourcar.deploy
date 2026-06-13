/** mulberry_softscore_hub.js — hub afișare YCS SoftScore în dashboard. */
(function () {
  window.addEventListener('mulberry:screen', function (e) {
    if (!e.detail || e.detail.screen !== 'dash') return;
    var el = document.getElementById('softscore-value');
    if (!el) return;
    var v = window.AppDB ? window.AppDB.getSavedVehicle() : {};
    el.textContent = v.ycs_score != null ? v.ycs_score + '%' : '—';
  });
})();
