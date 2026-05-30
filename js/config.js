/**
 * API base pentru Mulberry.
 * Orice host → http://46.225.100.151:8080
 */
(function () {
  function resolveMulberryApiBase() {
    return 'http://46.225.100.151:8080';
  }

  window.Config = window.Config || {};
  window.Config.apiBaseUrl = resolveMulberryApiBase();
})();
