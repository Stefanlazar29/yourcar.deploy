/**
 * Comunitate Daily Insight — opinii (stil feed) + optimizare limbaj MulberryEXO.
 */
(function () {
  'use strict';

  function apiBase() {
    return (
      (window.Config && window.Config.apiBaseUrl) ||
      window.API_BASE ||
      'http://127.0.0.1:9000'
    );
  }

  function getToken() {
    if (window.api && typeof window.api.getToken === 'function') {
      return window.api.getToken() || '';
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

  function headersJson() {
    var tok = getToken();
    var h = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + String(tok || '').trim()
    };
    try {
      var key = 'mulberry_device_ephemeral_v1';
      var s = sessionStorage.getItem(key);
      if (!s || s.length < 16) {
        s = 'mdev_sess_' + Math.random().toString(36).slice(2, 14) + '_' + Date.now().toString(36);
        sessionStorage.setItem(key, s);
      }
      h['X-Mulberry-Device-Id'] = s;
    } catch (e0) {}
    return h;
  }

  var ctx = null;

  function loadFeed() {
    var listEl = document.getElementById('insight-social-list');
    if (!listEl || !ctx) return;

    var q =
      ctx.cardId != null && ctx.cardId !== ''
        ? 'card_id=' + encodeURIComponent(String(ctx.cardId))
        : 'sort_order=' + encodeURIComponent(String(ctx.sortOrder != null ? ctx.sortOrder : 0));

    fetch(apiBase() + '/me/daily-insights/opinions?' + q, {
      method: 'GET',
      headers: headersJson()
    })
      .then(function (r) {
        if (!r.ok) throw new Error('feed');
        return r.json();
      })
      .then(function (data) {
        var items = (data && data.opinions) || [];
        if (!items.length) {
          listEl.innerHTML =
            '<p class="insight-social-hint" style="margin:0;">Fii primul care își spune părerea despre acest articol.</p>';
          return;
        }
        listEl.innerHTML = items
          .map(function (o) {
            return (
              '<div class="insight-social-post">' +
              '<div class="insight-social-post-meta">' +
              (o.author_display || '—') +
              ' · ' +
              (o.created_at || '').replace('T', ' ').slice(0, 16) +
              '</div>' +
              '<div class="insight-social-post-body">' +
              String(o.body || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;') +
              '</div></div>'
            );
          })
          .join('');
      })
      .catch(function () {
        listEl.innerHTML =
          '<p class="insight-social-hint">Nu am putut încărca opiniile. Verifică conexiunea și VIN-ul în profil.</p>';
      });
  }

  function init() {
    var titleH = document.getElementById('insight-social-h1');
    var sub = document.getElementById('insight-social-sub');
    var ta = document.getElementById('insight-social-text');
    var polishBtn = document.getElementById('insight-social-polish');
    var postBtn = document.getElementById('insight-social-post');

    var raw = null;
    try {
      raw = sessionStorage.getItem('mulberry_insight_community');
    } catch (e) {}
    if (!raw) {
      if (sub) sub.textContent = 'Deschide din dashboard — Daily Insights.';
      return;
    }
    try {
      ctx = JSON.parse(raw);
    } catch (e2) {
      return;
    }

    if (titleH) titleH.textContent = ctx.title || 'Daily Insight';
    if (sub) {
      sub.textContent =
        'Spune ce crezi — ton deschis, respectuos. MulberryEXO poate corecta formularea înainte de publicare.';
    }

    loadFeed();

    if (polishBtn && ta) {
      polishBtn.addEventListener('click', function () {
        var text = (ta.value || '').trim();
        if (text.length < 3) return;
        polishBtn.disabled = true;
        fetch(apiBase() + '/me/daily-insights/polish-text', {
          method: 'POST',
          headers: headersJson(),
          body: JSON.stringify({ text: text })
        })
          .then(function (r) {
            if (!r.ok) throw new Error('polish');
            return r.json();
          })
          .then(function (d) {
            if (d && d.polished) ta.value = d.polished;
          })
          .catch(function () {})
          .finally(function () {
            polishBtn.disabled = false;
          });
      });
    }

    if (postBtn && ta) {
      postBtn.addEventListener('click', function () {
        var text = (ta.value || '').trim();
        if (text.length < 2) return;
        postBtn.disabled = true;
        var body = { body: text };
        if (ctx.cardId != null && ctx.cardId !== '') {
          body.card_id = ctx.cardId;
        } else {
          body.sort_order = ctx.sortOrder != null ? ctx.sortOrder : 0;
        }
        fetch(apiBase() + '/me/daily-insights/opinions', {
          method: 'POST',
          headers: headersJson(),
          body: JSON.stringify(body)
        })
          .then(function (r) {
            if (!r.ok) throw new Error('post');
            return r.json();
          })
          .then(function () {
            ta.value = '';
            loadFeed();
          })
          .catch(function () {
            alert('Nu s-a putut publica. Ai VIN salvat în profil?');
          })
          .finally(function () {
            postBtn.disabled = false;
          });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
