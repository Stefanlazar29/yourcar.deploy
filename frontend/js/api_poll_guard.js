/** api_poll_guard.js — previne request-uri duble simultane. */
(function () {
  var _active = {};
  window.apiPollGuard = {
    run: function (key, fn) {
      if (_active[key]) return Promise.resolve(null);
      _active[key] = true;
      return Promise.resolve().then(fn).finally(function () { delete _active[key]; });
    },
    cancel: function (key) { delete _active[key]; }
  };
})();
