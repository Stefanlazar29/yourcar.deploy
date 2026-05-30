/**
 * Daily Insights — MulberryEXO: feed magazine, Citește → articol, card → comunitate.
 */
(function (global) {
  'use strict';

  var SWITCH_AUTO_MS = 5000;
  var _slideTimer = null;
  var _cardsCache = [];
  var _slideIndex = 0;

  /** Fallback când sincronizarea nu e disponibilă (aceeași structură ca GET /me/daily-insights). */
  var DEMO_FALLBACK = {
    banner:
      'Modul demo — conectează aplicația la serverul Mulberry și salvează vehiculul în profil pentru articole MulberryEXO reale.',
    cards: [
      {
        tag: 'TECH',
        title: 'Producător — tehnologii și planuri de produs',
        url: 'https://www.skoda-auto.ro/',
        image_url: 'https://images.unsplash.com/photo-1487754180451-c456f29a4ddc?w=900&q=80&auto=format&fit=crop',
        frame_images: [
          'https://images.unsplash.com/photo-1487754180451-c456f29a4ddc?w=900&q=80&auto=format&fit=crop',
          'https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=900&q=80&auto=format&fit=crop'
        ],
        kind: 'article',
        essence: 'Demo: direcții tehnice și electrificare — articolele complete vin de la MulberryEXO după sincronizare.',
        reading_text:
          'Acesta este un exemplu de layout. MulberryEXO redactează aici articole tematice despre planurile producătorului pentru marca ta: tehnologie, denumiri, rol în mașină și de ce contează pe piață.\n\n' +
          'În producție, fiecare articol are cel puțin trei paragrafe, cu argumente clare, nu doar slogane.\n\n' +
          'După ce profilul este sincronizat, vei citi conținut actualizat pentru vehiculul tău.'
      },
      {
        tag: 'ȘTIRI',
        title: 'Știri și context pentru modelul tău',
        url: 'https://www.skoda-auto.ro/',
        image_url: 'https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=900&q=80&auto=format&fit=crop',
        frame_images: [
          'https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=900&q=80&auto=format&fit=crop',
          'https://images.unsplash.com/photo-1545239351-1141bd82e8a6?w=900&q=80&auto=format&fit=crop',
          'https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=900&q=80&auto=format&fit=crop'
        ],
        kind: 'article',
        essence: 'Demo: noutăți despre modelul din profil — actualizare zilnică înainte de 06:00.',
        reading_text:
          'Exemplu pentru al doilea card: știri și context despre modelul exact din garaj (ex. Fabia 6Y), fără a repeta subiectele din zilele anterioare.\n\n' +
          'MulberryEXO structurează textul în paragrafe și explică de ce informația e relevantă pentru tine.\n\n' +
          'Conținutul real apare după sincronizare cu serverul Mulberry.'
      },
      {
        tag: 'SERVICE',
        title: 'Probleme frecvente și soluții practice',
        url: 'https://www.rarom.ro/',
        image_url: 'https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?w=900&q=80&auto=format&fit=crop',
        frame_images: [
          'https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?w=900&q=80&auto=format&fit=crop',
          'https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=900&q=80&auto=format&fit=crop'
        ],
        kind: 'article',
        essence: 'Demo: diagnostic orientativ și pași de remediere — verifică mereu la service autorizat.',
        reading_text:
          'Exemplu pentru al treilea card: probleme tipice ale modelului și soluții practice, cu ton educativ.\n\n' +
          'Fiecare articol MulberryEXO include argumente și pași pe care îi poți discuta cu mecanicul.\n\n' +
          'Citirea țintește sub două minute, cu minimum trei paragrafe.'
      }
    ]
  };

  function apiBase() {
    return (
      (global.Config && global.Config.apiBaseUrl) ||
      global.API_BASE ||
      'http://127.0.0.1:9000'
    );
  }

  function getToken() {
    if (global.api && typeof global.api.getToken === 'function') {
      return global.api.getToken() || '';
    }
    try {
      return (
        localStorage.getItem('mulberry_session') ||
        localStorage.getItem('yourcar_token') ||
        ''
      );
    } catch (e) {
      return '';
    }
  }

  function buildInsightHeaders() {
    var tok = getToken();
    var h = {
      Accept: 'application/json',
      Authorization: 'Bearer ' + String(tok || '').trim()
    };
    try {
      if (global.MulberryDevice && global.MulberryDevice.headers) {
        var d = global.MulberryDevice.headers();
        Object.keys(d).forEach(function (k) {
          if (d[k] != null && String(d[k]).trim().length) {
            h[k] = d[k];
          }
        });
      }
    } catch (e) {}
    if (!h['X-Mulberry-Device-Id'] || String(h['X-Mulberry-Device-Id']).trim().length < 8) {
      try {
        var key = 'mulberry_device_ephemeral_v1';
        var s = sessionStorage.getItem(key);
        if (!s || s.length < 16) {
          s = 'mdev_sess_' + Math.random().toString(36).slice(2, 14) + '_' + Date.now().toString(36);
          sessionStorage.setItem(key, s);
        }
        h['X-Mulberry-Device-Id'] = s;
      } catch (e2) {}
    }
    return h;
  }

  function showInsightsSection(section) {
    if (!section) return;
    section.classList.remove('daily-insights--hidden');
    section.style.display = 'block';
  }

  function hideInsightsSection(section) {
    if (!section) return;
    section.classList.add('daily-insights--hidden');
  }

  function applyInsightsPayload(section, track, dots, bannerEl, data) {
    if (!data || !data.cards || !data.cards.length) {
      return false;
    }
    if (bannerEl) {
      if (data.banner) {
        bannerEl.hidden = false;
        bannerEl.textContent = data.banner;
      } else {
        bannerEl.hidden = true;
        bannerEl.textContent = '';
      }
    }
    _cardsCache = data.cards.map(function (c, i) {
      var o = Object.assign({}, c);
      o._idx = i;
      return o;
    });
    _slideIndex = 0;
    var html = '';
    for (var j = 0; j < _cardsCache.length; j++) {
      html +=
        '<div class="insight-slide' +
        (j === 0 ? ' is-active' : '') +
        '" role="group" aria-roledescription="slide" aria-label="' +
        esc('Recomandare ' + (j + 1) + ' din ' + _cardsCache.length) +
        '">' +
        renderSlideInner(_cardsCache[j]) +
        '</div>';
    }
    track.innerHTML = html;
    if (dots) {
      var dh = '';
      for (var k = 0; k < _cardsCache.length; k++) {
        dh +=
          '<button type="button" data-dot="' +
          k +
          '" aria-current="' +
          (k === 0 ? 'true' : 'false') +
          '" aria-label="Slide ' +
          (k + 1) +
          '"></button>';
      }
      dots.innerHTML = dh;
    }
    wireSlideUI(track, dots);
    startSlideTimer(track, dots, _cardsCache.length);
    showInsightsSection(section);
    return true;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function estimateReadMinutes(text) {
    var w = (text || '').trim().split(/\s+/).filter(Boolean).length;
    var min = w / 190;
    if (min < 1) return 1;
    if (min > 2) return 2;
    return Math.round(min * 10) / 10;
  }

  function collectFrameImageUrls(c) {
    var urls = [];
    if (c && c.frame_images && Array.isArray(c.frame_images)) {
      for (var i = 0; i < c.frame_images.length; i++) {
        var u = String(c.frame_images[i] || '').trim();
        if (u.indexOf('http') === 0) urls.push(u);
      }
    }
    var hero = (c && c.image_url) ? String(c.image_url).trim() : '';
    if (urls.length === 0 && hero) urls = [hero];
    return urls;
  }

  function buildMagazineMediaHtml(urls) {
    if (!urls || !urls.length) {
      return '<div class="insight-card-media"></div>';
    }
    if (urls.length === 1) {
      return (
        '<div class="insight-card-media" style="background-image:url(' + JSON.stringify(urls[0]) + ')"></div>'
      );
    }
    var cells = '';
    for (var j = 0; j < urls.length; j++) {
      cells +=
        '<div class="insight-media-strip__cell" style="background-image:url(' +
        JSON.stringify(urls[j]) +
        ')"></div>';
    }
    return (
      '<div class="insight-card-media insight-card-media--strip" aria-label="Imagini asociate articolului">' +
      '<div class="insight-media-strip">' +
      cells +
      '</div></div>'
    );
  }

  function renderSlideInner(c) {
    var tag = esc((c && c.tag) || 'INSIGHT');
    var title = esc((c && c.title) || '');
    var kind = ((c && c.kind) || 'article').toLowerCase() === 'promo' ? 'promo' : 'article';
    var essence = (c && c.essence) ? String(c.essence).trim() : '';
    var reading = (c && c.reading_text) ? String(c.reading_text) : '';
    var rm = estimateReadMinutes(reading);
    var dateStr = '';
    try {
      dateStr = new Date().toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' });
    } catch (e1) {
      dateStr = '';
    }
    var preview = essence
      ? esc(essence)
      : 'Deschide pentru esența și articolul MulberryEXO (minim trei paragrafe, argumente tehnice).';
    var idx = typeof c._idx === 'number' ? c._idx : 0;
    var frameUrls = collectFrameImageUrls(c);
    var mediaHtml = buildMagazineMediaHtml(frameUrls);
    return (
      '<div class="insight-card-magazine insight-card-magazine--' +
      kind +
      '" data-insight-idx="' +
      idx +
      '" role="link" tabindex="0" aria-label="Deschide comunitatea Mulberry pentru acest articol">' +
      mediaHtml +
      '<div class="insight-card-body">' +
      '<div class="insight-card-brand-row">' +
      '<span class="insight-badge-mexo">MulberryEXO</span>' +
      '<span class="insight-pill-tag">' +
      tag +
      '</span>' +
      '</div>' +
      '<h3 class="insight-card-title">' +
      title +
      '</h3>' +
      '<p class="insight-essence-preview">' +
      preview +
      '</p>' +
      '<div class="insight-card-authorline">' +
      '<span class="insight-card-author">MulberryEXO</span>' +
      '<span class="insight-card-dot">·</span>' +
      '<span class="insight-card-date">' +
      esc(dateStr) +
      '</span>' +
      '<span class="insight-card-dot">·</span>' +
      '<span class="insight-card-readtime">' +
      esc(String(rm)) +
      ' min citire</span>' +
      '</div>' +
      '<div class="insight-actions">' +
      '<button type="button" class="insight-open-read" data-insight-idx="' +
      idx +
      '">Citește</button>' +
      '</div>' +
      '</div>' +
      '</div>'
    );
  }

  function openInsightArticle(idx) {
    var c = _cardsCache[idx];
    if (!c) return;
    try {
      sessionStorage.setItem('mulberry_insight_read', JSON.stringify(c));
    } catch (e) {}
    window.location.href = 'daily_insight_article.html';
  }

  function openInsightCommunity(idx) {
    var c = _cardsCache[idx];
    if (!c) return;
    try {
      sessionStorage.setItem(
        'mulberry_insight_community',
        JSON.stringify({
          cardId: c.id != null ? c.id : null,
          sortOrder: idx,
          title: c.title || '',
          tag: c.tag || '',
          image_url: c.image_url || ''
        })
      );
    } catch (e2) {}
    window.location.href = 'daily_insights_community.html';
  }

  function clearSlideTimer() {
    if (_slideTimer) {
      clearInterval(_slideTimer);
      _slideTimer = null;
    }
  }

  function goToSlide(track, dots, n, len) {
    if (!track || len < 1) return;
    _slideIndex = ((n % len) + len) % len;
    var slides = track.querySelectorAll('.insight-slide');
    for (var i = 0; i < slides.length; i++) {
      slides[i].classList.toggle('is-active', i === _slideIndex);
    }
    if (dots) {
      var b = dots.querySelectorAll('button');
      for (var j = 0; j < b.length; j++) {
        b[j].setAttribute('aria-current', j === _slideIndex ? 'true' : 'false');
      }
    }
  }

  function startSlideTimer(track, dots, len) {
    clearSlideTimer();
    if (len < 2) return;
    _slideTimer = setInterval(function () {
      goToSlide(track, dots, _slideIndex + 1, len);
    }, SWITCH_AUTO_MS);
  }

  function wireSlideUI(track, dots) {
    if (dots && !dots._mulberryInsightWired) {
      dots._mulberryInsightWired = true;
      dots.addEventListener('click', function (e) {
        var t = e.target;
        if (t && t.getAttribute && t.getAttribute('data-dot') != null) {
          var i = parseInt(t.getAttribute('data-dot'), 10);
          if (!isNaN(i)) {
            goToSlide(track, dots, i, _cardsCache.length);
            startSlideTimer(track, dots, _cardsCache.length);
          }
        }
      });
    }
    if (track && !track._mulberryInsightWired) {
      track._mulberryInsightWired = true;
      track.addEventListener('click', function (e) {
        var readBtn = e.target && e.target.closest ? e.target.closest('.insight-open-read') : null;
        if (readBtn) {
          e.preventDefault();
          e.stopPropagation();
          var ix = parseInt(readBtn.getAttribute('data-insight-idx'), 10);
          if (!isNaN(ix) && _cardsCache[ix]) openInsightArticle(ix);
          return;
        }
        var mag = e.target && e.target.closest ? e.target.closest('.insight-card-magazine') : null;
        if (mag) {
          e.preventDefault();
          var ix2 = parseInt(mag.getAttribute('data-insight-idx'), 10);
          if (!isNaN(ix2) && _cardsCache[ix2]) openInsightCommunity(ix2);
        }
      });
      track.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var mag = e.target && e.target.closest ? e.target.closest('.insight-card-magazine') : null;
        if (!mag || e.target.closest('.insight-open-read')) return;
        e.preventDefault();
        var ix3 = parseInt(mag.getAttribute('data-insight-idx'), 10);
        if (!isNaN(ix3) && _cardsCache[ix3]) openInsightCommunity(ix3);
      });
    }
  }

  function mulberryLoadDailyInsights() {
    var section = document.getElementById('daily-insights-section');
    var track = document.getElementById('insight-slides-track');
    var dots = document.getElementById('insight-slides-dots');
    var bannerEl = document.getElementById('daily-insights-banner');
    if (!section || !track) return;

    clearSlideTimer();

    var tok = getToken();
    if (!tok) {
      hideInsightsSection(section);
      return;
    }

    var headers = buildInsightHeaders();
    var path = '/me/daily-insights';

    function tryDemo(reason) {
      if (applyInsightsPayload(section, track, dots, bannerEl, DEMO_FALLBACK)) {
        try {
          console.warn('[DailyInsights] Demo MulberryEXO (exemplu UI):', reason || '');
        } catch (e) {}
      } else {
        hideInsightsSection(section);
      }
    }

    var fetchFn =
      typeof global.fetchWithBackoff === 'function'
        ? function () {
            return global.fetchWithBackoff(path, { method: 'GET', headers: headers }, { logPrefix: '[DailyInsights]', maxRetries: 1, timeout: 15000 });
          }
        : function () {
            return fetch(apiBase() + path, { method: 'GET', headers: headers });
          };

    fetchFn()
      .then(function (r) {
        if (r.status === 401) {
          hideInsightsSection(section);
          return null;
        }
        if (r.status === 403) {
          tryDemo('403-device');
          return null;
        }
        if (!r.ok) {
          tryDemo('http-' + r.status);
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.cards || !data.cards.length) {
          tryDemo('empty-cards');
          return;
        }
        if (!applyInsightsPayload(section, track, dots, bannerEl, data)) {
          tryDemo('apply-failed');
        }
      })
      .catch(function (err) {
        tryDemo((err && err.message) || 'network');
      });
  }

  global.mulberryLoadDailyInsights = mulberryLoadDailyInsights;
  global.openInsightArticle = openInsightArticle;
  global.openInsightCommunity = openInsightCommunity;
})(typeof window !== 'undefined' ? window : globalThis);
