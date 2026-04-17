/* offline/soft.js — Mulberry Soft Score (v1.0) */

(function() {
  function clamp01(x) { return Math.max(0, Math.min(1, x)); }

  // Helper pentru a citi din localStorage (cu fallback)
  function getSoftScoreData() {
    try { return JSON.parse(localStorage.getItem('mulberry_softscore_data') || '{}'); } catch (e) { return {}; }
  }

  // Funcție pentru a salva datele de calibrare
  window.saveSoftScoreCalibration = function() {
    var year = parseInt(document.getElementById('cal-year').value, 10);
    var km = parseInt(document.getElementById('cal-km').value, 10);
    var revision = document.getElementById('cal-revision').value;
    var accident = document.getElementById('cal-accident').value;
    var itp = document.getElementById('cal-itp').value;

    // Validare minimală
    if (!year || !km || !revision || !itp) {
      var errEl = document.getElementById('cal-err');
      if (errEl) errEl.textContent = 'Toate câmpurile sunt obligatorii!';
      return;
    }
    var data = { year: year, km: km, revision: revision, accident: accident, itp: itp, lastCalibrated: (new Date()).toISOString() };
    localStorage.setItem('mulberry_softscore_data', JSON.stringify(data));
    window.showToast('✅ SoftScore calibrat cu succes!', true);
    window.closeModalClick(null, 'modal-softscore'); // Închide modalul
    window.AppDB.ui.syncDashboard(); // Reîmprospătează dashboard-ul
  };

  // Deschide modalul de calibrare
  window.openSoftScoreModal = function() {
    var modal = document.getElementById('modal-softscore');
    if (modal) modal.classList.add('show');
    // Pre-populează cu date existente (dacă sunt)
    var data = getSoftScoreData();
    if (data.year) document.getElementById('cal-year').value = data.year;
    if (data.km) document.getElementById('cal-km').value = data.km;
    if (data.revision) document.getElementById('cal-revision').value = data.revision;
    if (data.accident) document.getElementById('cal-accident').value = data.accident;
    if (data.itp) document.getElementById('cal-itp').value = data.itp;
    var errEl = document.getElementById('cal-err'); // Curățăm erorile vechi
    if (errEl) errEl.textContent = '';
  };

  // Calculează SoftScore
  window.MulberrySoft = {
    computeScore: function(vehicle) {
      const calData = getSoftScoreData();
      if (!calData.year || !calData.km || !calData.revision || !calData.itp) {
        return { score: 'Necalibrat', hint: 'Necesită date complete pentru calibrare.' };
      }

      const currentYear = (new Date()).getFullYear();
      const age = Math.max(0, currentYear - calData.year);
      const km = calData.km;
      const hadAccident = calData.accident === 'yes';
      // Placeholder pentru mentenanță: 1.0 (perfect) sau 0.8 (cu probleme)
      const maintenanceFactor = 1.0; // Ideal, va fi calculat din remindere

      // Formula de start: Score = (70 - (Age * 2) - (Kms/10000 * 1.5)) * (Maintenance * 1.1)
      let score = (70 - (age * 2) - (km / 10000 * 1.5));
      score = score * (maintenanceFactor * 1.1);

      // Scade 5% pentru fiecare problemă neglijată (ex: accident)
      let neglectedProblems = 0;
      if (hadAccident) neglectedProblems++;
      // TODO: Adaugă aici logică pentru remindere întârziate

      score = score - (neglectedProblems * 5); // Scade 5% per problemă

      score = Math.max(0, Math.min(100, Math.round(score)));

      let hintText = 'Scor estimativ. Se ajustează cu mentenanța la timp.';
      if (hadAccident) hintText = 'Scorul este afectat de istoricul de accidente.';

      return { score: String(score), hint: hintText };
    }
  };

})();