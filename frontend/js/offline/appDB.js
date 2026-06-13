/**
 * appDB.js — stare locală a aplicației (user, vehicul, sesiune).
 * Stocare în localStorage; nu folosește IndexedDB.
 */
(function () {
  var VEHICLE_KEY = 'mulberry_vehicle';
  var USER_KEY    = 'mulberry_user';

  window.AppDB = {
    currentUser: null,

    /* ── vehicle ──────────────────────────────────────────── */
    getSavedVehicle: function () {
      try { return JSON.parse(localStorage.getItem(VEHICLE_KEY) || '{}'); } catch (e) { return {}; }
    },
    saveVehicle: function (data) {
      try { localStorage.setItem(VEHICLE_KEY, JSON.stringify(data)); } catch (e) {}
    },
    mergeVehicleFromServer: function (serverData) {
      var local = this.getSavedVehicle();
      this.saveVehicle(Object.assign({}, local, serverData));
      return Promise.resolve();
    },

    /* ── user ─────────────────────────────────────────────── */
    getUser: function () {
      if (this.currentUser) return this.currentUser;
      try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch (e) { return null; }
    },
    saveUser: function (user) {
      this.currentUser = user;
      try { localStorage.setItem(USER_KEY, JSON.stringify(user)); } catch (e) {}
    },

    /* ── ui helpers ───────────────────────────────────────── */
    ui: {
      syncDashboard: function () {
        var user    = window.AppDB.getUser();
        var vehicle = window.AppDB.getSavedVehicle();

        var nameEl = document.getElementById('dash-user-name');
        if (nameEl && user) nameEl.textContent = user.name || user.email || 'Utilizator';

        var vinEl = document.getElementById('dash-vin');
        if (vinEl && vehicle.vin) vinEl.textContent = vehicle.vin;

        var rcaEl = document.getElementById('dash-rca-expiry');
        if (rcaEl && vehicle.rca_expiry) rcaEl.textContent = vehicle.rca_expiry;
      }
    }
  };
})();
