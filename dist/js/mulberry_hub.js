/**
 * Mulberry ID HUB — statistici flotă (BIOS header).
 * Backend: GET /fleet/stats
 */
(function () {
  function apiBase() {
    return (window.Config && window.Config.apiBaseUrl) || 'http://127.0.0.1:9000';
  }

  async function updateFleetCount() {
    var el = document.getElementById('vehicle-count');
    if (!el) return;
    try {
      var r = await fetch(apiBase() + '/fleet/stats', { method: 'GET', cache: 'no-store' });
      if (!r.ok) throw new Error(String(r.status));
      var data = await r.json();
      var n = Number(data.total_vehicles);
      el.textContent = (isNaN(n) ? '0' : String(n)) + '_UNITS_ACTIVE';
    } catch (e) {
      el.textContent = 'UNAVAILABLE';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('vehicle-count')) updateFleetCount();
  });
})();
