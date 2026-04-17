/**
 * mulberry_settings_library.js — Meniu setări „⋯” reutilizabil (Hub, Chat, alte pagini).
 *
 * Poți extinde opțiunile:
 *   MulberrySettingsLibrary.appendItem({ id: 'x', label: 'Nume', href: 'page.html' });
 *   MulberrySettingsLibrary.prependItem({ ... });
 *   MulberrySettingsLibrary.setItems([ ... ]); // înlocuiește lista
 *
 * Inițializare:
 *   MulberrySettingsMenu.init({ triggerId: 'mulberry-hub-settings', theme: 'hub' });
 *   MulberrySettingsMenu.init({ triggerId: 'mulberry-chat-settings', theme: 'chat' });
 */
(function (global) {
  'use strict';

  function dirBase() {
    try {
      var path = global.location.pathname || '/';
      var i = path.lastIndexOf('/');
      return global.location.origin + (i >= 0 ? path.slice(0, i + 1) : '/');
    } catch (e) {
      return '';
    }
  }

  function norm(s) {
    return String(s == null ? '' : s).trim();
  }

  function onlyVin(v) {
    return norm(v).replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  }

  function deriveMlbr(v) {
    if (!v) return '';
    return norm(v.ycr_id) || norm(v.mlbr_code) || '';
  }

  function buildQrLandingHref() {
    var base = dirBase();
    var q = new URLSearchParams();
    try {
      var v = global.AppDB && global.AppDB.getSavedVehicle ? global.AppDB.getSavedVehicle() : {};
      var mlbr = deriveMlbr(v);
      var vin = onlyVin(v.vin);
      var profile =
        vin.length === 17
          ? base.replace(/\/+$/, '') + '/p/' + vin
          : mlbr
            ? base + 'vehicle_present.html?m=' + encodeURIComponent(mlbr)
            : '';
      if (profile) q.set('u', profile);
      if (mlbr) q.set('mlbr', mlbr);
      if (vin) q.set('vin', vin);
    } catch (e) {}
    return base + 'mulberry_qr_landing.html?' + q.toString();
  }

  /** Item: { id, label, description?, href? | hrefBuilder? | action?: 'about' | function } */
  function buildDefaultItems() {
    var b = dirBase();
    return [
      { id: 'mymulberry', label: 'MyMulberry', description: 'Aplicația principală', href: b + 'mulberry.html' },
      { id: 'profile', label: 'Profile', description: 'Cont și documente cloud', href: b + 'mulberry_cloud.html' },
      { id: 'mulberryid', label: 'MulberryID', description: 'Sesiune și vehicul legat', href: b + 'yourcar_id.html' },
      {
        id: 'mulberryqr',
        label: 'MulberryQR',
        description: 'Scan, Magazin Play, PDF',
        hrefBuilder: buildQrLandingHref,
      },
      { id: 'mulberryhub', label: 'MulberryHub', description: 'Vehicle BIOS · ID Hub', href: b + 'mulberry_menu.html' },
      { id: 'qdata', label: 'QData', description: 'Catalog câmpuri și surse (SQLite / API)', href: b + 'mulberry_qdata.html' },
      {
        id: 'mulberrychat',
        label: 'MulberryChat',
        description: 'Conversații cu alți utilizatori (în dezvoltare)',
        href: b + 'mulberry_chat.html?social=1',
      },
      { id: 'mulberrysoftscore', label: 'MulberrySoftScore', description: 'Scor și sănătate software', href: b + 'mulberry_softscore.html' },
      { id: 'about', label: 'About MulberryEXO', description: 'Versiune și misiune', action: 'about' },
    ];
  }

  var items = buildDefaultItems();

  var CSS_DONE = false;
  function injectCss() {
    if (CSS_DONE) return;
    CSS_DONE = true;
    var st = document.createElement('style');
    st.id = 'mlb-settings-lib-css';
    st.textContent = [
      '.mlb-set-backdrop{position:fixed;inset:0;z-index:5000;background:transparent;}',
      '.mlb-set-menu{position:fixed;z-index:5001;min-width:min(92vw,280px);max-width:92vw;padding:8px 0;margin:0;',
      'list-style:none;border-radius:14px;box-shadow:0 16px 48px rgba(0,0,0,.2);',
      'border:1px solid rgba(0,0,0,.1);font-family:inherit;font-size:14px;}',
      '.mlb-set-menu[data-theme="hub"]{background:rgba(255,255,255,.96);backdrop-filter:blur(12px);color:#2e3532;}',
      '.mlb-set-menu[data-theme="chat"]{background:rgba(22,24,32,.94);backdrop-filter:blur(16px);border-color:rgba(255,255,255,.12);color:rgba(248,250,255,.95);}',
      '.mlb-set-item{display:block;width:100%;text-align:left;padding:12px 16px;border:none;background:transparent;cursor:pointer;',
      'font:inherit;color:inherit;text-decoration:none;box-sizing:border-box;border-radius:0;}',
      '.mlb-set-menu[data-theme="hub"] .mlb-set-item:hover{background:rgba(46,53,50,.06);}',
      '.mlb-set-menu[data-theme="chat"] .mlb-set-item:hover{background:rgba(255,255,255,.08);}',
      '.mlb-set-item-title{font-weight:600;display:block;}',
      '.mlb-set-item-desc{font-size:11px;opacity:.65;margin-top:3px;line-height:1.35;}',
      '.mlb-set-sep{height:1px;margin:6px 12px;background:currentColor;opacity:.12;}',
      '.mlb-about-overlay{position:fixed;inset:0;z-index:6000;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:20px;}',
      '.mlb-about-box{max-width:400px;width:100%;padding:22px;border-radius:18px;background:#f7f5f0;color:#2e3532;',
      'box-shadow:0 24px 64px rgba(0,0,0,.35);font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;}',
      '.mlb-about-box h2{margin:0 0 10px;font-size:18px;}',
      '.mlb-about-box p{margin:0 0 12px;opacity:.88;}',
      '.mlb-about-close{margin-top:14px;padding:10px 16px;border-radius:10px;border:none;background:#2e3532;color:#f7f5f0;font-weight:600;cursor:pointer;width:100%;}',
      '.vorxs-more-btn,.chat-settings-btn{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;',
      'border-radius:50%;border:1px solid rgba(0,0,0,.12);background:rgba(255,255,255,.5);cursor:pointer;font-size:20px;line-height:1;color:inherit;padding:0;}',
      '.chat-settings-btn{border-color:rgba(255,255,255,.15);background:rgba(255,255,255,.08);color:#fff;}',
      '.chat-settings-btn:hover{background:rgba(255,255,255,.12);}',
      '.vorxs-more-btn:hover{background:rgba(255,255,255,.85);}',
    ].join('');
    document.head.appendChild(st);
  }

  function openAbout() {
    var o = document.createElement('div');
    o.className = 'mlb-about-overlay';
    o.setAttribute('role', 'dialog');
    o.setAttribute('aria-modal', 'true');
    o.innerHTML =
      '<div class="mlb-about-box">' +
      '<h2>MulberryEXO</h2>' +
      '<p>Platformă de identitate digitală auto, asistent tehnic și date vehicul. ' +
      'Conectată la backend Mulberry (FastAPI) și fluxuri locale (offline-first).</p>' +
      '<p style="font-size:12px;opacity:.7">Nu înlocuiește diagnoza service sau documentele oficiale.</p>' +
      '<button type="button" class="mlb-about-close">Închide</button>' +
      '</div>';
    function rm() {
      if (o.parentNode) o.parentNode.removeChild(o);
    }
    o.addEventListener('click', function (ev) {
      if (ev.target === o) rm();
    });
    o.querySelector('.mlb-about-close').addEventListener('click', rm);
    document.body.appendChild(o);
  }

  function resolveHref(it) {
    if (typeof it.hrefBuilder === 'function') return it.hrefBuilder() || '#';
    return it.href || '#';
  }

  function handleItemClick(it, closeMenu) {
    if (it.action === 'about') {
      openAbout();
      closeMenu();
      return;
    }
    if (typeof it.action === 'function') {
      try {
        it.action();
      } catch (e) {}
      closeMenu();
      return;
    }
    var h = resolveHref(it);
    if (h && h !== '#') {
      global.location.href = h;
    }
    closeMenu();
  }

  var MulberrySettingsMenu = {
    _instance: null,

    init: function (opts) {
      injectCss();
      opts = opts || {};
      var trigger = document.getElementById(opts.triggerId);
      if (!trigger) {
        console.warn('[MulberrySettingsMenu] trigger missing:', opts.triggerId);
        return null;
      }
      var theme = opts.theme === 'chat' ? 'chat' : 'hub';
      var self = this;
      var backdrop = null;
      var menu = null;

      function closeMenu() {
        if (backdrop && backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
        if (menu && menu.parentNode) menu.parentNode.removeChild(menu);
        backdrop = null;
        menu = null;
        trigger.setAttribute('aria-expanded', 'false');
      }

      function openMenu() {
        closeMenu();
        trigger.setAttribute('aria-expanded', 'true');
        backdrop = document.createElement('div');
        backdrop.className = 'mlb-set-backdrop';
        backdrop.addEventListener('click', closeMenu);

        menu = document.createElement('ul');
        menu.className = 'mlb-set-menu';
        menu.setAttribute('data-theme', theme);
        menu.setAttribute('role', 'menu');

        var list = items.slice();
        list.forEach(function (it, idx) {
          if (idx > 0) {
            var sep = document.createElement('li');
            sep.className = 'mlb-set-sep';
            sep.setAttribute('role', 'presentation');
            menu.appendChild(sep);
          }
          var li = document.createElement('li');
          li.setAttribute('role', 'none');
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'mlb-set-item';
          btn.setAttribute('role', 'menuitem');
          btn.innerHTML =
            '<span class="mlb-set-item-title">' +
            String(it.label || '').replace(/</g, '&lt;') +
            '</span>' +
            (it.description
              ? '<span class="mlb-set-item-desc">' + String(it.description).replace(/</g, '&lt;') + '</span>'
              : '');
          btn.addEventListener('click', function () {
            handleItemClick(it, closeMenu);
          });
          li.appendChild(btn);
          menu.appendChild(li);
        });

        document.body.appendChild(backdrop);
        document.body.appendChild(menu);

        var r = trigger.getBoundingClientRect();
        var mw = menu.offsetWidth;
        var mh = menu.offsetHeight;
        var top = r.bottom + 6;
        var left = r.right - mw;
        if (left < 8) left = 8;
        if (left + mw > global.innerWidth - 8) left = global.innerWidth - mw - 8;
        if (top + mh > global.innerHeight - 8) top = r.top - mh - 6;
        menu.style.top = top + 'px';
        menu.style.left = left + 'px';
      }

      function toggle() {
        if (menu) closeMenu();
        else openMenu();
      }

      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        toggle();
      });

      global.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape' && menu) closeMenu();
      });

      return { close: closeMenu, open: openMenu };
    },
  };

  var MulberrySettingsLibrary = {
    getItems: function () {
      return items.map(function (x) {
        return Object.assign({}, x);
      });
    },
    setItems: function (arr) {
      items = (arr || []).map(function (x) {
        return Object.assign({}, x);
      });
    },
    resetItems: function () {
      items = buildDefaultItems();
    },
    appendItem: function (it) {
      items.push(Object.assign({}, it));
    },
    prependItem: function (it) {
      items.unshift(Object.assign({}, it));
    },
    removeItemById: function (id) {
      items = items.filter(function (x) {
        return x.id !== id;
      });
    },
    buildQrLandingHref: buildQrLandingHref,
    dirBase: dirBase,
  };

  global.MulberrySettingsLibrary = MulberrySettingsLibrary;
  global.MulberrySettingsMenu = MulberrySettingsMenu;
})(typeof window !== 'undefined' ? window : globalThis);
