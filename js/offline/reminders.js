/* offline/reminders.js — Reminders + modal (stub safe) */

(function() {
  window.openAddModal = function() { window.showToast('Adaugă: urmează.'); };
  window.closeModalClick = function(e, id) {
    if (e && e.target && e.target.id === id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    }
  };
  window.saveItem = function() { window.showToast('Salvat (demo).'); };

  window.toggleEdit = function(viewId, inputId) {
    var v = document.getElementById(viewId);
    var i = document.getElementById(inputId);
    if (!v || !i) return;
    v.style.display = 'none';
    i.style.display = 'block';
    try { i.focus(); } catch (e) {}
  };

  window.cycleStatus = function() { window.showToast('Status schimbat (demo).'); };
  window.generateReminderPDF = function() { window.showToast('PDF reminder: dezactivat offline.'); };
  window.deleteReminder = function() { window.showToast('Șters (demo).'); };
  window.saveReminderEdit = function() { window.showToast('Modificări salvate (demo).'); };

  window.addOffer = function(title, desc) {
    window.showToast('Oferta adăugată: ' + (title || ''));
  };
})();

