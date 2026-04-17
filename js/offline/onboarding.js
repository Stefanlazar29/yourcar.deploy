/* offline/onboarding.js — pași onboarding (Mulberry) */

(function() {
  function val(id) {
    var el = document.getElementById(id);
    return (el && (el.value || '').trim()) || '';
  }

  function setActiveStep(step) {
    for (var i = 0; i <= 3; i++) {
      var el = document.getElementById('step-' + i);
      if (el) el.style.display = (i === step) ? 'flex' : 'none';
      var dot = document.getElementById('pb' + i);
      if (dot) {
        dot.classList.toggle('active', i === step);
        dot.classList.toggle('done', i < step);
      }
    }
    var t = document.getElementById('auth-step-title');
    var s = document.getElementById('auth-step-sub');
    if (t) t.textContent = (step === 0) ? 'Contul tău' : (step === 1) ? 'Vehicul' : (step === 2) ? 'Identificare' : 'Confirmare';
    if (s) s.textContent = 'Pasul ' + (step + 1) + ' din 4';
  }

  /** Ecran onboarding pas 1 (wizard în #s-auth), nu doar „auth” generic. */
  window.goToOnboarding = function() {
    if (typeof window.show === 'function') window.show('auth');
    setActiveStep(0);
  };
  window.setOnboardingStep = setActiveStep;

  window.clearErr = function(key) {
    var el = document.getElementById('err-' + key);
    if (el) { el.textContent = ''; el.classList.remove('show'); }
  };

  window.validateVIN = function(input) {
    var v = ((input && input.value) ? input.value : '').toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (input) input.value = v;
    var counter = document.getElementById('vin-counter');
    if (counter) counter.textContent = String(v.length) + ' / 17 caractere';
    var err = document.getElementById('err-vin');
    if (err) {
      if (v && v.length !== 17) { err.textContent = 'VIN trebuie să aibă 17 caractere.'; err.classList.add('show'); }
      else { err.textContent = ''; err.classList.remove('show'); }
    }
  };

  window.submitStep0 = async function() {
    var email = val('inp-email');
    var pass = val('inp-pass');
    var pass2 = val('inp-pass2');
    var ok = true;
    if (!email) { var e1 = document.getElementById('err-email'); if (e1) { e1.textContent = 'Completează emailul.'; e1.classList.add('show'); } ok = false; }
    if (!pass || pass.length < 8) { var e2 = document.getElementById('err-pass'); if (e2) { e2.textContent = 'Parola minim 8 caractere.'; e2.classList.add('show'); } ok = false; }
    if (pass2 !== pass) { var e3 = document.getElementById('err-pass2'); if (e3) { e3.textContent = 'Parolele nu coincid.'; e3.classList.add('show'); } ok = false; }
    if (!ok) return;

    if (typeof window.registerUser === 'function') {
      try {
        await window.registerUser(email, pass);
      } catch (regErr) {
        var msg = (regErr && regErr.message) ? String(regErr.message) : '';
        if (msg.indexOf('deja') >= 0 || msg.indexOf('înregistrat') >= 0) {
          /* cont LocalBase există deja — continuă onboarding */
        } else {
          var e4 = document.getElementById('err-email');
          if (e4) {
            e4.textContent = msg || 'Eroare la înregistrare.';
            e4.classList.add('show');
          }
          return;
        }
      }
    }

    setActiveStep(1);
  };

  window.submitStep1 = function() {
    var make = val('inp-make');
    var model = val('inp-model');
    var year = val('inp-year');
    var fuel = val('inp-fuel');
    var ok = true;
    if (!make) { var e1 = document.getElementById('err-make'); if (e1) { e1.textContent = 'Completează marca.'; e1.classList.add('show'); } ok = false; }
    if (!model) { var e2 = document.getElementById('err-vmodel'); if (e2) { e2.textContent = 'Completează modelul.'; e2.classList.add('show'); } ok = false; }
    if (!year) { var e3 = document.getElementById('err-year'); if (e3) { e3.textContent = 'Completează anul.'; e3.classList.add('show'); } ok = false; }
    if (!fuel) { var e4 = document.getElementById('err-fuel'); if (e4) { e4.textContent = 'Selectează combustibilul.'; e4.classList.add('show'); } ok = false; }
    if (!ok) return;
    setActiveStep(2);
  };

  window.submitStep2Form = function() {
    var plate = val('inp-plate').toUpperCase();
    var vin = val('inp-vin').toUpperCase();
    var series = val('inp-series');
    var ok = true;
    if (!plate) { var e1 = document.getElementById('err-plate'); if (e1) { e1.textContent = 'Completează numărul.'; e1.classList.add('show'); } ok = false; }
    if (!vin || vin.length !== 17) { var e2 = document.getElementById('err-vin'); if (e2) { e2.textContent = 'VIN trebuie să aibă 17 caractere.'; e2.classList.add('show'); } ok = false; }
    if (!ok) return;

    var make = val('inp-make');
    var model = val('inp-model');
    var year = val('inp-year');
    var confMake = document.getElementById('conf-make');
    if (confMake) confMake.textContent = (make + ' ' + model).trim();
    var confVin = document.getElementById('conf-vin');
    if (confVin) confVin.textContent = 'VIN: ' + vin;
    var confPlate = document.getElementById('conf-plate');
    if (confPlate) confPlate.textContent = 'Nr: ' + plate;
    var confYear = document.getElementById('conf-year');
    if (confYear) confYear.textContent = 'An: ' + year;
    var confSeries = document.getElementById('conf-series');
    if (confSeries) confSeries.textContent = series ? ('Serie: ' + series) : '';

    setActiveStep(3);
  };

  window.submitStep3 = async function(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!window.AppDB || typeof window.AppDB.registerVehicle !== 'function') {
      window.showToast('AppDB lipsește.');
      return;
    }

    var email = val('inp-email') || val('si-id') || 'offline@mulberry.local';
    var pass = val('inp-pass') || val('si-pass') || 'offline';
    var phone = val('inp-phone') || '';
    if (!window.AppDB.currentUser) {
      await window.AppDB.login(email, pass);
    }
    var token = window.api && window.api.getToken ? window.api.getToken() : (localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '');
    if (window.api && !token) {
      try {
        var regOut = await window.api.register(email, pass).catch(function() {});
        if (regOut && regOut.access_token && typeof regOut.access_token === 'string') {
          var rt = String(regOut.access_token).trim();
          if (rt.length > 20 && rt !== 'String') {
            token = rt;
            localStorage.setItem('mulberry_session', token);
            localStorage.setItem('yourcar_token', token);
            if (window.api.setSession) window.api.setSession(token, regOut.role || 'user');
          }
        }
        if (!token) {
          var loginOut = await window.api.login(email, pass, phone);
          if (loginOut && loginOut.access_token && typeof loginOut.access_token === 'string') {
            var lt = String(loginOut.access_token).trim();
            if (lt.length > 20 && lt !== 'String') {
              token = lt;
              localStorage.setItem('mulberry_session', token);
              localStorage.setItem('yourcar_token', token);
              if (window.api.setSession) window.api.setSession(token, loginOut.role || 'user');
            }
          }
        }
      } catch (err) {
        console.warn('[Onboarding] API auth eșuat, continuăm local:', err);
      }
    }

    token = window.api && window.api.getToken ? window.api.getToken() : (localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '');

    var vehicleData = {
      marca: val('inp-make'),
      model: val('inp-model'),
      an: val('inp-year'),
      combustibil: val('inp-fuel'),
      nr: (val('inp-plate') || '').toUpperCase(),
      vin: (val('inp-vin') || '').toUpperCase(),
      serie: val('inp-series') || ''
    };

    await window.AppDB.registerVehicle(vehicleData);

    var backendPayload = {
      make: vehicleData.marca,
      model: vehicleData.model,
      year: vehicleData.an,
      fuel: vehicleData.combustibil,
      plate: vehicleData.nr,
      vin: vehicleData.vin,
      series: vehicleData.serie || ''
    };

    var upsertResponse = null;
    if (window.api && window.api.upsertCar && token) {
      try {
        upsertResponse = await window.api.upsertCar(backendPayload);
        console.log('[Onboarding Pasul 4] Răspuns server upsertCar:', upsertResponse);
        (window.showToast || function() {})( 'Vehicul salvat în baza de date.' );
      } catch (err) {
        console.error('[Onboarding] upsertCar eșuat:', err);
        (window.showToast || function() {})( 'Vehicul salvat local; reconectează-te pentru sync.' );
      }
    } else if (!token) {
      (window.showToast || function() {})( 'Conectează-te cu ambele parole pentru a salva în DB.' );
    }

    if (token && String(token).trim().length > 20 && String(token).trim() !== 'String') {
      var tFinal = String(token).trim();
      localStorage.setItem('mulberry_session', tFinal);
      localStorage.setItem('yourcar_token', tFinal);
    } else if (token && (String(token).trim() === 'String' || String(token).trim().length < 20)) {
      console.warn('[Onboarding] Token invalid (posibil literal "String") — nu salvez.');
    }

    token = (localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '').trim();
    console.log('[Onboarding Pasul 4] Final — token în localStorage:', token ? ('DA, lungime ' + token.length) : 'NU (gol)');
    console.log('[Onboarding Pasul 4] Rămâi pe Pasul 4. Verifică Application → Local Storage → mulberry_session. Apoi apasă butonul „Confirm token OK”.');
    (window.showToast || function() {})( 'Pasul 4: verifică token-ul în consolă; fără redirect automat.' );

    var hint = document.getElementById('onboarding-step3-hint');
    var dashBtn = document.getElementById('btn-onboarding-dashboard');
    if (hint) hint.style.display = '';
    if (dashBtn) dashBtn.style.display = '';
  };

  window.onboardingProceedToDashboard = function() {
    if (window.AppDB.ui && typeof window.AppDB.ui.goTo === 'function') window.AppDB.ui.goTo('mulberry.html');
    else window.location.href = 'mulberry.html';
  };

  document.addEventListener('DOMContentLoaded', function() {
    setActiveStep(0);
    var dashBtn = document.getElementById('btn-onboarding-dashboard');
    if (dashBtn) dashBtn.addEventListener('click', function() { window.onboardingProceedToDashboard(); });
  });

  console.log('Mulberry Onboarding a fost încărcat cu succes!');
})();
