/* js/offline/appDB.js — LocalBase (Centralizatorul de logică) */

(function() {
  if (typeof window.AppDB !== 'undefined') return;

  // ── Guard împotriva buclelor ──
  var _syncDashboardPending = false;
  var _syncCorePending      = false;
  var _authRedirecting      = false;
  var _persistTimer         = null;

  /**
   * Ascunde doar overlay-uri dedicate dashboard-ului.
   * NU include #mulberry-profile-loading (e folosit de core.js; display:none aici îl lasă invizibil la hidden=false).
   * NU face sweep pe clase cu „loading” — .auth-btn-loading, .auth-loading-dots etc. ar dispărea din UI.
   */
  function _hideLoadingUiSafety(reason) {
    reason = reason || 'unknown';
    var primary = null;
    var candidates = [
      'bios-loading-overlay',
      'dash-loading-overlay',
      'loading',
    ];
    for (var c = 0; c < candidates.length; c++) {
      primary = document.getElementById(candidates[c]);
      if (primary) break;
    }
    if (!primary) {
      try {
        primary = document.querySelector('.bios-loading') || document.querySelector('.loading-overlay');
      } catch (eQ) {}
    }

    console.log(
      '[AppDB] loadingEl (overlay dashboard):',
      primary ? { id: primary.id || '(fără id)', className: primary.className, tag: primary.tagName } : null,
      '| reason:',
      reason
    );

    if (!primary) {
      if (typeof console.debug === 'function') {
        console.debug(
          '[AppDB] Fără overlay dedicat (bios-loading-overlay / dash-loading-overlay / #loading / .bios-loading / .loading-overlay). Normal pe mulberry.html fără astfel de nod.'
        );
      }
    } else {
      try {
        console.log('[AppDB] loadingEl înainte de hide:', {
          id: primary.id,
          display: primary.style.display,
          computedDisplay: typeof getComputedStyle === 'function' ? getComputedStyle(primary).display : 'n/a',
          hidden: primary.hidden,
        });
      } catch (eDiag) {}
      try {
        primary.style.display = 'none';
        primary.setAttribute('hidden', 'true');
        primary.style.pointerEvents = 'none';
      } catch (e1) {}
    }
  }

  var AppDB = {
    /** Cod MLBR stabil din VIN (SHA-256 → MLBR-XXXX-XXXX), aliniat la backend/database.py */
    mlbrCodeFromVin: async function (vin) {
      var v = String(vin || '').trim().toUpperCase().replace(/\s/g, '');
      if (!v) return 'MLBR-0000-0000';
      var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(v));
      var hex = Array.from(new Uint8Array(buf)).map(function (b) {
        return b.toString(16).padStart(2, '0');
      }).join('');
      return 'MLBR-' + hex.slice(0, 4).toUpperCase() + '-' + hex.slice(4, 8).toUpperCase();
    },

    currentUser: (function() {
      try {
        var raw = null;
        try {
          if (typeof window !== 'undefined' && window.MULBERRY_TAB_SESSION_ONLY) {
            raw = sessionStorage.getItem('mulberry_current_session') || localStorage.getItem('mulberry_current_session');
          } else {
            raw = localStorage.getItem('mulberry_current_session') || sessionStorage.getItem('mulberry_current_session');
          }
        } catch (e0) {
          raw = localStorage.getItem('mulberry_current_session');
        }
        return JSON.parse(raw || 'null');
      } catch (e) { return null; }
    })(),

    // ────────────────────────────────────────
    // 1) AUTH
    // ────────────────────────────────────────
    async login(email, password) {
      console.log('[AppDB] Tentativă login pentru:', email);
      var session = {
        id: 'user_' + Date.now(),
        email: email || 'offline@mulberry.local',
        name: 'Șofer Mulberry'
      };
      try { localStorage.setItem('mulberry_current_session', JSON.stringify(session)); } catch (e) {}
      this.currentUser = session;
      return session;
    },

    async logout() {
      localStorage.removeItem('mulberry_current_session');
      try {
        localStorage.removeItem('mulberry_session');
        localStorage.removeItem('yourcar_token');
        localStorage.removeItem('is_founder');
      } catch (e) {}
      this.currentUser = null;
      window.location.href = 'mulberry.html';
    },

    // ────────────────────────────────────────
    // 2) VEHICUL
    // ────────────────────────────────────────
    async registerVehicle(vehicleData) {
      if (!this.currentUser) return { error: 'Nu ești logat!' };

      var payload = Object.assign(
        { userId: this.currentUser.id, timestamp: new Date().toISOString() },
        vehicleData || {}
      );
      if (!payload.mlbr_code) {
        payload.mlbr_code = await this.mlbrCodeFromVin(payload.vin || '');
      }

      this.saveVehicle(payload);

      console.log('[AppDB] Vehicul înregistrat local:', payload);

      // Sync server async — nu blochează UI
      this.insert('vehicule', payload).catch(function(e) {
        console.warn("Sync server eșuat, rămâne local.");
      });

      // Sync Core după 500ms — o singură dată
      setTimeout(function() {
        window.AppDB.syncWithCore().then(function(analysis) {
          if (analysis) console.log('[AppDB] Vehicul sincronizat cu Core:', analysis);
        });
      }, 500);

      // Salvare în backend (PUT /cars)
      var token = window.api && window.api.getToken ? window.api.getToken() : '';
      if (token && token.startsWith('eyJ') && window.api && typeof window.api.upsertCar === 'function') {
        var mlbr = payload.mlbr_code || '';
        var backendPayload = {
          make:   payload.marca   || payload.make,
          model:  payload.model,
          year:   payload.an      || payload.year,
          fuel:   payload.combustibil || payload.fuel,
          plate:  payload.nr      || payload.plate,
          vin:    payload.vin,
          series: payload.serie   || payload.series,
          mlbr_code: mlbr,
          ycr_code: mlbr,
        };
        try { await window.api.upsertCar(backendPayload); }
        catch (e) { console.warn('[AppDB] upsertCar eșuat:', e); }
      }

      return payload;
    },

    getSavedVehicle: function() {
      if (!this.currentUser) return {};
      try {
        return JSON.parse(
          localStorage.getItem('mulberry_vehicle_' + this.currentUser.id) || '{}'
        );
      } catch (e) { return {}; }
    },

    /** Salvează vehiculul local (merge) și sincronizează spre dev.db când există JWT + VIN valid. */
    saveVehicle: function(partial) {
      if (!this.currentUser) return;
      var cur = this.getSavedVehicle() || {};
      var next = Object.assign({}, cur, partial || {});
      try {
        localStorage.setItem('mulberry_vehicle_' + this.currentUser.id, JSON.stringify(next));
      } catch (e) { console.error('Eroare salvare vehicul local'); }
      this._schedulePersistBackend();
    },

    _schedulePersistBackend: function() {
      var self = this;
      if (_persistTimer) clearTimeout(_persistTimer);
      _persistTimer = setTimeout(function() {
        _persistTimer = null;
        var token = localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '';
        if (!token || token.indexOf('eyJ') !== 0) return;
        var v = self.getSavedVehicle();
        if (!v || !v.vin || String(v.vin).trim().length !== 17) return;
        if (window.api && typeof window.api.syncVehicleFromLocalStorage === 'function') {
          window.api.syncVehicleFromLocalStorage().catch(function(e) { console.warn('[AppDB] persist backend:', e); });
        }
      }, 800);
    },

    mergeVehicleFromServer: async function(car) {
      if (!this.currentUser || !car) return;
      var vin = (car.vin || '').toUpperCase();
      if (!vin) return;
      var existing = this.getSavedVehicle() || {};
      var mlbr = (car.mlbr_code && String(car.mlbr_code).trim()) || existing.mlbr_code;
      if (!mlbr) {
        try {
          mlbr = await this.mlbrCodeFromVin(vin);
        } catch (e) {
          mlbr = 'MLBR-0000-0000';
        }
      }
      var merged = {
        userId:      this.currentUser.id,
        timestamp:   new Date().toISOString(),
        marca:       car.make    || existing.marca  || '',
        model:       car.model   || existing.model  || '',
        vin:         vin,
        nr:          (car.plate  || car.nr    || existing.nr    || '').toUpperCase(),
        plate:       car.plate   || existing.plate  || existing.nr || '',
        combustibil: car.fuel    || existing.combustibil || '',
        an:          car.year != null ? String(car.year) : (existing.an || ''),
        serie:       car.series  || existing.serie  || '',
        mlbr_code:   mlbr,
      };
      this.saveVehicle(merged);
      console.log('[AppDB] Vehicul restaurat din backend:', merged);
    },

    // ────────────────────────────────────────
    // 3) BACKEND
    // ────────────────────────────────────────
    insert: async function(table, data) {
      console.log('[AppDB] Trimitere către server (' + table + ')...');
      try {
        var response = await fetch('/form/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ table: table, data: data || {}, timestamp: new Date().toISOString() }),
        });
        return await response.json();
      } catch (err) {
        console.warn('[AppDB] Server offline. Datele sunt securizate local.');
        var offlineKey = 'mulberry_offline_' + table + '_' + Date.now();
        try { localStorage.setItem(offlineKey, JSON.stringify(data || {})); } catch (e) {}
        return { status: 'offline-saved', key: offlineKey };
      }
    },

    syncWithCore: async function() {
      // ── Guard: un singur sync simultan ──
      if (_syncCorePending) {
        console.log('[AppDB] syncWithCore deja în curs, skip.');
        return null;
      }

      var vehicle = this.getSavedVehicle();
      if (!vehicle || !vehicle.vin) {
        console.warn('[AppDB] Nu există VIN pentru sync.');
        return null;
      }

      // ── Verifică token înainte de orice fetch ──
      var token = localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '';
      if (!token || !token.startsWith('eyJ')) {
        console.warn('[AppDB] syncWithCore: token non-JWT, skip.');
        return null;
      }

      _syncCorePending = true;
      try {
        var apiBase = (window.Config && window.Config.apiBaseUrl) || 'http://127.0.0.1:9000';
        var response = await fetch(apiBase + '/sync', {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': 'Bearer ' + token,
          },
          body: JSON.stringify({
            vin:          vehicle.vin,
            owner_email:  this.currentUser ? this.currentUser.email : null,
            cloud_files:  vehicle.cloud_files  || [],
            reminders:    vehicle.reminders    || [],
            force_recalc: true,
          }),
          signal: AbortSignal.timeout ? AbortSignal.timeout(8000) : undefined,
        });

        if (!response.ok) {
          // 401 → token expirat → curăță fără redirect în buclă
          if (response.status === 401) {
            console.warn('[AppDB] syncWithCore 401 — token expirat.');
            _handleExpiredToken();
          }
          return null;
        }

        var analysis = await response.json();
        console.log('[AppDB] Analiză primită:', analysis);

        // Actualizează local
        vehicle.soft_score    = analysis.soft_score;
        vehicle.status_health = analysis.status_health;
        if (this.currentUser) {
          this.saveVehicle({ soft_score: vehicle.soft_score, status_health: vehicle.status_health });
        }

        return analysis;
      } catch (err) {
        console.warn('[AppDB] Sync cu backend eșuat (offline mode):', err.message || err);
        try {
          _hideLoadingUiSafety('syncWithCore.catch');
        } catch (eH) {}
        return null;
      } finally {
        _syncCorePending = false;
      }
    },

    // ────────────────────────────────────────
    // 4) UI
    // ────────────────────────────────────────
    ui: {
      goTo: function(page) { window.location.href = page; },
      show: function(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'block';
      },

      syncDashboard: function() {
        // ── Guard: nu rula de mai multe ori simultan ──
        if (_syncDashboardPending) return;
        _syncDashboardPending = true;

        try {
          var vehicle = window.AppDB.getSavedVehicle();
          var user    = window.AppDB.currentUser;

          function norm(s) { return (s == null ? '' : String(s)).trim(); }
          function onlyAZ09(s) { return norm(s).toUpperCase().replace(/[^A-Z0-9]/g, ''); }
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
            var vin    = onlyAZ09(v && v.vin);
            var series = onlyAZ09(v && (v.series || v.serie));
            var seed   = vin + '|' + series;
            var num    = (hash32(seed) % 9000) + 1000;
            var letters = pickLetters(series || vin, 2);
            var digits  = pickDigits(vin.slice(-6), 2);
            if (!digits || digits === '00')
              digits = String(hash32(seed) % 100).padStart(2, '0');
            return 'MLBR ' + String(num) + ' - ' + letters + digits;
          }

          // Header user
          var userFullNameEl = document.getElementById('user-full-name');
          if (userFullNameEl) userFullNameEl.textContent = user ? (user.name || user.email || 'Guest') : 'Guest';
          var userEmailEl = document.getElementById('user-email');
          if (userEmailEl) userEmailEl.textContent = user ? (user.email || '') : '';

          // Card ID: marcă, model sub marcă, VIN, nr., MLBR (cod persistent, generat o singură dată)
          var marca = norm(vehicle.marca);
          var modelName = norm(vehicle.model);
          var ser = norm(vehicle.series || vehicle.serie);
          var brandEl = document.getElementById('d-car-brand');
          var modelEl = document.getElementById('d-car-title');
          if (brandEl) {
            if (marca) {
              brandEl.textContent = marca.toUpperCase();
            } else if (modelName) {
              brandEl.textContent = modelName.toUpperCase();
            } else if (ser) {
              brandEl.textContent = ser.toUpperCase();
            } else {
              brandEl.textContent = '—';
            }
          }
          if (modelEl) {
            if (marca && modelName) {
              modelEl.textContent = modelName;
            } else if (!marca && modelName) {
              modelEl.textContent = modelName;
            } else {
              modelEl.textContent = '';
            }
          }

          var vinSubEl = document.getElementById('d-vin-subtle');
          if (vinSubEl) vinSubEl.textContent = onlyAZ09(vehicle.vin) || '—';

          var mlbrStored = norm(vehicle.mlbr_code) || norm(vehicle.ycr_id);
          var mlbrFinal = mlbrStored;
          if (!mlbrFinal) {
            mlbrFinal = deriveMulberryIndex(vehicle);
            var uidMlbr = window.AppDB.currentUser && window.AppDB.currentUser.id;
            if (uidMlbr) {
              try {
                var mergedV = Object.assign({}, window.AppDB.getSavedVehicle(), { mlbr_code: mlbrFinal });
                localStorage.setItem('mulberry_vehicle_' + uidMlbr, JSON.stringify(mergedV));
              } catch (e) {}
            }
          }

          var idxEl = document.getElementById('d-mlbr-index');
          if (idxEl) idxEl.textContent = mlbrFinal;

          var plateSubEl = document.getElementById('d-plate-sub');
          if (plateSubEl) {
            var plate = norm(vehicle.nr || vehicle.plate);
            plateSubEl.textContent = plate ? plate.toUpperCase() : '—';
          }

          // SoftScore preview — aceeași sursă ca Mulberry Hub: GET /me/vehicle/softscore/latest (+ bootstrap ca Hub)
          var vin = (vehicle.vin || '').trim();
          var priceEl = document.getElementById('d-softscore-preview-price');
          var pctEl   = document.getElementById('d-softscore-preview-pct');
          var updEl   = document.getElementById('d-softscore-preview-updated');
          var deprEl  = document.getElementById('d-softscore-preview-depr');

          function previewSoftScoreLine(sc) {
            return (typeof sc === 'number' && !isNaN(sc))
              ? ('SoftScore ' + sc.toFixed(1).replace('.', ',') + '%')
              : 'SoftScore —%';
          }
          function previewSoftScoreDualLine(hubSc, cloudSc) {
            var parts = [];
            if (typeof hubSc === 'number' && !isNaN(hubSc)) {
              parts.push('Mulberry ' + hubSc.toFixed(1).replace('.', ',') + '%');
            }
            if (typeof cloudSc === 'number' && !isNaN(cloudSc)) {
              parts.push('Client ' + cloudSc.toFixed(1).replace('.', ',') + '%');
            }
            if (!parts.length) return previewSoftScoreLine(null);
            return parts.join(' · ');
          }
          function updateAssistantSoftLine(hubSc, cloudSc) {
            var asSoftEl = document.getElementById('d-assistant-preview-soft');
            if (!asSoftEl) return;
            if (typeof hubSc === 'number' && typeof cloudSc === 'number' && !isNaN(hubSc) && !isNaN(cloudSc)) {
              asSoftEl.textContent = previewSoftScoreDualLine(hubSc, cloudSc);
            } else if (typeof hubSc === 'number' && !isNaN(hubSc)) {
              asSoftEl.textContent = previewSoftScoreLine(hubSc);
            } else if (typeof cloudSc === 'number' && !isNaN(cloudSc)) {
              asSoftEl.textContent = previewSoftScoreLine(cloudSc);
            } else {
              asSoftEl.textContent = previewSoftScoreLine(null);
            }
          }

          if (priceEl && pctEl) {
            var sc0 = vehicle.soft_score;
            pctEl.textContent = previewSoftScoreLine(sc0);
            updateAssistantSoftLine(sc0, null);

            var token =
              localStorage.getItem('mulberry_session') ||
              localStorage.getItem('yourcar_token') ||
              '';
            var tokenOk = token && token.indexOf('eyJ') === 0 && String(token).length >= 51;

            function fetchValuationExtras(hubScFromHub) {
              if (!vin || !tokenOk) return;
              var apiRoot = (window.Config && window.Config.apiBaseUrl) || 'http://127.0.0.1:9000';
              apiRoot = String(apiRoot || '').trim().replace(/\/+$/, '');
              fetch(
                apiRoot + '/valuation/estimate?vin=' + encodeURIComponent(vin) + '&live_market=1',
                { headers: { Authorization: 'Bearer ' + token } }
              )
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(data) {
                  if (!data) return;
                  var EUR_RATE = 5.0;
                  if (!priceEl.dataset.hubLine && typeof data.estimated_value_lei === 'number' && priceEl) {
                    priceEl.textContent = Math.round(data.estimated_value_lei / EUR_RATE)
                      .toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' €';
                  }
                  if (typeof data.annual_depreciation === 'number' && deprEl) {
                    deprEl.textContent = '-' + Math.round(Math.abs(data.annual_depreciation * 100)) + '% / an · market value';
                  }
                  if (data.price_last_updated && updEl && !updEl.dataset.hubTs) {
                    updEl.textContent = 'Actualizat săptămânal · ' + data.price_last_updated;
                  }
                  var hubSc =
                    typeof hubScFromHub === 'number' && !isNaN(hubScFromHub)
                      ? hubScFromHub
                      : null;
                  var cloudSc = data.soft_score != null ? Number(data.soft_score) : null;
                  if (cloudSc != null && isNaN(cloudSc)) cloudSc = null;
                  if (pctEl) {
                    pctEl.textContent = previewSoftScoreDualLine(hubSc, cloudSc);
                    updateAssistantSoftLine(hubSc, cloudSc);
                  }
                })
                .catch(function() { /* silent */ });
            }

            if (vin && tokenOk && window.MulberrySoftScoreHub) {
              window.MulberrySoftScoreHub.ensureLatestWithBootstrap({ bootstrap: true }).then(function(j) {
                var hubScPass = null;
                if (j && j.softscore != null) {
                  var scn = Number(j.softscore);
                  if (!isNaN(scn)) {
                    hubScPass = scn;
                    pctEl.textContent = previewSoftScoreLine(scn);
                    updateAssistantSoftLine(scn, null);
                    if (window.AppDB && typeof window.AppDB.saveVehicle === 'function') {
                      window.AppDB.saveVehicle({ soft_score: scn });
                    }
                  }
                  var mv = j.market_value;
                  var cur = j.currency || 'EUR';
                  if (typeof mv === 'number' && !isNaN(mv) && priceEl) {
                    var rounded = Math.abs(mv - Math.round(mv)) < 1e-6 ? Math.round(mv) : Math.round(mv * 10) / 10;
                    priceEl.textContent = '~' + String(rounded).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' ' + cur;
                    priceEl.dataset.hubLine = '1';
                  }
                  if (updEl && j.created_at) {
                    var ts = String(j.created_at).replace('T', ' ');
                    updEl.textContent = 'Evaluare Hub · ' + ts.slice(0, 16);
                    updEl.dataset.hubTs = '1';
                  }
                }
                fetchValuationExtras(hubScPass);
              });
            } else {
              fetchValuationExtras(null);
            }
          }

          /* Assistant card: ultima întrebare din chat (SoftScore e sincron mai sus cu Hub) */
          var asChatEl = document.getElementById('d-assistant-preview-last');
          if (asChatEl) {
            var chatSnip = '';
            try {
              var rawConv = localStorage.getItem('mulberry_conversations');
              if (rawConv) {
                var convList = JSON.parse(rawConv);
                if (Array.isArray(convList) && convList.length) {
                  var sortedConv = convList.slice().sort(function(a, b) {
                    return new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0);
                  });
                  outerChat: for (var ic = 0; ic < sortedConv.length; ic++) {
                    var mlist = sortedConv[ic].messages || [];
                    for (var jm = mlist.length - 1; jm >= 0; jm--) {
                      if (mlist[jm].role === 'user' && mlist[jm].content) {
                        chatSnip = String(mlist[jm].content).trim().replace(/\s+/g, ' ');
                        if (chatSnip.length > 52) chatSnip = chatSnip.slice(0, 49) + '…';
                        break outerChat;
                      }
                    }
                  }
                }
              }
            } catch (eChat) {}
            asChatEl.textContent = chatSnip
              ? ('Ultima întrebare: ' + chatSnip)
              : 'Întreabă despre întreținere, DTC…';
          }

          // QR — URL public Digital File (negru pe galben neon), corectură H
          function toCanonicalMlbrId(s) {
            return String(s || '').trim().replace(/\s+/g, '-').replace(/-+/g, '-');
          }
          function mlbrDigitalFileQrUrl(mlbrId) {
            var base =
              (window.Config && window.Config.mlbrPublicBase) ||
              window.API_BASE ||
              (window.Config && window.Config.apiBaseUrl) ||
              'http://127.0.0.1:9000';
            base = String(base || '').trim();
            if (!base || base === 'undefined' || base === 'null') base = 'http://127.0.0.1:9000';
            var path =
              (window.Config && window.Config.mlbrScanPage) ||
              'vehicle_present.html';
            var id = toCanonicalMlbrId(mlbrId);
            /* ?m= — URL mai scurt → mai puține module, puncte mai „mari” la același pixel */
            return String(base).replace(/\/$/, '') + '/' + path.replace(/^\//, '') + '?m=' + encodeURIComponent(id);
          }
          /** QR unic: /p/{VIN} → modal BIOS; fallback MLBR dacă VIN incomplet. */
          function mulberryProfileQrUrl(vehicle) {
            var base =
              (window.Config && window.Config.mlbrPublicBase) ||
              window.API_BASE ||
              (window.Config && window.Config.apiBaseUrl) ||
              'http://127.0.0.1:9000';
            base = String(base || '').trim().replace(/\/$/, '');
            if (!base || base === 'undefined' || base === 'null') base = 'http://127.0.0.1:9000';
            var vin = onlyAZ09(vehicle && vehicle.vin);
            if (vin.length === 17) {
              return base + '/p/' + vin;
            }
            var mid = toCanonicalMlbrId((vehicle && (vehicle.mlbr_code || vehicle.ycr_id)) || '');
            if (mid) return mlbrDigitalFileQrUrl(mid);
            return null;
          }
          function paintMlbrQr(qrEl, mlbrId) {
            if (!qrEl) return;
            var veh = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
            var url = mulberryProfileQrUrl(veh) || (mlbrId ? mlbrDigitalFileQrUrl(mlbrId) : null);
            if (!url) return;
            /* QR stilizat (module rotunjite, galben referință) — vezi mulberry_styled_qr.js */
            if (window.MulberryStyledQR && window.MulberryStyledQR.paint) {
              window.MulberryStyledQR.paint(qrEl, url, {
                width: 48,
                height: 48,
                backgroundColor: '#F7D735',
                foregroundColor: '#000000',
                margin: 4,
                errorCorrectionLevel: 'L'
              });
              return;
            }
            if (!window.QRCode) return;
            qrEl.innerHTML = '';
            var opts = {
              text: url,
              width: 48,
              height: 48,
              colorDark: '#000000',
              colorLight: '#F7D735'
            };
            if (window.QRCode.CorrectLevel) opts.correctLevel = window.QRCode.CorrectLevel.L;
            new window.QRCode(qrEl, opts);
          }
          function bindMainCardQrTap(qrNode, mlbrId) {
            var wrap = qrNode && qrNode.parentElement;
            if (!wrap) return;
            var veh = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
            var u = mulberryProfileQrUrl(veh) || (mlbrId ? mlbrDigitalFileQrUrl(mlbrId) : '');
            if (window.mulberryBindQrTapOpen) window.mulberryBindQrTapOpen(wrap, u);
          }
          var qrEl = document.getElementById('qrcode-mini');
          paintMlbrQr(qrEl, mlbrFinal);
          bindMainCardQrTap(qrEl, mlbrFinal);

          // Fișier MLBR pe server (o singură dată) — actualizează ID + QR
          (function mlbrEnsureDigitalFile() {
            var tok = localStorage.getItem('mulberry_session') || '';
            var v = (vehicle.vin || '').trim();
            if (!v || !tok || !tok.startsWith('eyJ')) return;
            var tryKey = 'mlbr_gen_tried_' + v;
            if (sessionStorage.getItem(tryKey)) return;
            var apiB = (window.Config && window.Config.apiBaseUrl) || 'http://127.0.0.1:9000';
            fetch(apiB + '/mlbr/generate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok },
              body: JSON.stringify({ vin: v })
            })
              .then(function(r) {
                if (!r.ok) return null;
                return r.json();
              })
              .then(function(data) {
                if (!data || !data.mlbr_file || !data.mlbr_file.mlbr_id) return;
                sessionStorage.setItem(tryKey, '1');
                var mid = data.mlbr_file.mlbr_id;
                var uid = window.AppDB.currentUser && window.AppDB.currentUser.id;
                if (uid) {
                  try {
                    var merged = Object.assign({}, window.AppDB.getSavedVehicle(), { mlbr_code: mid, ycr_id: mid });
                    localStorage.setItem('mulberry_vehicle_' + uid, JSON.stringify(merged));
                  } catch (e1) {}
                }
                var idx = document.getElementById('d-mlbr-index');
                if (idx) idx.textContent = mid;
                var qm = document.getElementById('qrcode-mini');
                paintMlbrQr(qm, mid);
                bindMainCardQrTap(qm, mid);
              })
              .catch(function() { /* backend offline */ });
          })();

          // Digital Twin alert
          (function syncTwinAlert() {
            var el = document.getElementById('digital-twin-alert');
            if (!el) return;
            function esc(s) {
              return String(s == null ? '' : s)
                .replace(/&/g,'&amp;').replace(/</g,'&lt;')
                .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
            }
            try {
              var raw = sessionStorage.getItem('mulberry_twin_alert');
              if (!raw) { el.style.display = 'none'; el.innerHTML = ''; return; }
              var a = JSON.parse(raw);
              el.style.display = 'block';
              el.innerHTML =
                '<strong style="color:var(--neon);">' + esc(a.title) + '</strong>' +
                '<div style="margin-top:6px;opacity:0.92;">' + esc(a.detail) + '</div>' +
                '<button type="button" class="btn" style="margin-top:10px;font-size:12px;padding:8px 12px;">Am înțeles</button>';
              var btn = el.querySelector('button');
              if (btn) btn.onclick = function() {
                try { sessionStorage.removeItem('mulberry_twin_alert'); } catch (e) {}
                el.style.display = 'none'; el.innerHTML = '';
              };
            } catch (e) { el.style.display = 'none'; }
          })();

          console.log("[AppDB UI] Dashboard actualizat (noua structură).");
          if (typeof window.refreshProfileSettingsPreview === 'function') {
            try { window.refreshProfileSettingsPreview(); } catch (eR) {}
          }
        } catch (err) {
          console.error('[AppDB] syncDashboard eroare:', err);
          try {
            _hideLoadingUiSafety('syncDashboard.catch');
          } catch (eH2) {}
        } finally {
          try {
            _hideLoadingUiSafety('syncDashboard.finally');
          } catch (eLoad) {}
          _syncDashboardPending = false;
        }
      },

      notifyChange: function() {
        var self = window.AppDB;
        if (!self || typeof self.syncWithCore !== 'function') return;
        // Debounce: nu apela mai des de o dată la 5 secunde
        if (window._notifyChangeTimer) clearTimeout(window._notifyChangeTimer);
        window._notifyChangeTimer = setTimeout(function() {
          self.syncWithCore().then(function(analysis) {
            if (analysis && analysis.alerts && analysis.alerts.length > 0) {
              console.log('[AppDB] Alerte noi de la Core:', analysis.alerts);
            }
            if (typeof self.ui.syncDashboard === 'function') self.ui.syncDashboard();
          });
        }, 5000); // debounce 5s
      },
    },
  };

  // ── Handler centralizat pentru token expirat ──
  function _handleExpiredToken() {
    if (_authRedirecting) return;
    _authRedirecting = true;
    console.warn('[AppDB] Token expirat — curăță sesiunea.');
    try {
      localStorage.removeItem('mulberry_session');
      localStorage.removeItem('yourcar_token');
      localStorage.removeItem('mulberry_current_session');
      localStorage.removeItem('is_founder');
      sessionStorage.removeItem('mulberry_session');
      sessionStorage.removeItem('yourcar_token');
      sessionStorage.removeItem('mulberry_current_session');
      sessionStorage.removeItem('is_founder');
    } catch (e) {}
    // Redirect o singură dată după 300ms
    setTimeout(function() {
      if (typeof window.show === 'function') window.show('login');
      else window.location.href = 'mulberry.html';
    }, 300);
  }

  // ── Interceptează 401 global (din api_client.js) ──
  window.__appdb_handle401 = _handleExpiredToken;

  // Export Global
  window.AppDB = AppDB;

  window.clearSiErr = function() {
    var err = document.getElementById('error-display') || document.querySelector('.ferr');
    if (err) err.textContent = '';
  };

})();
