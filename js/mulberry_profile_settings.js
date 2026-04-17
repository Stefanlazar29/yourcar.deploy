/**
 * MyMulberry — profil card (imagine vehicul, sefanlazar + bifă galbenă, gradient negru).
 */
(function () {
  'use strict';

  var FALLBACK_IMG = 'assets/car-profile-reference.png';
  var DISPLAY_NAME = 'sefanlazar';

  function enc(s) {
    return encodeURIComponent(String(s || '').slice(0, 400));
  }

  var IMG_NOTE =
    '<p class="profile-model-p profile-model-p--dim profile-literary-footnote">Imaginea de profil este o sinteză vizuală generată (Pollinations), pe fundal alb de studio; nu înlocuiește fotografia reală, fișa tehnică oficială sau expertiza unui mecanic.</p>';

  function getApiBase() {
    return (window.Config && window.Config.apiBaseUrl) || 'http://127.0.0.1:9000';
  }

  function getBearerToken() {
    var t = '';
    try {
      t =
        localStorage.getItem('mulberry_session') ||
        localStorage.getItem('yourcar_token') ||
        '';
    } catch (e) {}
    t = t != null ? String(t).trim() : '';
    if (!t || t.indexOf('eyJ') !== 0 || t.length < 51) return null;
    return t;
  }

  function wireNarrativeRefreshOnce() {
    var btn = document.getElementById('profile-narrative-refresh');
    if (!btn || btn.dataset.wired) return;
    btn.dataset.wired = '1';
    btn.addEventListener('click', function () {
      var tok = getBearerToken();
      if (!tok) {
        (window.showToast || alert)('Autentificare necesară (token JWT).');
        return;
      }
      var hist = document.getElementById('profile-model-history');
      var meta = document.getElementById('profile-narrative-meta');
      btn.disabled = true;
      var url = getApiBase().replace(/\/+$/, '') + '/me/vehicle/profile-narrative/refresh';
      fetch(url, { method: 'POST', headers: { Authorization: 'Bearer ' + tok } })
        .then(function (r) {
          return r.json().then(function (j) {
            if (!r.ok) {
              var d = j.detail;
              throw new Error(typeof d === 'string' ? d : JSON.stringify(d || j));
            }
            return j;
          });
        })
        .then(function (j) {
          if (hist) hist.innerHTML = (j.narrative || '') + IMG_NOTE;
          if (meta && j.updated_at) {
            meta.textContent =
              'Actualizat: ' + String(j.updated_at).replace('T', ' ').slice(0, 19) + ' (AI + istoric Mulberry)';
            meta.hidden = false;
          }
          if (window.showToast) window.showToast('Descriere profil actualizată.');
        })
        .catch(function (e) {
          (window.showToast || alert)((e && e.message) || 'Nu s-a putut regenera descrierea.');
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  function loadProfileNarrativeFromServer() {
    var hist = document.getElementById('profile-model-history');
    var meta = document.getElementById('profile-narrative-meta');
    var btn = document.getElementById('profile-narrative-refresh');
    if (!hist) return;
    var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
    var vin = String(v.vin || '').trim();
    var tok = getBearerToken();
    if (vin.length !== 17 || !tok) {
      hist.innerHTML =
        '<p class="profile-model-p profile-literary-p">Conectează-te cu un token valid și completează VIN-ul (17 caractere) pentru a încărca descrierea generată de server din istoricul vehiculului.</p>' +
        IMG_NOTE;
      if (meta) meta.hidden = true;
      if (btn) btn.hidden = true;
      return;
    }
    hist.innerHTML =
      '<p class="profile-model-p profile-literary-p" style="opacity:0.65">Se încarcă descrierea din istoric…</p>';
    if (btn) btn.hidden = false;
    wireNarrativeRefreshOnce();
    var url = getApiBase().replace(/\/+$/, '') + '/me/vehicle/profile-narrative';
    fetch(url, { headers: { Authorization: 'Bearer ' + tok } })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        var html = data && data.narrative ? String(data.narrative).trim() : '';
        if (html) {
          hist.innerHTML = html + IMG_NOTE;
          if (meta && data.updated_at) {
            meta.textContent =
              'Actualizat: ' + String(data.updated_at).replace('T', ' ').slice(0, 19) + ' (AI + istoric Mulberry)';
            meta.hidden = false;
          }
        } else {
          hist.innerHTML =
            '<p class="profile-model-p profile-literary-p">Nu există încă o descriere salvată. Apasă „Actualizează descrierea din istoric” pentru a o genera din datele vehiculului, documentelor, scorului și conversațiilor salvate.</p>' +
            IMG_NOTE;
          if (meta) meta.hidden = true;
        }
      })
      .catch(function () {
        hist.innerHTML =
          '<p class="profile-model-p profile-literary-p">Nu am putut încărca descrierea. Verifică backend-ul (FastAPI) și rețeaua.</p>' +
          IMG_NOTE;
        if (meta) meta.hidden = true;
      });
  }

  function readSoftScorePreview() {
    var el = document.getElementById('d-softscore-preview-pct');
    if (!el) return '—';
    var t = String(el.textContent || '').trim();
    if (!t) return '—';
    var m = t.match(/([\d]+[.,]?[\d]*)/);
    if (m) return m[1].replace('.', ',');
    return t.length > 12 ? t.slice(0, 12) + '…' : t;
  }

  function wireActions() {
    var c = document.getElementById('profile-btn-contact');
    if (c && !c.dataset.wired) {
      c.dataset.wired = '1';
      c.addEventListener('click', function () {
        var u = window.AppDB && window.AppDB.currentUser;
        var em = u && (u.email || u.identifier);
        if (em) {
          window.location.href = 'mailto:' + encodeURIComponent(em);
        } else if (typeof window.showToast === 'function') {
          window.showToast('Email indisponibil — verifică sesiunea.');
        }
      });
    }
    var b = document.getElementById('profile-btn-bookmark');
    if (b && !b.dataset.wired) {
      b.dataset.wired = '1';
      b.addEventListener('click', function () {
        window.location.href = 'mulberry_softscore.html';
      });
    }
  }

  function wireHubPreview() {
    var prev = document.getElementById('hub-mymulberry-preview');
    if (!prev || prev.dataset.wired) return;
    prev.dataset.wired = '1';
    prev.removeAttribute('aria-hidden');
    prev.setAttribute('role', 'button');
    prev.setAttribute('tabindex', '0');
    prev.setAttribute('aria-label', 'Deschide profilul MyMulberry');
    function go() {
      try {
        if (window.closeMulberryLibrarySheet) window.closeMulberryLibrarySheet();
      } catch (e1) {}
      if (typeof window.show === 'function') window.show('profile-settings');
      try {
        history.replaceState(null, '', 'mulberry.html#profile-settings');
      } catch (e2) {}
    }
    prev.addEventListener('click', go);
    prev.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        go();
      }
    });
  }

  function fill() {
    var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
    var marca = String(v.marca || '').trim() || '—';
    var model = String(v.model || '').trim() || '';
    var an = String(v.an || '').trim() || '';
    var km = v.km_actuali != null && v.km_actuali !== '' ? String(v.km_actuali) : '—';
    var fuel = String(v.combustibil || v.fuel || '').trim();
    var vin = String(v.vin || '').trim();
    var serie = String(v.serie || v.series || '').trim();

    var titleLine = [marca, model].filter(Boolean).join(' ') + (an ? ' · ' + an : '');
    var nameEl = document.getElementById('profile-display-name');
    if (nameEl) nameEl.textContent = DISPLAY_NAME;

    var titleEl = document.getElementById('profile-model-title-line');
    if (titleEl) titleEl.textContent = titleLine;

    var sub = document.getElementById('profile-model-vin-line');
    if (sub) sub.textContent = vin.length === 17 ? 'VIN ' + vin : 'Completează VIN în datele vehiculului pentru sincron complet.';

    var bio = document.getElementById('profile-bio');
    if (bio) {
      bio.textContent =
        'Co-pilot auto Mulberry · ' +
        (marca !== '—' || model
          ? [marca !== '—' ? marca : '', model].filter(Boolean).join(' ')
          : 'vehicul legat de cont');
    }

    var stSoft = document.getElementById('profile-stat-soft-txt');
    if (stSoft) stSoft.textContent = readSoftScorePreview();

    var stKm = document.getElementById('profile-stat-km');
    if (stKm) stKm.textContent = km !== '—' ? km : '—';

    var stYear = document.getElementById('profile-stat-year');
    if (stYear) stYear.textContent = an || '—';

    var hubSub = document.getElementById('hub-mymulberry-preview-sub');
    if (hubSub) {
      hubSub.textContent =
        vin.length >= 8
          ? 'VIN …' + vin.slice(-6)
          : [marca !== '—' ? marca : '', model].filter(Boolean).join(' ') || 'Profil vehicul · Mulberry';
    }

    var img = document.getElementById('profile-model-ai-img');
    if (img) {
      var prompt = [
        marca !== '—' ? marca : 'car',
        model,
        an || 'vehicle',
        'professional automotive studio photograph three quarter front view soft diffused lighting',
        'pure solid white background #ffffff no gradient no people',
        'photorealistic sharp detail no text no logo no watermark',
      ]
        .filter(Boolean)
        .join(' ');
      var seed = 0;
      for (var i = 0; i < prompt.length; i++) seed = (seed * 31 + prompt.charCodeAt(i)) >>> 0;
      img.onerror = function () {
        img.onerror = null;
        img.src = FALLBACK_IMG;
        syncHubThumb();
      };
      img.src =
        'https://image.pollinations.ai/prompt/' +
        enc(prompt) +
        '?width=768&height=900&nologo=true&seed=' +
        seed;
      img.alt = 'Vizual generat AI — ' + titleLine;
    }

    function syncHubThumb() {
      var hubImg = document.getElementById('hub-mymulberry-preview-img');
      if (!hubImg || !img) return;
      hubImg.onerror = function () {
        hubImg.onerror = null;
        hubImg.src = FALLBACK_IMG;
      };
      hubImg.src = img.src;
      hubImg.alt = titleLine;
    }
    syncHubThumb();

    loadProfileNarrativeFromServer();

    wireActions();
    wireHubPreview();
  }

  function run() {
    fill();
  }

  window.refreshProfileSettingsPreview = fill;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
