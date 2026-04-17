/**
 * MLRB — VehicleCore
 * Logică pură: model de date, sertar de stare (update parțial), observatori (fără notificări false),
 * fail-safe (viteză > 400 km/h sau baterie < 15%). Fără DOM/CSS.
 * Mapare ușoară ulterior: VehicleState → record Java, subscribe → ApplicationListener / flux reactiv.
 */
(function (global) {
  'use strict';

  var VEL_MAX_KMH = 400;
  var BATTERY_CRITICAL_PCT = 15;

  var STATE_KEYS = ['velocity', 'altitude', 'batteryLevel', 'motorStatus', 'alerts'];

  /**
   * @typedef {Object} VehicleState
   * @property {number} velocity      Viteză (km/h); bandă nominală 0–400; peste 400 → safety
   * @property {number} altitude
   * @property {number} batteryLevel  Nivel baterie (%); sub 15 → safety
   * @property {boolean} motorStatus
   * @property {Array<string|Object>} alerts Mesaje sau obiecte serializabile (comparare stabilă)
   */

  function defaultState() {
    return {
      velocity: 0,
      altitude: 0,
      batteryLevel: 100,
      motorStatus: false,
      alerts: []
    };
  }

  function cloneState(src) {
    return {
      velocity: src.velocity,
      altitude: src.altitude,
      batteryLevel: src.batteryLevel,
      motorStatus: src.motorStatus,
      alerts: cloneAlerts(src.alerts)
    };
  }

  function cloneAlerts(arr) {
    if (!arr || !arr.length) return [];
    var out = new Array(arr.length);
    for (var i = 0; i < arr.length; i++) {
      var item = arr[i];
      out[i] = typeof item === 'object' && item !== null ? JSON.parse(JSON.stringify(item)) : item;
    }
    return out;
  }

  function valuesEqual(a, b) {
    if (a === b) return true;
    if (Number.isNaN(a) && Number.isNaN(b)) return true;
    return false;
  }

  function alertsEqual(prev, next) {
    if (prev === next) return true;
    if (!prev || !next) return !prev && !next;
    if (prev.length !== next.length) return false;
    for (var i = 0; i < prev.length; i++) {
      var p = prev[i];
      var n = next[i];
      if (typeof p === 'object' && p !== null && typeof n === 'object' && n !== null) {
        if (JSON.stringify(p) !== JSON.stringify(n)) return false;
      } else if (p !== n) {
        return false;
      }
    }
    return true;
  }

  function fieldChanged(key, prev, next) {
    if (key === 'alerts') return !alertsEqual(prev.alerts, next);
    return !valuesEqual(prev[key], next[key]);
  }

  function shouldTriggerSafety(state) {
    return state.velocity > VEL_MAX_KMH || state.batteryLevel < BATTERY_CRITICAL_PCT;
  }

  function safetyInputsChanged(prev, next) {
    return !valuesEqual(prev.velocity, next.velocity) || !valuesEqual(prev.batteryLevel, next.batteryLevel);
  }

  /** Evită re-apeluri la fiecare ciclu: doar la intrare în unsafe sau la schimbare viteză/baterie cât e unsafe. */
  function shouldInvokeSafetyAfterUpdate(prev, next, touched) {
    if (!touched || !shouldTriggerSafety(next)) return false;
    if (!shouldTriggerSafety(prev)) return true;
    return safetyInputsChanged(prev, next);
  }

  /**
   * @param {Object} [options]
   * @param {VehicleState} [options.initial]
   * @param {function(): void} [options.onSafetyMode] Apelat când starea finală după update îndeplinește condițiile fail-safe
   */
  function createVehicleCore(options) {
    options = options || {};
    var state = cloneState(options.initial ? mergeIntoDefault(options.initial) : defaultState());
    var listeners = [];
    var safetyHandler = typeof options.onSafetyMode === 'function' ? options.onSafetyMode : noop;

    function noop() {}

    function mergeIntoDefault(partial) {
      var base = defaultState();
      for (var k = 0; k < STATE_KEYS.length; k++) {
        var key = STATE_KEYS[k];
        if (Object.prototype.hasOwnProperty.call(partial, key)) {
          if (key === 'alerts') base.alerts = cloneAlerts(partial.alerts);
          else base[key] = partial[key];
        }
      }
      return base;
    }

    function getState() {
      return cloneState(state);
    }

    /**
     * Actualizează doar câmpurile prezente în newData; notifică observatorii doar dacă
     * cel puțin o valoare s-a schimbat efectiv (fără flicker la cicluri identice).
     * @param {Partial<VehicleState>} newData
     * @returns {{ changed: boolean, state: VehicleState }}
     */
    function updateState(newData) {
      if (!newData || typeof newData !== 'object') {
        return { changed: false, state: getState() };
      }

      var prev = state;
      var next = cloneState(prev);
      var touched = false;

      for (var i = 0; i < STATE_KEYS.length; i++) {
        var key = STATE_KEYS[i];
        if (!Object.prototype.hasOwnProperty.call(newData, key)) continue;

        var incoming = newData[key];
        if (key === 'alerts') {
          var cloned = cloneAlerts(incoming);
          if (!alertsEqual(prev.alerts, cloned)) {
            next.alerts = cloned;
            touched = true;
          }
        } else {
          if (!valuesEqual(prev[key], incoming)) {
            next[key] = incoming;
            touched = true;
          }
        }
      }

      if (!touched) {
        return { changed: false, state: getState() };
      }

      state = next;

      if (shouldInvokeSafetyAfterUpdate(prev, next, true)) {
        safetyHandler();
      }

      var snapshot = getState();
      for (var j = 0; j < listeners.length; j++) {
        try {
          listeners[j](snapshot, buildChangeMask(prev, next));
        } catch (e) {
          if (typeof console !== 'undefined' && console.error) {
            console.error('[VehicleCore] observer error', e);
          }
        }
      }

      return { changed: true, state: snapshot };
    }

    function buildChangeMask(prev, next) {
      return {
        velocity: fieldChanged('velocity', prev, next),
        altitude: fieldChanged('altitude', prev, next),
        batteryLevel: fieldChanged('batteryLevel', prev, next),
        motorStatus: fieldChanged('motorStatus', prev, next),
        alerts: fieldChanged('alerts', prev, next)
      };
    }

    /**
     * @param {function(VehicleState, Object): void} fn Primește snapshot imutabil + mască câmpuri schimbate
     * @returns {function(): void} unsubscribe
     */
    function subscribe(fn) {
      if (typeof fn !== 'function') return noop;
      listeners.push(fn);
      return function unsubscribe() {
        var idx = listeners.indexOf(fn);
        if (idx !== -1) listeners.splice(idx, 1);
      };
    }

    function setSafetyHandler(handler) {
      safetyHandler = typeof handler === 'function' ? handler : noop;
    }

    /** Pentru teste / integrare: declanșare manuală aceluiași canal ca fail-safe-ul automat */
    function triggerSafetyMode() {
      safetyHandler();
    }

    return {
      getState: getState,
      updateState: updateState,
      subscribe: subscribe,
      setSafetyHandler: setSafetyHandler,
      triggerSafetyMode: triggerSafetyMode,
      constants: {
        VEL_MAX_KMH: VEL_MAX_KMH,
        BATTERY_CRITICAL_PCT: BATTERY_CRITICAL_PCT
      }
    };
  }

  var VehicleCore = {
    createVehicleCore: createVehicleCore,
    defaultState: defaultState,
    constants: {
      VEL_MAX_KMH: VEL_MAX_KMH,
      BATTERY_CRITICAL_PCT: BATTERY_CRITICAL_PCT
    }
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = VehicleCore;
  }
  global.VehicleCore = VehicleCore;
})(typeof window !== 'undefined' ? window : globalThis);
