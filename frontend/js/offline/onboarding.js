/**
 * onboarding.js — flux înregistrare vehicul (pași 1–4).
 */
(function () {
  var step = 0;

  window.goToOnboarding = function () {
    step = 0;
    if (typeof window.show === 'function') window.show('auth');
    updateStep();
  };

  function updateStep() {
    var titleEl = document.getElementById('auth-step-title');
    var subEl   = document.getElementById('auth-step-sub');
    var titles  = ['Contul tău', 'Vehiculul tău', 'Asigurare RCA', 'Confirmare'];
    if (titleEl) titleEl.textContent = titles[step] || 'Înregistrare';
    if (subEl)   subEl.textContent   = 'Pasul ' + (step + 1) + ' din 4';
  }

  /* submitStep0..3 — apelate din butoane în mulberry.html */
  window.submitStep0 = function () { step = 1; updateStep(); };
  window.submitStep1 = function () { step = 2; updateStep(); };
  window.submitStep2 = function () { step = 3; updateStep(); };
  window.submitStep3 = function () {
    localStorage.setItem('mulberry_verify_ok', '1');
    if (typeof window.bootApp === 'function') window.bootApp();
  };

  /* alias generic */
  window.submitStep = function (n) {
    step = (n != null ? n : step + 1);
    updateStep();
  };
})();
