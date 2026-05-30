/**
 * API base pentru Mulberry.
 * Producție (mulberry.autos) → Railway.
 * Orice alt host             → http://46.225.100.151:8080
 */
(function () {
  function resolveMulberryApiBase() {
    const host = window.location.hostname;

    if (host.includes('mulberry.autos')) {
      return 'https://mulberry-production-d9db.up.railway.app';
    }

    return 'http://46.225.100.151:8080';
  }

  window.Config = window.Config || {};
  window.Config.apiBaseUrl = resolveMulberryApiBase();
})();
