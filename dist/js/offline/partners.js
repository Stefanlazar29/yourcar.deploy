/* offline/partners.js — Partners (demo/stub) */

(function() {
  var partnerType = 'service';

  window.showPartnersAuth = function(mode) {
    window.show('partners-auth');
    var t = document.getElementById('pauth-title');
    var s = document.getElementById('pauth-sub');
    var loginForm = document.getElementById('pauth-login-form');
    var regForm = document.getElementById('pauth-register-form');
    var isReg = mode === 'register';
    if (t) t.textContent = isReg ? 'Înregistrare Partener' : 'Conectare Partener';
    if (s) s.textContent = isReg ? 'Creează contul firmei tale' : 'Accesează contul firmei tale';
    if (loginForm) loginForm.style.display = isReg ? 'none' : 'block';
    if (regForm) regForm.style.display = isReg ? 'block' : 'none';
  };

  window.selectPartnerType = function(t) {
    partnerType = t || 'service';
    ['service','insurance','carshop'].forEach(function(k) {
      var el = document.getElementById('ptype-' + k);
      if (el) el.classList.toggle('selected', k === partnerType);
    });
  };

  window.submitPartnerLogin = function() {
    window.showToast('Login partener: urmează backend.');
    window.show('partners-dash');
  };

  window.submitPartnerRegister = function() {
    window.showToast('Înregistrare partener: urmează backend.');
    window.show('partners-dash');
  };

  window.partnerLogout = function() {
    window.show('partners-landing');
  };

  window.loadPartners = function() {
    window.showToast('Listă parteneri: demo.');
  };

  window.filterPartners = function(kind) {
    ['all','service','insurance','carshop'].forEach(function(k) {
      var el = document.getElementById('ftab-' + k);
      if (el) el.classList.toggle('active', k === kind);
    });
  };
})();

