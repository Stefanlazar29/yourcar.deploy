/** reminders.js — gestionare notificări și remindere RCA/ITP. */
(function () {
  window.MulberryReminders = {
    init: function () {},
    schedule: function (type, date) {
      try { localStorage.setItem('reminder_' + type, date); } catch (e) {}
    },
    get: function (type) {
      return localStorage.getItem('reminder_' + type) || null;
    }
  };
  if (typeof window.initMulberryNotifications === 'function') {
    window.initMulberryNotifications();
  }
})();
