/**
 * api_poll_guard.js — rate limiting / backoff pentru fetch-uri (evită bucle agresive)
 * Nu există contentScript.js în proiect — erorile din consolă la „contentScript.js”
 * vin de la extensii Chrome; acest modul folosește doar codul aplicației.
 */
(function () {
  'use strict';

  /**
   * fetchWithBackoff este definit în js/api_client.js (retry + timeout + 5xx).
   * Acest fișier expune doar createSafePoller.
   */

  /**
   * Înlocuiește setInterval cu planificare adaptivă: succes → intervalMs, eșec → backoff.
   */
  window.createSafePoller = function (fn, intervalMs, options) {
    options = options || {};
    var maxConsecutiveFailures = options.maxConsecutiveFailures != null ? options.maxConsecutiveFailures : 5;
    var failCount = 0;
    var timerId = null;
    var stopped = false;

    function schedule(delay) {
      if (stopped) return;
      if (timerId) clearTimeout(timerId);
      timerId = setTimeout(tick, delay);
    }

    function tick() {
      if (stopped) return;
      if (failCount >= maxConsecutiveFailures) {
        console.warn('[SafePoller] Oprit după ' + maxConsecutiveFailures + ' eșecuri consecutive. Reîncarcă pagina.');
        return;
      }
      Promise.resolve()
        .then(function () {
          return fn();
        })
        .then(function (ok) {
          if (ok === false) failCount++;
          else failCount = 0;
          var delay = failCount > 0 ? Math.min(5000 * failCount, 60000) : intervalMs;
          schedule(delay);
        })
        .catch(function (e) {
          var st = e && e.httpStatus;
          var msg = (e && e.message) || '';
          if (st === 401 || msg.indexOf('401') >= 0 || (msg.toLowerCase && msg.toLowerCase().indexOf('unauthorized') >= 0)) {
            console.warn('[SafePoller] 401 — nu mai reîncerc.');
            return;
          }
          if (st === 403 || msg.indexOf('Eroare API (403)') >= 0) {
            console.warn('[SafePoller] 403 — nu mai reîncerc (ex. politică dispozitiv / HWID).');
            return;
          }
          failCount++;
          var delay = Math.min(1000 * Math.pow(2, Math.min(failCount, 3)), 60000);
          console.warn('[SafePoller] Eroare:', e && e.message, '— următorul tick în', delay, 'ms');
          schedule(delay);
        });
    }

    schedule(intervalMs);

    return {
      stop: function () {
        stopped = true;
        if (timerId) clearTimeout(timerId);
        timerId = null;
      }
    };
  };
})();
