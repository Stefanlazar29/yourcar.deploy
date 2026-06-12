/**
 * API base pentru Mulberry.
 * Production (mulberry.autos / HTTPS) → https://mulberry.autos/api
 * Dev local                           → http://46.225.100.151:8080
 */
(function () {
  function resolveMulberryApiBase() {
    var h = window.location.hostname;
    var proto = window.location.protocol;
    if (h === 'mulberry.autos' || h.endsWith('.vercel.app') || proto === 'https:') {
      return 'https://mulberry.autos/api';
    }
    return 'http://46.225.100.151:8080';
  }

  window.Config = window.Config || {};
  window.Config.apiBaseUrl = resolveMulberryApiBase();
})();
