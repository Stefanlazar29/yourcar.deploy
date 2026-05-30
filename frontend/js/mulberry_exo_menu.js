/* Mulberry ID HUB — BIOS · mentenanță + AppDB + API */
(function () {
  'use strict';

  var LS_MODE = 'mulberry_exo_mode';
  var CLOUD_CAP_GB = 5;
  var CHAR_STORE = 16;
  var TIMING_LS_PREFIX = 'mulberry_timing_chain_';
  /** Mesaje UI cerute (policy conținut) */
  var MSG_INTERNAL_UPDATE = 'Disponibil la următoarea actualizare.';
  var MSG_INTRODU_DATE = 'introduce date';

  /** Notificare tip BIOS (strip #exo-bios-notify + console; showToast dacă există). */
  function showNotify(msg) {
    var t = msg != null ? String(msg) : '';
    try {
      if (typeof window.showToast === 'function') window.showToast(t);
    } catch (e0) {}
    try {
      var el = document.getElementById('exo-bios-notify');
      if (el) el.textContent = t;
    } catch (e1) {}
    try {
      console.log('[HUB]', t);
    } catch (e2) {}
  }

  function norm(s) {
    return (s == null ? '' : String(s)).trim();
  }
  function onlyAZ09(s) {
    return norm(s).toUpperCase().replace(/[^A-Z0-9]/g, '');
  }
  function pickLetters(s, n) {
    var m = onlyAZ09(s).replace(/[^A-Z]/g, '');
    return (m + 'AA').slice(0, n);
  }
  function pickDigits(s, n) {
    var m = onlyAZ09(s).replace(/[^0-9]/g, '');
    return (m + '00').slice(0, n);
  }
  function hash32(str) {
    var h = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = (h * 0x01000193) >>> 0;
    }
    return h >>> 0;
  }
  function deriveMulberryIndex(v) {
    var vin = onlyAZ09(v && v.vin);
    var series = onlyAZ09(v && (v.series || v.serie));
    var seed = vin + '|' + series;
    var num = (hash32(seed) % 9000) + 1000;
    var letters = pickLetters(series || vin, 2);
    var digits = pickDigits(vin.slice(-6), 2);
    if (!digits || digits === '00') digits = String(hash32(seed) % 100).padStart(2, '0');
    return 'MLBR-' + String(num) + '-' + letters + digits;
  }

  function apiBase() {
    var raw =
      (window.CONFIG && window.CONFIG.API_BASE_URL) ||
      (window.Config && window.Config.apiBaseUrl) ||
      'http://127.0.0.1:9000';
    raw = String(raw || '').trim().replace(/\/+$/, '');
    if (!raw) raw = 'http://127.0.0.1:9000';
    if (!/^https?:\/\//i.test(raw)) raw = 'http://' + raw.replace(/^\/+/, '');
    try {
      new URL(raw);
    } catch (e) {
      console.warn('[EXO menu] API_BASE_URL invalid, folosesc http://127.0.0.1:9000:', raw);
      raw = 'http://127.0.0.1:9000';
    }
    return raw.replace(/\/$/, '');
  }

  function getToken() {
    try {
      if (window.api && typeof window.api.getToken === 'function') {
        var t = window.api.getToken();
        if (t) return t;
      }
    } catch (e0) {}
    try {
      var tabOnly = !!window.MULBERRY_TAB_SESSION_ONLY;
      if (tabOnly) {
        return (
          sessionStorage.getItem('mulberry_session') ||
          sessionStorage.getItem('yourcar_token') ||
          localStorage.getItem('mulberry_session') ||
          localStorage.getItem('yourcar_token') ||
          ''
        );
      }
      return (
        localStorage.getItem('mulberry_session') ||
        localStorage.getItem('yourcar_token') ||
        sessionStorage.getItem('mulberry_session') ||
        sessionStorage.getItem('yourcar_token') ||
        ''
      );
    } catch (e) {
      return '';
    }
  }

  /** Etichetă Kanban / e-ink (PDF) — fetch + blob; fallback deschidere filă (evită blocaje download). */
  function downloadKanbanLabelPdf() {
    var url = apiBase().replace(/\/+$/, '') + '/labels/kanban-pervasive-sample.pdf';

    function tryOpenInNewTab() {
      var w = window.open(url, '_blank', 'noopener,noreferrer');
      if (!w) {
        try {
          alert(
            'PDF: permite ferestre pop-up pentru acest site sau deschide manual:\n' + url
          );
        } catch (e0) {}
      }
    }

    fetch(url, { method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.blob();
      })
      .then(function (blob) {
        if (!blob || blob.size < 80) throw new Error('PDF gol sau invalid.');
        var t = (blob.type || '').toLowerCase();
        if (t && t.indexOf('pdf') < 0 && t.indexOf('octet-stream') < 0) {
          throw new Error('Răspunsul nu este PDF.');
        }
        var u = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = u;
        a.download = 'kanban-pervasive-label.pdf';
        a.rel = 'noopener';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () {
          try {
            URL.revokeObjectURL(u);
          } catch (eR) {}
        }, 4000);
      })
      .catch(function (e) {
        try {
          console.warn('[EXO] Kanban PDF fetch:', e);
        } catch (e1) {}
        tryOpenInNewTab();
      });
  }

  function digitalIdPayload(v, mlbr) {
    var title = [norm(v.marca), norm(v.series || v.serie), norm(v.model)].filter(Boolean).join(' ');
    return (
      'MULBERRY DIGITAL ID\n' +
      'ID: ' + mlbr + '\n' +
      'VIN: ' + (onlyAZ09(v.vin) || '—') + '\n' +
      'Nr: ' + (norm(v.nr || v.plate).toUpperCase() || '—') + '\n' +
      'Vehicul: ' + (title || '—') + '\n' +
      '— Mulberry ID HUB'
    );
  }

  /** Bază pentru `mulberry_qr_demo.html` (același folder cu HUB). null dacă file:// */
  function demoPageBaseUrl() {
    try {
      var href = String(window.location.href || '');
      if (href.indexOf('file:') === 0) return null;
      var path = window.location.pathname || '/';
      var i = path.lastIndexOf('/');
      var dir = i >= 0 ? path.slice(0, i + 1) : '/';
      return window.location.origin + dir;
    } catch (e) {
      return null;
    }
  }

  /** URL demo complet — stabil pentru același profil (MLBR + câmpuri vehicul). */
  function buildDemoUrlFull(v, mlbr) {
    var base = demoPageBaseUrl();
    if (!base) return null;
    var q = new URLSearchParams();
    q.set('v', '1');
    q.set('mlbr', mlbr);
    q.set('vin', onlyAZ09(v.vin));
    q.set('plate', norm(v.nr || v.plate).toUpperCase());
    q.set('marca', norm(v.marca));
    q.set('model', norm(v.model));
    q.set('an', norm(v.an));
    q.set('serie', norm(v.serie || v.series));
    return base + 'mulberry_qr_demo.html?' + q.toString();
  }

  function buildDemoUrlMinimal(v, mlbr) {
    var base = demoPageBaseUrl();
    if (!base) return null;
    var q = new URLSearchParams();
    q.set('v', '1');
    q.set('mlbr', mlbr);
    q.set('vin', onlyAZ09(v.vin));
    return base + 'mulberry_qr_demo.html?' + q.toString();
  }

  /** Cel mai scurt link demo — doar MLBR (m), pentru QR mic cu module mari. */
  function buildDemoUrlTiny(mlbr) {
    var base = demoPageBaseUrl();
    if (!base || !mlbr) return null;
    return base + 'mulberry_qr_demo.html?m=' + encodeURIComponent(mlbr);
  }

  /** Pagină publică `vehicle_present.html` — prezentare vehicul din baza MLBR, scanabil oriunde. */
  function buildMlbrPublicPageUrl(mlbr) {
    var base = demoPageBaseUrl();
    if (!base || !mlbr) return null;
    return base + 'vehicle_present.html?m=' + encodeURIComponent(mlbr);
  }

  /** QR principal: `/p/{VIN}` → modal BIOS în mulberry.html */
  function buildProfilePathUrl(v) {
    var vin = onlyAZ09(v && v.vin);
    if (vin.length !== 17) return null;
    var base = demoPageBaseUrl();
    if (!base) return null;
    return base.replace(/\/$/, '') + '/p/' + vin;
  }

  /** Payload scanabil permanent: link demo HTTP(S), altfel linie compactă MULBERRY|… */
  function profileQrPayload(v, mlbr) {
    var url = buildDemoUrlFull(v, mlbr);
    if (url) return url;
    return [
      'MULBERRY',
      '1',
      mlbr,
      onlyAZ09(v.vin),
      norm(v.nr || v.plate).toUpperCase(),
      norm(v.marca),
      norm(v.model),
      norm(v.an),
      norm(v.serie || v.series)
    ].join('|');
  }

  function profileQrPayloadForExport(v, mlbr) {
    return buildDemoUrlFull(v, mlbr) || profileQrPayload(v, mlbr);
  }

  function charBar(pct, totalChars) {
    var p = typeof pct === 'number' && !isNaN(p) ? Math.max(0, Math.min(100, pct)) : 0;
    var filled = Math.round((p / 100) * totalChars);
    if (filled > totalChars) filled = totalChars;
    var empty = totalChars - filled;
    return new Array(filled + 1).join('█') + new Array(empty + 1).join('░');
  }

  function formatDateFeed(iso) {
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return '—';
      var dd = String(d.getDate()).padStart(2, '0');
      var mm = String(d.getMonth() + 1).padStart(2, '0');
      var yy = d.getFullYear();
      return dd + '.' + mm + '.' + yy;
    } catch (e) {
      return '—';
    }
  }

  function formatLocalSync(d) {
    var x = d || new Date();
    var y = x.getFullYear();
    var m = String(x.getMonth() + 1).padStart(2, '0');
    var da = String(x.getDate()).padStart(2, '0');
    var h = String(x.getHours()).padStart(2, '0');
    var mi = String(x.getMinutes()).padStart(2, '0');
    return y + '-' + m + '-' + da + ' ' + h + ':' + mi;
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function parseKm(v) {
    var k = v.km != null ? v.km : v.kilometraj != null ? v.kilometraj : v.kilometers != null ? v.kilometers : v.odometer;
    if (k == null) return 0;
    var n = parseInt(String(k).replace(/[^\d]/g, ''), 10);
    return isNaN(n) ? 0 : n;
  }

  function estimateKmIfMissing(v) {
    var km = parseKm(v);
    if (km > 0) return km;
    var y = parseInt(String(v.an || '').trim(), 10);
    if (isNaN(y) || y < 1970) return 0;
    var age = Math.max(0, new Date().getFullYear() - y);
    return age * 13500;
  }

  function getHardwareProfile(v) {
    var marca = norm(v.marca).toLowerCase();
    var model = norm(v.model).toLowerCase();
    var fuel = norm(v.combustibil).toLowerCase();
    var year = parseInt(String(v.an || '').trim(), 10) || 0;
    var fabia = model.indexOf('fabia') !== -1;
    var skoda = marca.indexOf('skoda') !== -1 || marca.indexOf('škoda') !== -1;

    if ((skoda && fabia) || (fabia && year >= 1999 && year <= 2014)) {
      return {
        engineCode: 'CBZA / CBZB (1.2 HTP · REF PIESE)',
        oilSpec: 'VW 502 00 / 504 00',
        idleRpm: '750',
        maxRpm: '5400',
        gearbox: '02T · MAN 5 VITEZE',
        brakes: 'FS-III (ABS / ENCODER REF)',
        tires: '2.1 BAR (FRONT) / 2.0 BAR (REAR)',
        family: 'fabia6y'
      };
    }
    if (skoda || fabia) {
      return {
        engineCode: 'CBZA / CBZB (VERIFICĂ MOTOR)',
        oilSpec: 'VW 502 00 / 504 00 (TSI/HTP)',
        idleRpm: '750',
        maxRpm: '5400',
        gearbox: '02T / DQ200 (VERIFY)',
        brakes: 'FS-III / MK60 (VERIFY)',
        tires: 'SEE PLACARD',
        family: 'skoda'
      };
    }
    return {
      engineCode: 'SEE OEM · ENGINE CODE PLATE',
      oilSpec: 'OEM ACEA / VW (VERIFY)',
      idleRpm: '—',
      maxRpm: '—',
      gearbox: '—',
      brakes: '—',
      tires: '—',
      family: 'generic'
    };
  }

  function getTimingChainLine(v) {
    var vinK = onlyAZ09(v.vin);
    var iso = '';
    try {
      iso = vinK ? localStorage.getItem(TIMING_LS_PREFIX + vinK) || '' : '';
    } catch (e) {}
    if (!iso && norm(v.timing_chain_inspection)) {
      return 'LAST: ' + norm(v.timing_chain_inspection) + ' · 1.2 TSI CRITICAL';
    }
    if (iso) {
      return 'LAST INSPECTION: ' + formatDateFeed(iso) + ' · 1.2 TSI CHAIN';
    }
    return MSG_INTRODU_DATE;
  }

  function bushingLine(km) {
    if (km >= 155000) return 'WARN · VERIFICĂ BUȘONI (CLOC-CLOC)';
    if (km >= 115000) return 'WARN · UZURĂ PROBABILĂ';
    return 'OK';
  }

  function corrosionLine(docs) {
    try {
      if (localStorage.getItem('mulberry_sill_verified') === '1') return 'SILL: VERIFIED (MANUAL)';
    } catch (e) {}
    if (findDoc(docs, ['SILL', 'PRAG', 'CORROSION', 'RUGIN'])) return 'SILL: VERIFIED (DOC VAULT)';
    return MSG_INTRODU_DATE;
  }

  function clutchLine(km) {
    var ref = 120000;
    if (km <= 0) return MSG_INTRODU_DATE;
    var p = Math.min(99, Math.round((km / ref) * 100));
    return '~' + p + '% UZURĂ EST. @ ' + km.toLocaleString('ro-RO') + ' KM (REF ' + ref / 1000 + 'K)';
  }

  function applyHardwareUI(v, docs) {
    var p = getHardwareProfile(v);
    var km = estimateKmIfMissing(v);

    var el;
    el = document.getElementById('bios-hw-engine');
    if (el) el.textContent = norm(v.engine_code) || p.engineCode;
    el = document.getElementById('bios-hw-oil');
    if (el) el.textContent = norm(v.oil_spec) || p.oilSpec;
    el = document.getElementById('bios-hw-timing');
    if (el) el.textContent = getTimingChainLine(v);
    el = document.getElementById('bios-hw-rpm');
    if (el) el.textContent = p.idleRpm + ' / ' + p.maxRpm + ' RPM';
    el = document.getElementById('bios-hw-gearbox');
    if (el) el.textContent = norm(v.gearbox_code) || p.gearbox;
    el = document.getElementById('bios-hw-brake');
    if (el) el.textContent = norm(v.brake_system) || p.brakes;
    el = document.getElementById('bios-hw-tires');
    if (el) el.textContent = norm(v.tire_pressure_baseline) || p.tires;

    el = document.getElementById('bios-hw-bush');
    if (el) {
      el.textContent = 'STATUS: ' + bushingLine(km);
      el.classList.toggle('bios-warn-txt', km >= 115000);
    }

    el = document.getElementById('bios-corrosion-sill');
    if (el) el.textContent = corrosionLine(docs || []);

    el = document.getElementById('bios-clutch-wear');
    if (el) el.textContent = clutchLine(km);
  }

  function docTypeKey(t) {
    return norm(t)
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, '');
  }

  function findDoc(docs, keys) {
    if (!Array.isArray(docs)) return null;
    for (var i = 0; i < docs.length; i++) {
      var k = docTypeKey(docs[i].type);
      for (var j = 0; j < keys.length; j++) {
        if (k.indexOf(keys[j]) !== -1) return docs[i];
      }
    }
    return null;
  }

  function adminLineFromDoc(d) {
    if (!d) return MSG_INTRODU_DATE;
    if (!d.verified) return MSG_INTRODU_DATE;
    var st = 'VERIFIED';
    var up = d.uploaded_at ? formatDateFeed(d.uploaded_at) : '—';
    return st + ' · ' + up;
  }

  function renderAdminFromDocs(docs) {
    var itp = findDoc(docs, ['ITP']);
    var rca = findDoc(docs, ['RCA']);
    var tal = findDoc(docs, ['TALON', 'TALO', 'CARTE', 'IDENT']);

    var a = document.getElementById('bios-admin-itp');
    if (a) a.textContent = itp ? adminLineFromDoc(itp) : MSG_INTRODU_DATE;
    var b = document.getElementById('bios-admin-rca');
    if (b) b.textContent = rca ? adminLineFromDoc(rca) : MSG_INTRODU_DATE;
    var c = document.getElementById('bios-admin-talon');
    if (c) c.textContent = tal ? adminLineFromDoc(tal) : MSG_INTRODU_DATE;
    var vaultEl = document.getElementById('bios-admin-vault');
    if (vaultEl) {
      var n = (docs && docs.length) || 0;
      vaultEl.textContent = n > 0 ? String(n) + ' fișiere cloud' : MSG_INTRODU_DATE;
    }
  }

  function setStorageMbAndBar(docCount) {
    var barEl = document.getElementById('exo-storage-bar');
    var mbEl = document.getElementById('bios-storage-mb');
    if (barEl) barEl.textContent = charBar(0, CHAR_STORE);
    if (mbEl) mbEl.textContent = MSG_INTERNAL_UPDATE;
  }

  function authHeadersJson() {
    var h = { 'Content-Type': 'application/json' };
    var t = getToken();
    if (t) h['Authorization'] = 'Bearer ' + t;
    return h;
  }

  function formatCycleTime(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso.indexOf('T') === -1 ? iso.replace(' ', 'T') + 'Z' : iso);
      if (isNaN(d.getTime())) return String(iso).slice(0, 19);
      return d.toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
      return '—';
    }
  }

  function formatEta(sec) {
    if (sec == null || sec === '') return '—';
    var s = Math.floor(Number(sec));
    if (s < 0) s = 0;
    var m = Math.floor(s / 60);
    var r = s % 60;
    return m + 'm ' + r + 's';
  }

  function applyExoPrefUI(prefs) {
    prefs = prefs || {};
    var usage = norm(prefs.usage) || 'mixed';
    var budget = norm(prefs.budget) || 'medium';
    var concerns = Array.isArray(prefs.concerns) ? prefs.concerns : [];

    document.querySelectorAll('#exo-pref-usage .bios-mode-btn').forEach(function (b) {
      b.classList.toggle('is-active', b.getAttribute('data-usage') === usage);
    });
    document.querySelectorAll('#exo-pref-budget .bios-mode-btn').forEach(function (b) {
      b.classList.toggle('is-active', b.getAttribute('data-budget') === budget);
    });
    document.querySelectorAll('#exo-pref-concerns input[data-concern]').forEach(function (cb) {
      var k = cb.getAttribute('data-concern');
      cb.checked = concerns.indexOf(k) >= 0;
    });
  }

  function collectExoPrefsFromUI() {
    var usage = 'mixed';
    var ub = document.querySelector('#exo-pref-usage .bios-mode-btn.is-active');
    if (ub) usage = ub.getAttribute('data-usage') || 'mixed';
    var budget = 'medium';
    var bb = document.querySelector('#exo-pref-budget .bios-mode-btn.is-active');
    if (bb) budget = bb.getAttribute('data-budget') || 'medium';
    var concerns = [];
    document.querySelectorAll('#exo-pref-concerns input[data-concern]:checked').forEach(function (cb) {
      concerns.push(cb.getAttribute('data-concern'));
    });
    return { usage: usage, budget: budget, concerns: concerns, location: 'Romania' };
  }

  function loadExoPreferences() {
    if (!getToken()) {
      applyExoPrefUI({});
      return;
    }
    fetch(apiBase() + '/me/preferences', { headers: authHeadersJson() })
      .then(function (r) {
        return r.ok ? r.json() : {};
      })
      .then(function (data) {
        applyExoPrefUI(data || {});
      })
      .catch(function () {
        applyExoPrefUI({});
      });
  }

  function saveExoPreferences() {
    if (!getToken()) return;
    var body = collectExoPrefsFromUI();
    fetch(apiBase() + '/me/preferences', {
      method: 'PUT',
      headers: authHeadersJson(),
      body: JSON.stringify(body)
    })
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, j: j };
        });
      })
      .then(function (x) {
        if (x.ok && window.showToast) window.showToast(x.j.message || 'Preferințe salvate.');
      })
      .catch(function () {});
  }

  function refreshExoSchedulerStatus() {
    var nextEl = document.getElementById('exo-next-cycle');
    var lastEl = document.getElementById('exo-last-cycle');
    return fetch(apiBase() + '/exo/status')
      .then(function (r) {
        if (!r.ok) {
          if (nextEl) nextEl.textContent = MSG_INTRODU_DATE;
          if (lastEl) lastEl.textContent = MSG_INTRODU_DATE;
          return false;
        }
        return r.json();
      })
      .then(function (data) {
        if (data === false) return false;
        var st = (data && data.scheduler) || {};
        var last = st.last_cycle_at;
        var ins = st.last_cycle_insights;
        if (lastEl) {
          lastEl.textContent =
            last
              ? formatCycleTime(last) + (ins != null ? ' · ' + ins + ' insights' : '')
              : MSG_INTRODU_DATE;
        }
        if (nextEl) {
          var eta = data && data.next_cycle_in_sec_approx;
          nextEl.textContent = eta != null ? '≈ ' + formatEta(eta) : MSG_INTRODU_DATE;
        }
        return true;
      })
      .catch(function () {
        if (nextEl) nextEl.textContent = MSG_INTRODU_DATE;
        if (lastEl) lastEl.textContent = MSG_INTRODU_DATE;
        return false;
      });
  }

  function runExoCycleNow() {
    if (!getToken()) {
      if (window.showToast) window.showToast('Autentifică-te pentru EXO Intelligence.');
      return;
    }
    var btn = document.getElementById('exo-run-now');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '[… EXO …]';
    }
    fetch(apiBase() + '/exo/run', { method: 'POST', headers: authHeadersJson() })
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, j: j };
        });
      })
      .then(function (x) {
        if (window.showToast) {
          window.showToast(
            x.ok
              ? 'EXO: ' + (x.j.insights_added != null ? x.j.insights_added : '?') + ' insights'
              : 'EXO eșuat'
          );
        }
        refreshExoSchedulerStatus().catch(function () {});
      })
      .catch(function () {
        if (window.showToast) window.showToast('EXO: eroare rețea');
      })
      .finally(function () {
        if (btn) {
          btn.disabled = false;
          btn.textContent = '[▶ RULEAZĂ ACUM]';
        }
      });
  }

  function bindExoIntelligenceUI(vin) {
    document.querySelectorAll('#exo-pref-usage .bios-mode-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('#exo-pref-usage .bios-mode-btn').forEach(function (x) {
          x.classList.remove('is-active');
        });
        b.classList.add('is-active');
      });
    });
    document.querySelectorAll('#exo-pref-budget .bios-mode-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('#exo-pref-budget .bios-mode-btn').forEach(function (x) {
          x.classList.remove('is-active');
        });
        b.classList.add('is-active');
      });
    });

    var saveBtn = document.getElementById('exo-prefs-save');
    if (saveBtn) saveBtn.addEventListener('click', saveExoPreferences);
    var runBtn = document.getElementById('exo-run-now');
    if (runBtn) runBtn.addEventListener('click', runExoCycleNow);

    loadExoPreferences();
    refreshExoSchedulerStatus().catch(function () {});
    if (vin) setHealthAnomalies(vin).catch(function () {});

    if (window.__exoStatusPoller && typeof window.__exoStatusPoller.stop === 'function') {
      window.__exoStatusPoller.stop();
    }
    if (window.__exoStatusTimer) clearInterval(window.__exoStatusTimer);
    window.__exoStatusTimer = null;

    function hubExoPollTick() {
      return refreshExoSchedulerStatus().then(function (ok1) {
        if (!vin || ok1 === false) return ok1;
        return setHealthAnomalies(vin).then(function (ok2) {
          return ok1 !== false && ok2 !== false;
        });
      });
    }

    if (typeof window.createSafePoller === 'function') {
      window.__exoStatusPoller = window.createSafePoller(hubExoPollTick, 25000, {
        maxConsecutiveFailures: 12
      });
    } else {
      window.__exoStatusTimer = setInterval(function () {
        refreshExoSchedulerStatus().catch(function () {});
        if (vin) setHealthAnomalies(vin).catch(function () {});
      }, 25000);
    }

    /* SSE: Bearer în header (fără token în URL) — fetch + ReadableStream */
    if (window.__exoSseAbort) {
      try {
        window.__exoSseAbort.abort();
      } catch (e) {}
      window.__exoSseAbort = null;
    }
    var tok2 = getToken();
    if (tok2 && vin && typeof fetch !== 'undefined' && window.ReadableStream) {
      var ac = new AbortController();
      window.__exoSseAbort = ac;
      var sseBuf = '';
      fetch(apiBase() + '/exo/stream?vin=' + encodeURIComponent(vin), {
        headers: { Authorization: 'Bearer ' + tok2 },
        signal: ac.signal
      })
        .then(function (r) {
          if (!r.ok || !r.body) return null;
          var reader = r.body.getReader();
          var dec = new TextDecoder();
          function pump() {
            return reader.read().then(function (x) {
              if (x.done) return;
              sseBuf += dec.decode(x.value, { stream: true });
              var parts = sseBuf.split('\n\n');
              sseBuf = parts.pop() || '';
              parts.forEach(function (block) {
                var lines = block.split('\n');
                for (var i = 0; i < lines.length; i++) {
                  if (lines[i].indexOf('data:') !== 0) continue;
                  try {
                    JSON.parse(lines[i].slice(5).trim());
                    if (document.getElementById('exo-health-anomalies')) setHealthAnomalies(vin).catch(function () {});
                    refreshExoSchedulerStatus().catch(function () {});
                  } catch (e2) {}
                }
              });
              return pump();
            });
          }
          return pump();
        })
        .catch(function () {});
    }
  }

  function setHealthAnomalies(vin) {
    var host = document.getElementById('exo-health-anomalies');
    if (!host) return Promise.resolve(true);
    host.innerHTML =
      '<div class="bios-log-empty">' + esc(MSG_INTERNAL_UPDATE) + '</div>';
    return Promise.resolve(true);
  }

  function fetchCloudList(vin, onDone) {
    var vSaved = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
    if (!getToken() || !vin) {
      renderAdminFromDocs([]);
      applyHardwareUI(vSaved, []);
      setStorageMbAndBar(0);
      if (onDone) onDone([]);
      return;
    }
    fetch(apiBase() + '/cloud/list?vin=' + encodeURIComponent(vin))
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        var docs = (data && data.documents) || [];
        renderAdminFromDocs(docs);
        var v2 = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
        applyHardwareUI(v2, docs);
        setStorageMbAndBar(docs.length);
        if (onDone) onDone(docs);
      })
      .catch(function () {
        renderAdminFromDocs([]);
        var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
        applyHardwareUI(v, []);
        setStorageMbAndBar(0);
        if (onDone) onDone([]);
      });
  }

  function checkSync(vin) {
    var pill = document.getElementById('exo-sync-pill');
    var labelEl = document.getElementById('exo-sync-label');
    var det = document.getElementById('exo-sync-detail');
    var onlineEl = document.getElementById('exo-header-online');
    var syncLocalEl = document.getElementById('bios-local-sync');
    var stripApi = document.getElementById('exo-strip-api');
    var stripExo = document.getElementById('exo-strip-exo');
    var stripVin = document.getElementById('exo-strip-vin');
    var stripObd = document.getElementById('exo-strip-obd');

    function setStripsOffline() {
      if (stripApi) {
        stripApi.className = 'bios-st bios-st-off';
        stripApi.textContent = '[OFFLINE] API';
      }
      if (stripExo) {
        stripExo.className = 'bios-st bios-st-off';
        stripExo.textContent = '[OFFLINE] EXO';
      }
      if (stripObd) {
        stripObd.className = 'bios-st bios-st-off';
        stripObd.textContent = '[OFFLINE] OBD';
      }
    }

    fetch(apiBase() + '/health', { method: 'GET' })
      .then(function (r) {
        if (!r.ok) throw new Error('bad');
        return r.json().catch(function () {
          return {};
        });
      })
      .then(function () {
        if (pill) pill.classList.remove('bios-sync-warn');
        if (labelEl) labelEl.textContent = '[● ONLINE]';
        if (onlineEl) {
          onlineEl.textContent = 'ONLINE';
          onlineEl.classList.add('bios-accent-blink');
          onlineEl.style.color = '';
        }
        if (stripApi) {
          stripApi.className = 'bios-st bios-st-ok';
          stripApi.textContent = '[OK] API';
        }
        if (stripObd) {
          stripObd.className = 'bios-st bios-st-off';
          stripObd.textContent = '[OFFLINE] OBD';
        }
        var vinOk = vin && onlyAZ09(vin).length === 17;
        if (stripVin) {
          stripVin.className = 'bios-st ' + (vinOk ? 'bios-st-ok' : 'bios-st-warn');
          stripVin.textContent = vinOk ? '[OK] VIN' : '[!] VIN';
        }
        var nowStr = formatLocalSync(new Date());
        if (syncLocalEl) syncLocalEl.textContent = MSG_INTERNAL_UPDATE;
        var base = getToken()
          ? 'API activ · ' + nowStr
          : 'API activ · autentificare pentru cloud';
        if (det) det.textContent = base;
        if (!vin) {
          if (stripExo) {
            stripExo.className = 'bios-st bios-st-off';
            stripExo.textContent = '[OFFLINE] EXO';
          }
          return;
        }
        return fetch(apiBase() + '/exo/health?vin=' + encodeURIComponent(vin))
          .then(function (r) {
            return r.json();
          })
          .then(function (h) {
            if (stripExo) {
              if (h && h.ok && h.within_24h) {
                stripExo.className = 'bios-st bios-st-ok';
                stripExo.textContent = '[OK] EXO';
              } else {
                stripExo.className = 'bios-st bios-st-warn';
                stripExo.textContent = '[!] EXO';
              }
            }
            if (h && h.ok && h.within_24h && det) det.textContent = base + ' · EXO: OK (24H)';
          })
          .catch(function () {
            if (stripExo) {
              stripExo.className = 'bios-st bios-st-off';
              stripExo.textContent = '[OFFLINE] EXO';
            }
          });
      })
      .catch(function () {
        if (pill) pill.classList.add('bios-sync-warn');
        if (labelEl) labelEl.textContent = '[○ OFFLINE]';
        if (onlineEl) {
          onlineEl.textContent = 'DEGRADED';
          onlineEl.classList.remove('bios-accent-blink');
          onlineEl.style.color = 'var(--danger)';
        }
        if (det) det.textContent = '[!] SYNC_ERROR: CORE_DB_UNREACHABLE // PORT 9000';
        if (syncLocalEl) syncLocalEl.textContent = MSG_INTERNAL_UPDATE;
        setStripsOffline();
        if (stripVin && vin) {
          var ok = onlyAZ09(vin).length === 17;
          stripVin.className = 'bios-st ' + (ok ? 'bios-st-ok' : 'bios-st-warn');
          stripVin.textContent = ok ? '[OK] VIN' : '[!] VIN';
        }
      });
  }

  var INSIGHT_SEEN_KEY = 'mulberry_hub_insight_seen_id';
  var SOFTSCORE_SEEN_KEY = 'mulberry_hub_softscore_insight_id';

  function insightAuthHeaders() {
    var t = getToken();
    var s = t != null ? String(t) : '';
    if (!s || s.indexOf('eyJ') !== 0 || s.length < 51) return null;
    return { Authorization: 'Bearer ' + s };
  }

  function applySoftScoreGauge(j) {
    var wrap = document.getElementById('exo-softscore-gauge');
    var fill = document.getElementById('exo-softscore-fill');
    var num = document.getElementById('exo-softscore-val');
    var eur = document.getElementById('exo-softscore-eur');
    var hint = document.getElementById('exo-softscore-hint');
    var srcEl = document.getElementById('exo-softscore-source');
    if (!wrap || !fill || !num || !eur || !hint) return;
    wrap.classList.remove('exo-softscore--high', 'exo-softscore--mid', 'exo-softscore--low');
    if (!j || j.softscore == null) {
      wrap.classList.remove('exo-softscore--pulse');
      fill.style.width = '0%';
      num.textContent = '—';
      eur.textContent = '';
      if (srcEl) srcEl.textContent = '';
      hint.textContent =
        'Autentifică-te cu JWT valid sau apasă „Actualizează” după ce ai o mașină în profil.';
      wrap.dataset.insightId = '';
      return;
    }
    var s = Number(j.softscore);
    var pct = Math.max(0, Math.min(100, s));
    fill.style.width = pct + '%';
    num.textContent = s.toFixed(2).replace('.', ',') + '%';
    var mv = j.market_value != null ? Number(j.market_value) : NaN;
    var cur = j.currency || 'EUR';
    eur.textContent = !isNaN(mv) ? '~' + mv + ' ' + cur : '';
    var base = j.market_base_eur != null ? Number(j.market_base_eur) : null;
    var bsrc = j.base_source ? String(j.base_source) : '';
    if (srcEl) {
      if (base != null && !isNaN(base) && bsrc) {
        srcEl.textContent = 'Preț bază ~' + base + ' ' + cur + ' · sursă ' + bsrc;
      } else if (bsrc) {
        srcEl.textContent = 'Sursă preț bază: ' + bsrc;
      } else {
        srcEl.textContent = '';
      }
    }
    if (s > 80) {
      wrap.classList.add('exo-softscore--high');
      hint.textContent =
        'Verde: profil favorabil pe uzură; valoarea estimată este apropiată de prețul de referință.';
    } else if (s >= 50) {
      wrap.classList.add('exo-softscore--mid');
      hint.textContent = 'Galben: uzură obișnuită pentru vârstă și kilometraj.';
    } else {
      wrap.classList.add('exo-softscore--low');
      hint.textContent =
        'Roșu: risc ridicat de costuri — verificare tehnică și buget reparații recomandate.';
    }
    var iid = j.insight_id != null ? String(j.insight_id) : '';
    wrap.dataset.insightId = iid;
    var seen = '';
    try {
      seen = sessionStorage.getItem(SOFTSCORE_SEEN_KEY) || '';
    } catch (e0) {}
    wrap.classList.toggle('exo-softscore--pulse', !!iid && iid !== seen);
  }

  function postSoftScoreRefresh() {
    var h = insightAuthHeaders();
    var wrap = document.getElementById('exo-softscore-gauge');
    if (!h) {
      showNotify('[!] SOFTSCORE // TOKEN_INVALID');
      return Promise.resolve();
    }
    if (wrap) wrap.classList.add('exo-softscore--loading');
    return fetch(apiBase() + '/me/vehicle/softscore/refresh', { method: 'POST', headers: h })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (j) {
        applySoftScoreGauge(j);
        try {
          if (j && j.insight_id != null) {
            sessionStorage.setItem(SOFTSCORE_SEEN_KEY, String(j.insight_id));
          }
        } catch (e1) {}
        try {
          refreshInsightIndicator();
        } catch (e2) {}
        showNotify('[OK] SOFTSCORE actualizat');
      })
      .catch(function () {
        showNotify('[!] SOFTSCORE // EROARE server');
      })
      .finally(function () {
        if (wrap) wrap.classList.remove('exo-softscore--loading');
      });
  }

  function refreshSoftScoreGauge(opts) {
    opts = opts || {};
    var wrap = document.getElementById('exo-softscore-gauge');
    if (!wrap) return;
    var h = insightAuthHeaders();
    if (!h) {
      applySoftScoreGauge(null);
      return;
    }
    fetch(apiBase() + '/me/vehicle/softscore/latest', { method: 'GET', headers: h })
      .then(function (r) {
        if (!r.ok) throw new Error('bad');
        return r.json();
      })
      .then(function (j) {
        if (!j || j.softscore == null) {
          if (opts.bootstrap) {
            var boot = '';
            try {
              boot = sessionStorage.getItem('mulberry_softscore_bootstrapped') || '';
            } catch (e0) {}
            if (!boot) {
              try {
                sessionStorage.setItem('mulberry_softscore_bootstrapped', '1');
              } catch (e1) {}
              return postSoftScoreRefresh();
            }
          }
        }
        applySoftScoreGauge(j || null);
      })
      .catch(function () {
        applySoftScoreGauge(null);
      });
  }

  function bindSoftScoreGauge() {
    var btn = document.getElementById('exo-softscore-refresh');
    if (btn) {
      btn.addEventListener('click', function () {
        postSoftScoreRefresh();
      });
    }
    var wrap = document.getElementById('exo-softscore-gauge');
    if (wrap) {
      wrap.addEventListener('click', function (ev) {
        if (ev.target && ev.target.closest && ev.target.closest('button')) return;
        try {
          var id = wrap.dataset && wrap.dataset.insightId;
          if (id) sessionStorage.setItem(SOFTSCORE_SEEN_KEY, id);
        } catch (e) {}
        wrap.classList.remove('exo-softscore--pulse');
      });
    }
  }

  function closeInsightPanel() {
    var ov = document.getElementById('exo-insight-overlay');
    var p = document.getElementById('exo-insight-panel');
    if (ov) {
      ov.hidden = true;
      ov.setAttribute('aria-hidden', 'true');
    }
    if (p) {
      p.hidden = true;
      p.setAttribute('aria-hidden', 'true');
    }
    try {
      var sh = document.getElementById('exo-sheet');
      if (sh && !sh.hidden) document.body.style.overflow = 'hidden';
      else document.body.style.overflow = '';
    } catch (e0) {
      document.body.style.overflow = '';
    }
  }

  function openInsightPanel(data) {
    var ov = document.getElementById('exo-insight-overlay');
    var pan = document.getElementById('exo-insight-panel');
    var meta = document.getElementById('exo-insight-meta');
    var qEl = document.getElementById('exo-insight-question');
    var rEl = document.getElementById('exo-insight-reply');
    if (!ov || !pan) return;
    if (meta) meta.textContent = data.created_at ? 'Salvat · ' + String(data.created_at) : '';
    if (qEl) qEl.textContent = data.question ? String(data.question) : '—';
    if (rEl) rEl.textContent = data.reply ? String(data.reply) : '';
    ov.hidden = false;
    ov.setAttribute('aria-hidden', 'false');
    pan.hidden = false;
    pan.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function markInsightSeen(id) {
    if (id == null) return;
    try {
      sessionStorage.setItem(INSIGHT_SEEN_KEY, String(id));
    } catch (e) {}
  }

  function refreshInsightIndicator() {
    var btn = document.getElementById('exo-insight-bulb');
    if (!btn) return;
    var h = insightAuthHeaders();
    if (!h) {
      btn.hidden = true;
      btn.classList.remove('exo-insight--pulse', 'exo-insight--has');
      return;
    }
    btn.hidden = false;
    fetch(apiBase() + '/me/vehicle/insights/latest', { method: 'GET', headers: h })
      .then(function (r) {
        if (!r.ok) throw new Error('bad');
        return r.json();
      })
      .then(function (j) {
        if (!j || j.latest_id == null) {
          btn.classList.remove('exo-insight--pulse', 'exo-insight--has');
          btn.dataset.latestId = '';
          return;
        }
        var id = j.latest_id;
        var w24 = !!j.within_24h;
        var seen = '';
        try {
          seen = sessionStorage.getItem(INSIGHT_SEEN_KEY) || '';
        } catch (e) {}
        btn.classList.toggle('exo-insight--has', true);
        btn.classList.toggle('exo-insight--pulse', w24 && String(id) !== seen);
        btn.dataset.latestId = String(id);
      })
      .catch(function () {
        btn.classList.remove('exo-insight--pulse', 'exo-insight--has');
        btn.dataset.latestId = '';
      });
  }

  function bindInsightHub() {
    var btn = document.getElementById('exo-insight-bulb');
    var ov = document.getElementById('exo-insight-overlay');
    var closeBtn = document.getElementById('exo-insight-close');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var h = insightAuthHeaders();
      if (!h) {
        showNotify('[!] INSIGHT // TOKEN_INVALID');
        return;
      }
      fetch(apiBase() + '/me/vehicle/insights/latest', { method: 'GET', headers: h })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (j) {
          if (!j || j.latest_id == null) {
            showNotify('[○] INSIGHT // NICIUN_RĂSPUNS_SALVAT');
            return;
          }
          markInsightSeen(j.latest_id);
          btn.classList.remove('exo-insight--pulse');
          openInsightPanel(j);
        })
        .catch(function () {
          showNotify('[!] INSIGHT // FETCH_ERROR');
        });
    });
    if (ov) ov.addEventListener('click', closeInsightPanel);
    if (closeBtn) closeBtn.addEventListener('click', closeInsightPanel);
  }

  function loadModeUI() {
    var m = 'eco';
    try {
      m = localStorage.getItem(LS_MODE) || 'eco';
    } catch (e) {}
    if (m !== 'eco' && m !== 'perf' && m !== 'sale') m = 'eco';
    document.querySelectorAll('.bios-mode-btn[data-mode]').forEach(function (btn) {
      btn.classList.toggle('is-active', btn.getAttribute('data-mode') === m);
    });
  }

  function bindMode() {
    document.querySelectorAll('.bios-mode-btn[data-mode]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var m = btn.getAttribute('data-mode');
        try {
          localStorage.setItem(LS_MODE, m);
        } catch (e) {}
        loadModeUI();
      });
    });
  }

  function setVerified(ok) {
    var el = document.getElementById('exo-verified-line');
    if (!el) return;
    if (ok) {
      el.textContent = '[● ACTIV]';
      el.classList.add('bios-accent-blink');
      el.style.color = '';
    } else {
      el.textContent = '[○ PENDING] COMPLETEAZĂ VIN ȘI DOCUMENTE';
      el.classList.remove('bios-accent-blink');
      el.style.color = 'var(--text-dim)';
    }
  }

  function setSheetHidden(hidden) {
    var ov = document.getElementById('exo-sheet-overlay');
    var sh = document.getElementById('exo-sheet');
    if (ov) {
      ov.hidden = hidden;
      ov.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    }
    if (sh) {
      sh.hidden = hidden;
      sh.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    }
    document.body.style.overflow = hidden ? '' : 'hidden';
  }

  function setPzPresentationHidden(hidden) {
    var ov = document.getElementById('pz-mulberry-qr-overlay');
    if (ov) {
      ov.hidden = !!hidden;
      ov.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    }
    document.body.style.overflow = hidden ? '' : 'hidden';
  }

  /** Filă nouă: landing PlayerZero — QR centrat, Magazin Play, Trimite mesaj. */
  function openMulberryQrLandingTab() {
    var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
    var mlbr = norm(v.ycr_id) || norm(v.mlbr_code) || deriveMulberryIndex(v);
    var base = demoPageBaseUrl();
    var q = new URLSearchParams();
    var profileUrl =
      buildProfilePathUrl(v) || buildMlbrPublicPageUrl(mlbr) || buildDemoUrlTiny(mlbr) || '';
    if (profileUrl) q.set('u', profileUrl);
    if (mlbr) q.set('mlbr', mlbr);
    var vin17 = onlyAZ09(v.vin);
    if (vin17) q.set('vin', vin17);
    var plate = norm(v.nr || v.plate).toUpperCase();
    if (plate) q.set('plate', plate);
    var path = 'mulberry_qr_landing.html?' + q.toString();
    if (base) window.open(base + path, '_blank', 'noopener,noreferrer');
    else window.open(path, '_blank', 'noopener,noreferrer');
  }

  function openMulberryQrPresentation() {
    var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
    var mlbr = norm(v.ycr_id) || norm(v.mlbr_code) || deriveMulberryIndex(v);
    var url =
      buildProfilePathUrl(v) ||
      buildMlbrPublicPageUrl(mlbr) ||
      buildDemoUrlTiny(mlbr) ||
      buildDemoUrlMinimal(v, mlbr) ||
      '';
    var mlbrEl = document.getElementById('pz-modal-mlbr');
    if (mlbrEl) mlbrEl.textContent = mlbr || '—';
    var prev = document.getElementById('pz-url-preview');
    if (prev) {
      prev.textContent =
        url ||
        '(Deschide HUB de pe http(s) — file:// nu poate genera link scanabil pe telefon.)';
    }
    initQrInEl('pz-modal-qr', v, mlbr, 104, 'light');
    setPzPresentationHidden(false);
    try {
      var cta = document.getElementById('pz-copy-qr-url');
      if (cta && url) cta.dataset.clipboardUrl = url;
    } catch (eC) {}
  }

  function closeMulberryQrPresentation() {
    setPzPresentationHidden(true);
  }

  function openSheet() {
    openMulberryQrLandingTab();
  }

  function closeSheet() {
    closeMulberryQrPresentation();
    setSheetHidden(true);
  }

  function fillDigitalSheet(v, mlbr) {
    var titleEl = document.getElementById('exo-sheet-title');
    var spec = document.getElementById('exo-sheet-specs');
    var vehTitle = [norm(v.marca), norm(v.series || v.serie), norm(v.model)].filter(Boolean).join(' · ');
    if (titleEl) titleEl.textContent = vehTitle || 'VEHICLE';
    if (spec) {
      spec.innerHTML =
        '<div class="bios-spec-row"><span class="bios-k">MLBR ID</span><span class="bios-pipe">│</span><span class="bios-v">' +
        esc(mlbr) +
        '</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">VIN</span><span class="bios-pipe">│</span><span class="bios-v">' +
        esc(onlyAZ09(v.vin) || '—') +
        '</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">PLATE</span><span class="bios-pipe">│</span><span class="bios-v">' +
        esc(norm(v.nr || v.plate).toUpperCase() || '—') +
        '</span></div>';
    }
  }

  function initQrInEl(id, v, mlbr, size, preset) {
    var wrap = document.getElementById(id);
    if (!wrap) return;
    if (!window.MulberryStyledQR && !window.QRCode) {
      wrap.textContent = 'QR N/A';
      if (window.mulberryBindQrTapOpen) window.mulberryBindQrTapOpen(wrap, '');
      return;
    }
    var light = preset === 'light';
    /* Același profil public ca pe main card: vehicle_present.html?m=… */
    var openUrl =
      buildProfilePathUrl(v) ||
      buildMlbrPublicPageUrl(mlbr) ||
      buildDemoUrlTiny(mlbr) ||
      buildDemoUrlMinimal(v, mlbr) ||
      '';
    var text = openUrl || profileQrPayload(v, mlbr);
    var px = size || 48;
    var bg = light ? '#f9f9f9' : '#F7D735';
    var fg = '#000000';
    var margin = light ? (px >= 100 ? 6 : 3) : px >= 100 ? 6 : 4;
    var labelBase =
      'Profil vehicul Mulberry — același link ca pe cardul principal. Apasă pentru a deschide în browser.';
    function afterPaint() {
      if (window.mulberryBindQrTapOpen) window.mulberryBindQrTapOpen(wrap, openUrl);
    }
    if (window.MulberryStyledQR && window.MulberryStyledQR.paint) {
      try {
        window.MulberryStyledQR.paint(wrap, text, {
          width: px,
          height: px,
          backgroundColor: bg,
          foregroundColor: fg,
          margin: margin,
          errorCorrectionLevel: 'L'
        });
        wrap.setAttribute('aria-label', labelBase);
        afterPaint();
        return;
      } catch (e0) {
        /* fallback mai jos */
      }
    }
    wrap.innerHTML = '';
    var opts = {
      text: text,
      width: px,
      height: px,
      colorDark: fg,
      colorLight: bg
    };
    if (window.QRCode && window.QRCode.CorrectLevel) {
      opts.correctLevel = window.QRCode.CorrectLevel.L;
    }
    try {
      new window.QRCode(wrap, opts);
      wrap.setAttribute('aria-label', labelBase);
    } catch (e1) {
      try {
        opts.text = buildDemoUrlMinimal(v, mlbr) || profileQrPayload(v, mlbr);
        if (window.QRCode && window.QRCode.CorrectLevel) {
          opts.correctLevel = window.QRCode.CorrectLevel.L;
        }
        new window.QRCode(wrap, opts);
        wrap.setAttribute('aria-label', labelBase);
      } catch (e2) {
        try {
          opts.text = digitalIdPayload(v, mlbr);
          new window.QRCode(wrap, opts);
          wrap.setAttribute('aria-label', labelBase);
        } catch (e3) {
          wrap.textContent = 'QR ERR';
          if (window.mulberryBindQrTapOpen) window.mulberryBindQrTapOpen(wrap, '');
          return;
        }
      }
    }
    afterPaint();
  }

  function bindPdfDownload() {
    var btn = document.getElementById('exo-hub-pdf');
    if (!btn) return;
    btn.addEventListener('click', function () {
      downloadKanbanLabelPdf();
    });
  }

  function telemetryFromVin(v) {
    var vin = onlyAZ09(v.vin) || 'NOVIN';
    var h = hash32(vin);
    return {
      health: 65 + (h % 28),
      engine: 75 + (h % 20),
      trans: 88 + (h % 10),
      brakes: 70 + (h % 18),
      susp: 82 + (h % 12),
      elec: 92 + (h % 8),
      emis: 58 + (h % 25),
      padF: 65 + (h % 30),
      padR: 72 + (h % 25),
      tireF: 58 + (h % 35),
      tireR: 62 + (h % 30),
      battery: 52 + (h % 40),
      fuelCity: (6.5 + (h % 20) / 10).toFixed(1),
      fuelHwy: (5.0 + (h % 15) / 10).toFixed(1),
      fuelComb: (6.2 + (h % 18) / 10).toFixed(1),
      co2gkm: 145 + (h % 40),
      coolant: 88 + (h % 8),
      oilP: (3.0 + (h % 10) / 10).toFixed(1),
      oilT: 92 + (h % 10),
      intake: 22 + (h % 15),
      fuelPct: 35 + (h % 50),
      fuelBar: (4.2 + (h % 8) / 10).toFixed(1),
      rangeKm: 280 + (h % 120),
      batV: (13.8 + (h % 8) / 10).toFixed(1),
      altA: 75 + (h % 25),
      o2v: (0.42 + (h % 8) / 100).toFixed(2),
      catT: 420 + (h % 80),
      maf: (4.0 + (h % 10) / 10).toFixed(1)
    };
  }

  function wearLine(label, pct) {
    return (
      '<div class="bios-spec-row"><span class="bios-k">' +
      esc(label) +
      '</span><span class="bios-pipe">│</span><span class="bios-v"><pre class="bios-charbar" style="display:inline;margin:0">' +
      esc(charBar(pct, 10)) +
      ' ' +
      pct +
      '%</pre></span></div>'
    );
  }

  function initHubTabs() {
    var tabs = document.querySelectorAll('.bios-tab[data-tab]');
    var map = {
      overview: document.getElementById('panel-overview'),
      diagnostics: document.getElementById('panel-diagnostics'),
      maintenance: document.getElementById('panel-maintenance'),
      economy: document.getElementById('panel-economy'),
      security: document.getElementById('panel-security'),
      archives: document.getElementById('panel-archives'),
      yourcar: document.getElementById('panel-yourcar')
    };
    tabs.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var name = btn.getAttribute('data-tab');
        tabs.forEach(function (b) {
          var on = b.getAttribute('data-tab') === name;
          b.classList.toggle('is-active', on);
          b.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        Object.keys(map).forEach(function (k) {
          var p = map[k];
          if (p) p.classList.toggle('is-active', k === name);
        });
      });
    });
  }

  function renderDiagnosticsTab(v, mlbr) {
    var t = telemetryFromVin(v);
    var overall = t.health;
    var barEl = document.getElementById('diag-overall-bar');
    var pctEl = document.getElementById('diag-overall-pct');
    if (barEl) barEl.textContent = charBar(overall, 10) + '  ' + overall + '%';
    if (pctEl) pctEl.textContent = overall + '%';

    var sub = document.getElementById('diag-subsystems');
    if (sub) {
      var rows = [
        ['ENGINE', t.engine],
        ['TRANSMISSION', t.trans],
        ['BRAKES', t.brakes],
        ['SUSPENSION', t.susp],
        ['ELECTRICAL', t.elec],
        ['EMISSIONS', t.emis]
      ];
      sub.innerHTML = rows
        .map(function (r) {
          return wearLine(r[0], r[1]);
        })
        .join('');
    }

    function liveHtmlShell() {
      return (
        '<div class="bios-spec-row"><span class="bios-k">COOLANT</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-coolant">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">OIL PRESS</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-oilp">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">OIL TEMP</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-oilt">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">INTAKE AIR</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-intake">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">FUEL LEVEL</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-fuel">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">FUEL PRESS</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-fuelp">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">RANGE EST</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-range">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">BATTERY</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-bat">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">ALT OUTPUT</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-alt">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">O2 B1</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-o2">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">CAT TEMP</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-cat">—</span></div>' +
        '<div class="bios-spec-row"><span class="bios-k">MAF</span><span class="bios-pipe">│</span><span class="bios-v" id="diag-live-maf">—</span></div>'
      );
    }

    function patchDiagLiveSensors(tt) {
      function set(id, txt) {
        var el = document.getElementById(id);
        if (el) el.textContent = txt;
      }
      set('diag-live-coolant', tt.coolant + '°C (NORMAL)');
      set('diag-live-oilp', tt.oilP + ' bar (OK)');
      set('diag-live-oilt', tt.oilT + '°C');
      set('diag-live-intake', tt.intake + '°C');
      set('diag-live-fuel', tt.fuelPct + '% (~' + Math.round((tt.fuelPct / 100) * 50) + ' L)');
      set('diag-live-fuelp', tt.fuelBar + ' bar');
      set('diag-live-range', '~' + tt.rangeKm + ' km');
      set('diag-live-bat', tt.batV + ' V (CHARGING)');
      set('diag-live-alt', tt.altA + ' A');
      set('diag-live-o2', tt.o2v + ' V');
      set('diag-live-cat', tt.catT + '°C');
      set('diag-live-maf', tt.maf + ' g/s');
    }

    var liveEl = document.getElementById('diag-live-sensors');
    if (liveEl) {
      liveEl.innerHTML = liveHtmlShell();
      patchDiagLiveSensors(telemetryFromVin(v));
      if (window._hubLiveTimer) clearInterval(window._hubLiveTimer);
      window._hubLiveTimer = setInterval(function () {
        if (liveEl && document.getElementById('panel-diagnostics') && document.getElementById('panel-diagnostics').classList.contains('is-active')) {
          patchDiagLiveSensors(telemetryFromVin(v));
        }
      }, 2000);
    }

    var dtcS = document.getElementById('diag-dtc-stored');
    if (dtcS) {
      dtcS.textContent =
        'P0420  Catalyst System Efficiency Below Threshold (Bank 1)\n' +
        '         First seen: 2024-02-10 · Status: PENDING (EXO)\n\n' +
        'P0171  System Too Lean (Bank 1)\n' +
        '         First seen: 2024-03-15 · Status: ACTIVE — CHECK SOON';
    }
    var dtcC = document.getElementById('diag-dtc-cleared');
    if (dtcC) {
      dtcC.textContent =
        'P0300  Random/Multiple Cylinder Misfire — Cleared: 2024-02-28 (after service)';
    }
  }

  function renderMaintenanceTab(v) {
    var km = estimateKmIfMissing(v);
    var t = telemetryFromVin(v);
    var pred = document.getElementById('maint-predict');
    if (pred) {
      pred.textContent = MSG_INTRODU_DATE;
    }
    var wear = document.getElementById('maint-wear');
    if (wear) {
      wear.innerHTML =
        wearLine('Brake Pads Front', t.padF) +
        wearLine('Brake Pads Rear', t.padR) +
        wearLine('Tires Front', t.tireF) +
        wearLine('Tires Rear', t.tireR) +
        wearLine('Battery Health', t.battery);
    }
    var tl = document.getElementById('maint-timeline');
    if (tl) {
      tl.textContent = MSG_INTRODU_DATE;
    }
  }

  function renderEconomyTab(v, mlbr) {
    var km = estimateKmIfMissing(v);
    var t = telemetryFromVin(v);
    var marca = norm(v.marca) || 'VEHICLE';
    var model = norm(v.model) || '';
    var fuel = document.getElementById('eco-fuel');
    if (fuel) {
      fuel.textContent =
        'CONSUMPTION (last 1000 km · sim):\n' +
        '  City:     ' +
        t.fuelCity +
        ' L/100km\n' +
        '  Highway:  ' +
        t.fuelHwy +
        ' L/100km\n' +
        '  Combined: ' +
        t.fuelComb +
        ' L/100km\n\n' +
        'CURRENT TANK (est):\n' +
        '  Fuel est:  ~' +
        Math.round((t.fuelPct / 100) * 50) +
        ' L · Distance since fill ~587 km';
    }
    var fleet = document.getElementById('eco-fleet');
    if (fleet) {
      fleet.textContent =
        'YOUR ' +
        marca.toUpperCase() +
        ' ' +
        model.toUpperCase() +
        ' vs FLEET AVG (demo):\n\n' +
        'Fuel economy:   ' +
        t.fuelComb +
        ' L/100km  (Fleet avg: 7.2)  [OK] better\n' +
        'Maint cost/yr:  ~1.200 RON (Fleet avg: 1.450) [OK]\n' +
        'Issues/year:    2 DTC (Fleet avg: 3.5) [OK]\n\n' +
        "YOU'RE IN TOP 25% (demo label)";
    }
    var carb = document.getElementById('eco-carbon');
    if (carb) {
      var lifetime = Math.round((km || 120000) * t.co2gkm / 1000);
      carb.textContent =
        'ENVIRONMENTAL (est):\n\n' +
        'CO2 lifetime: ~' +
        lifetime +
        ' kg\n' +
        'Last month CO2: ~189 kg (demo)\n' +
        'vs electric alt: -78% CO2 / month (indicativ)';
    }
    var marketEl = document.getElementById('eco-market');
    if (marketEl) marketEl.textContent = MSG_INTRODU_DATE;
    var vin = norm(v.vin);
    if (!vin) {
      if (marketEl) marketEl.textContent = MSG_INTRODU_DATE;
      return;
    }
    fetch(apiBase() + '/valuation/estimate?vin=' + encodeURIComponent(vin))
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!marketEl) return;
        var lo = data.estimated_value_lei != null ? Math.round(data.estimated_value_lei * 0.92) : 0;
        var hi = data.estimated_value_lei != null ? Math.round(data.estimated_value_lei * 1.08) : 0;
        var mid = data.estimated_value_lei || 0;
        marketEl.textContent =
          'ESTIMATED VALUE (API):\n\n' +
          'Range:     ' +
          lo.toLocaleString('ro-RO') +
          ' - ' +
          hi.toLocaleString('ro-RO') +
          ' RON\n' +
          'Mid / est: ' +
          mid.toLocaleString('ro-RO') +
          ' RON\n' +
          'Age years: ' +
          (data.age_years != null ? data.age_years : '—') +
          '\n' +
          'Delta mkt: ' +
          (data.delta_vs_market_lei != null ? data.delta_vs_market_lei : '—') +
          ' RON\n\n' +
          'Compared to listings: demo copy — full history in Vault [OK]';
      })
      .catch(function () {
        if (marketEl) marketEl.textContent = MSG_INTRODU_DATE;
      });
  }

  function renderSecurityTab(v) {
    var vin = onlyAZ09(v.vin) || '—';
    var el = document.getElementById('sec-detail');
    var vm = document.getElementById('sec-vin-match');
    if (vm) vm.textContent = vin.length === 17 ? '[OK] VIN MATCH' : '[!] VIN INCOMPLETE';
    if (el) {
      el.textContent =
        'VIN VERIFICATION:\n' +
        '  Registered VIN:  ' +
        vin +
        '\n' +
        '  OBD VIN (sim):   ' +
        vin +
        '\n' +
        '  Status:          ' +
        (vin.length === 17 ? 'AUTHENTIC' : 'PENDING') +
        '\n\n' +
        'IMMOBILIZER:   ACTIVE (demo)\n' +
        'ALARM:         ARMED (demo)\n' +
        'LAST UNLOCK:   2024-03-21 08:15:32 (demo)\n' +
        'GPS (demo):    44.4268 N, 26.1025 E · București\n\n' +
        'THEFT ALERTS:\n' +
        '  [OK] No unauthorized access (demo)\n' +
        '  [OK] VIN tampering: NONE';
    }
  }

  function bindYourCarActions() {
    var qrBtn = document.getElementById('act-share-qr');
    if (qrBtn) qrBtn.addEventListener('click', openSheet);
  }

  function loadSystemArchives() {
    var list = document.getElementById('archive-list');
    var noticeEl = document.getElementById('archive-notice');
    if (!list || !window.api || typeof window.api.listSystemArchives !== 'function') return;
    list.innerHTML = '<li class="bios-archive-li">SE ÎNCARCĂ…</li>';
    window.api
      .listSystemArchives()
      .then(function (data) {
        var n = data && data.notice;
        if (noticeEl) {
          noticeEl.textContent =
            n && (n.message || n.ARCHIVE_GENERATED)
              ? String(n.message || n.ARCHIVE_GENERATED)
              : '—';
        }
        var files = (data && data.files) || [];
        if (!files.length) {
          list.innerHTML = '<li class="bios-archive-li">Niciun fișier încă.</li>';
          return;
        }
        list.innerHTML = '';
        files.forEach(function (f) {
          var li = document.createElement('li');
          li.className = 'bios-archive-li';
          var d = new Date((f.mtime || 0) * 1000);
          var dateStr = isNaN(d.getTime()) ? '—' : d.toISOString().slice(0, 10);
          li.appendChild(document.createTextNode('[' + dateStr + '] > '));
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'bios-archive-btn';
          btn.textContent = f.name;
          btn.addEventListener('click', function () {
            if (window.api && typeof window.api.downloadArchiveFile === 'function') {
              window.api.downloadArchiveFile(f.rel_path).catch(function (e) {
                console.warn(e);
              });
            }
          });
          li.appendChild(btn);
          li.appendChild(document.createTextNode(' · ' + (f.size_bytes != null ? f.size_bytes + ' B' : '')));
          list.appendChild(li);
        });
      })
      .catch(function (e) {
        list.innerHTML =
          '<li class="bios-archive-li">[!] ' + String((e && e.message) || e) + '</li>';
      });
  }

  /**
   * Profil BIOS (/me/vehicles/profile): pe mulberry.html există modal + openMulberryPublicProfile;
   * din HUB (fără core.js) redirecționăm către mulberry.html?p={VIN} (parsat la bootstrap).
   */
  window.openCarProfile = function (vin) {
    var v = onlyAZ09(vin);
    if (v.length !== 17) return Promise.reject(new Error('VIN invalid'));
    if (typeof window.openMulberryPublicProfile === 'function') {
      return window.openMulberryPublicProfile(v);
    }
    try {
      window.location.href = 'mulberry.html?p=' + encodeURIComponent(v);
    } catch (e) {
      return Promise.reject(e);
    }
    return Promise.resolve();
  };

  window.showNotify = showNotify;

  /**
   * REFAC_CODE: POST /system/utils/clean-code (Fondator + JWT). Rezultat în preview; APPLY copiază în editor.
   */
  function setRefacStatus(line) {
    var st = document.getElementById('exo-refac-status');
    if (st) st.textContent = line != null ? String(line) : '';
  }

  window.triggerCodeClean = async function () {
    var refacBtn = document.getElementById('exo-refac-code');
    var ed = document.getElementById('developer-console');
    var prev = document.getElementById('developer-console-preview');
    var incReq = document.getElementById('dev-clean-include-req');
    var codeSnippet = ed ? ed.value : '';
    if (!String(codeSnippet).trim()) {
      showNotify('[!] INPUT_EMPTY // PASTE_SNIPPET_FIRST');
      setRefacStatus('[!] REFAC_IDLE // INPUT_EMPTY');
      return;
    }
    showNotify('[!] AI_CLEANUP_INITIATED // TARGET: CORE_LOGIC');
    setRefacStatus('[…] GROQ_PIPELINE // BUSY');
    if (refacBtn) refacBtn.disabled = true;
    if (prev) prev.value = '';
    try {
      if (!window.api || typeof window.api.cleanCodeSnippet !== 'function') {
        throw new Error('cleanCodeSnippet indisponibil (api_client)');
      }
      var resp = await window.api.cleanCodeSnippet(codeSnippet, !!(incReq && incReq.checked));
      if (resp && resp.status === 'SUCCESS' && resp.cleaned_code != null) {
        if (prev) {
          prev.value = String(resp.cleaned_code);
          try {
            prev.scrollTop = 0;
          } catch (eSc) {}
        }
        showNotify('[OK] CODE_OPTIMIZED // BY_GROQ · PREVIEW_READY');
        setRefacStatus('[OK] REFAC_COMPLETE // PREVIEW_UPDATED');
      } else {
        showNotify('[!] SYNC_ERROR: UNEXPECTED_RESPONSE');
        setRefacStatus('[!] REFAC_IDLE // BAD_RESPONSE');
      }
    } catch (e) {
      var m = e && e.message ? String(e.message) : 'ERR';
      showNotify('[!] REFAC_FAILED // ' + (m.length > 140 ? m.slice(0, 137) + '…' : m));
      setRefacStatus('[!] REFAC_IDLE // ERROR');
    } finally {
      if (refacBtn) refacBtn.disabled = false;
    }
  };

  /**
   * Emergency BIOS: golește preview REFAC, reactivează butonul dacă a rămas disabled (ex. tab închis în timpul fetch).
   * Consolă (F12): mulberryBiosEmergencyReset()
   * Hard refresh fără cache: Ctrl+Shift+R (browser).
   */
  window.mulberryBiosEmergencyReset = function () {
    var prev = document.getElementById('developer-console-preview');
    if (prev) prev.value = '';
    var refacBtn = document.getElementById('exo-refac-code');
    if (refacBtn) refacBtn.disabled = false;
    var st = document.getElementById('exo-refac-status');
    if (st) st.textContent = '[○] REFAC_IDLE // READY';
    showNotify('[!] CACHE_CLEARED // UI_STABILIZED');
  };

  document.addEventListener('DOMContentLoaded', function () {
    var haltRoot = document.getElementById('exo-security-halt');
    var haltBtn = document.getElementById('exo-halt-dismiss');
    if (haltBtn && haltRoot) {
      haltBtn.addEventListener('click', function () {
        haltRoot.hidden = true;
        haltRoot.setAttribute('aria-hidden', 'true');
      });
    }

    var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
    var mlbr = norm(v.ycr_id) || norm(v.mlbr_code) || deriveMulberryIndex(v);

    var idEl = document.getElementById('exo-mulberry-id');
    if (idEl) idEl.textContent = mlbr;

    var biosMlbr = document.getElementById('bios-row-mlbr');
    if (biosMlbr) biosMlbr.textContent = mlbr;

    var hv = document.getElementById('bios-hardware-vin');
    if (hv) hv.textContent = onlyAZ09(v.vin) || '—';

    var plateEl = document.getElementById('exo-plate');
    if (plateEl) plateEl.textContent = norm(v.nr || v.plate).toUpperCase() || '—';

    var mm = document.getElementById('exo-make-model');
    if (mm) {
      var mk = [norm(v.marca), norm(v.model)].filter(Boolean).join(' · ');
      mm.textContent = mk || '—';
    }

    var yr = document.getElementById('exo-year');
    if (yr) yr.textContent = norm(v.an) || '—';

    var fuel = document.getElementById('exo-fuel');
    if (fuel) fuel.textContent = norm(v.combustibil) || '—';

    var ser = document.getElementById('exo-series');
    if (ser) ser.textContent = norm(v.serie || v.series) || '—';

    var vinOk = onlyAZ09(v.vin).length === 17;
    setVerified(vinOk && (!!getToken() || !!(window.AppDB && window.AppDB.currentUser)));

    applyHardwareUI(v, []);

    initQrInEl('exo-qr', v, mlbr, 48);
    fillDigitalSheet(v, mlbr);

    var openBtn = document.getElementById('exo-open-sheet');
    if (openBtn) openBtn.addEventListener('click', openSheet);
    var scanHeader = document.getElementById('exo-scan-mulberry-qr');
    if (scanHeader) scanHeader.addEventListener('click', openMulberryQrLandingTab);
    var pzBack = document.getElementById('pz-mulberry-qr-backdrop');
    if (pzBack) pzBack.addEventListener('click', closeMulberryQrPresentation);
    var pzX = document.getElementById('pz-mulberry-qr-close');
    if (pzX) pzX.addEventListener('click', closeMulberryQrPresentation);
    var pzCopy = document.getElementById('pz-copy-qr-url');
    if (pzCopy) {
      pzCopy.addEventListener('click', function () {
        var u =
          (pzCopy.dataset && pzCopy.dataset.clipboardUrl) ||
          (document.getElementById('pz-url-preview') && document.getElementById('pz-url-preview').textContent) ||
          '';
        u = String(u || '').trim();
        if (!u || u.indexOf('(') === 0) return;
        var origHtml = pzCopy.innerHTML;
        function ok() {
          pzCopy.innerHTML = 'Copiat în clipboard';
          setTimeout(function () {
            pzCopy.innerHTML = origHtml;
          }, 2000);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(u).then(ok).catch(function () {});
        }
      });
    }
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closeMulberryQrPresentation();
    });
    document.getElementById('exo-sheet-overlay') &&
      document.getElementById('exo-sheet-overlay').addEventListener('click', closeSheet);
    document.getElementById('exo-sheet-close') &&
      document.getElementById('exo-sheet-close').addEventListener('click', closeSheet);
    document.getElementById('exo-sheet-arrow') &&
      document.getElementById('exo-sheet-arrow').addEventListener('click', function (ev) {
        ev.preventDefault();
        closeSheet();
      });
    window.closeMulberryVaultSheet = closeSheet;

    bindPdfDownload();

    initHubTabs();
    renderDiagnosticsTab(v, mlbr);
    renderMaintenanceTab(v);
    renderEconomyTab(v, mlbr);
    renderSecurityTab(v);
    bindYourCarActions();

    window.MulberryBiosExport = {
      downloadKanbanLabelPdf: downloadKanbanLabelPdf,
    };

    var vin = norm(v.vin);
    renderAdminFromDocs([]);
    fetchCloudList(vin, function () {});

    setHealthAnomalies(vin).catch(function () {});
    bindExoIntelligenceUI(vin);

    loadModeUI();
    bindMode();

    checkSync(vin);

    bindInsightHub();
    bindSoftScoreGauge();
    refreshInsightIndicator();
    refreshSoftScoreGauge({ bootstrap: true });
    try {
      setInterval(refreshInsightIndicator, 90000);
    } catch (eInt) {}
    try {
      setInterval(function () {
        refreshSoftScoreGauge({});
      }, 120000);
    } catch (eInt2) {}
    document.addEventListener('visibilitychange', function () {
      try {
        if (!document.hidden) {
          refreshInsightIndicator();
          refreshSoftScoreGauge({});
        }
      } catch (eVis) {}
    });

    var logoutBtn = document.getElementById('exo-logout');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () {
        try {
          localStorage.removeItem('yourcar_token');
        } catch (e) {}
        if (window.AppDB && typeof window.AppDB.logout === 'function') window.AppDB.logout();
        else {
          try {
            localStorage.removeItem('mulberry_current_session');
          } catch (e2) {}
          window.location.href = 'login.html';
        }
      });
    }

    var isFounder =
      (window.api && window.api.isFounder && window.api.isFounder()) ||
      localStorage.getItem('is_founder') === 'true';
    if (isFounder) {
      var tabArch = document.getElementById('tab-btn-archives');
      if (tabArch) tabArch.removeAttribute('hidden');
      loadSystemArchives();
      var arRef = document.getElementById('archive-refresh');
      var arGen = document.getElementById('archive-generate');
      if (arRef) arRef.addEventListener('click', loadSystemArchives);
      if (arGen) {
        arGen.addEventListener('click', function () {
          if (window.api && typeof window.api.generateDailyArchive === 'function') {
            window.api
              .generateDailyArchive()
              .then(function () {
                loadSystemArchives();
              })
              .catch(function (e) {
                console.warn(e);
              });
          }
        });
      }
      var regCard = document.getElementById('exo-registry-card');
      if (regCard) regCard.removeAttribute('hidden');
      var devCard = document.getElementById('exo-dev-console-card');
      if (devCard) devCard.removeAttribute('hidden');
      var refacBtn = document.getElementById('exo-refac-code');
      var applyPrevBtn = document.getElementById('exo-refac-apply-preview');
      if (refacBtn && !refacBtn._exoRefacBound) {
        refacBtn._exoRefacBound = true;
        refacBtn.addEventListener('click', function () {
          if (typeof window.triggerCodeClean === 'function') window.triggerCodeClean();
        });
      }
      if (applyPrevBtn && !applyPrevBtn._exoApplyBound) {
        applyPrevBtn._exoApplyBound = true;
        applyPrevBtn.addEventListener('click', function () {
          var p = document.getElementById('developer-console-preview');
          var e2 = document.getElementById('developer-console');
          if (p && e2 && String(p.value).trim()) {
            e2.value = p.value;
            showNotify('[OK] PREVIEW_APPLIED // EDITOR (verifică înainte de commit)');
          } else {
            showNotify('[!] PREVIEW_EMPTY // RUN_REFAC_FIRST');
          }
        });
      }
      function loadRegistry() {
        var st = document.getElementById('exo-registry-status');
        var veh = document.getElementById('exo-registry-vehicles');
        if (st) st.textContent = MSG_INTERNAL_UPDATE;
        if (veh) veh.textContent = MSG_INTERNAL_UPDATE;
      }
      loadRegistry();
      document.getElementById('exo-registry-refresh') &&
        document.getElementById('exo-registry-refresh').addEventListener('click', loadRegistry);
    }

    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') {
        closeInsightPanel();
        closeSheet();
      }
    });

    try {
      if (new URLSearchParams(window.location.search).get('scan') === '1') {
        setTimeout(function () {
          openMulberryQrLandingTab();
        }, 350);
      }
    } catch (eScan) {}
  });
})();
