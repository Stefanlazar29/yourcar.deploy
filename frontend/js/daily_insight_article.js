/**
 * Pagină articol Daily Insight — hero + conținut (stil frame 2).
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

  function estimateReadMinutes(text) {
    var w = (text || '').trim().split(/\s+/).filter(Boolean).length;
    var min = w / 190;
    if (min < 1) return 1;
    if (min > 2) return 2;
    return Math.round(min * 10) / 10;
  }

  function init() {
    var root = document.getElementById('insight-article-root');
    var hero = document.getElementById('insight-article-hero');
    var tagsEl = document.getElementById('insight-hero-tags');
    var titleEl = document.getElementById('insight-hero-title');
    var metaEl = document.getElementById('insight-article-meta');
    var bodyEl = document.getElementById('insight-article-body');
    var galleryEl = document.getElementById('insight-frame-gallery');
    var shareBtn = document.getElementById('insight-share-btn');

    var raw = null;
    try {
      raw = sessionStorage.getItem('mulberry_insight_read');
    } catch (e) {}
    if (!raw) {
      if (root) {
        root.innerHTML =
          '<div class="insight-article-sheet"><p style="padding:24px;">Articolul nu a fost găsit. <a href="mulberry.html">Înapoi la Mulberry</a></p></div>';
      }
      return;
    }

    var c = {};
    try {
      c = JSON.parse(raw);
    } catch (e2) {
      return;
    }

    var img = (c.image_url && String(c.image_url).trim()) || '';
    if (img && hero) {
      hero.style.backgroundImage = 'url(' + JSON.stringify(img) + ')';
    }

    var tag = (c.tag || 'INSIGHT').trim();
    if (tagsEl) {
      tagsEl.innerHTML =
        '<span class="insight-badge-mexo">MulberryEXO</span>' +
        '<span class="insight-pill-tag">' +
        String(tag).replace(/</g, '&lt;') +
        '</span>';
    }
    if (titleEl) {
      titleEl.textContent = c.title || 'Daily Insight';
    }

    var reading = (c.reading_text && String(c.reading_text).trim()) || '';
    var essence = (c.essence && String(c.essence).trim()) || '';
    var rm = estimateReadMinutes(reading);
    var dateStr = '';
    try {
      dateStr = new Date().toLocaleDateString('ro-RO', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch (e3) {
      dateStr = '';
    }
    if (metaEl) {
      metaEl.textContent = 'MulberryEXO · ' + dateStr + ' · ~' + rm + ' min citire';
    }
    if (bodyEl) {
      bodyEl.textContent =
        reading ||
        essence ||
        'Conținutul va fi disponibil după sincronizare cu profilul tău Mulberry.';
    }

    var frames = [];
    if (c.frame_images && Array.isArray(c.frame_images)) {
      for (var fi = 0; fi < c.frame_images.length; fi++) {
        var fu = String(c.frame_images[fi] || '').trim();
        if (fu.indexOf('http') === 0) frames.push(fu);
      }
    }
    if (galleryEl) {
      if (frames.length > 0) {
        galleryEl.hidden = false;
        galleryEl.innerHTML = '';
        var label = document.createElement('p');
        label.className = 'insight-frame-gallery__label';
        label.textContent = 'Imagini din flux (cadru)';
        galleryEl.appendChild(label);
        var strip = document.createElement('div');
        strip.className = 'insight-frame-gallery__strip';
        for (var g = 0; g < frames.length; g++) {
          var fig = document.createElement('figure');
          fig.className = 'insight-frame-gallery__fig';
          var im = document.createElement('div');
          im.className = 'insight-frame-gallery__img';
          im.style.backgroundImage = 'url(' + JSON.stringify(frames[g]) + ')';
          im.setAttribute('role', 'img');
          fig.appendChild(im);
          strip.appendChild(fig);
        }
        galleryEl.appendChild(strip);
      } else {
        galleryEl.hidden = true;
        galleryEl.innerHTML = '';
      }
    }

    if (shareBtn) {
      shareBtn.addEventListener('click', function () {
        var t = (c.title || '') + '\n\n' + (reading || '').slice(0, 500);
        if (navigator.share) {
          navigator.share({ title: c.title || 'Mulberry', text: t }).catch(function () {});
        } else {
          try {
            navigator.clipboard.writeText(t);
            shareBtn.textContent = '✓';
            setTimeout(function () {
              shareBtn.textContent = '↗';
            }, 1600);
          } catch (e4) {}
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
