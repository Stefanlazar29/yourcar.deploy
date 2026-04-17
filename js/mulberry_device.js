/**
 * Amprentă stabilă per browser (HWID logic) — trimisă ca X-Mulberry-Device-Id.
 * Persistă în localStorage; nu conține PII în clar.
 */
(function () {
  'use strict';
  var LS_KEY = 'mulberry_device_fingerprint_v1';

  function simpleHash(str) {
    var h = 2166136261 >>> 0;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    var a = ('00000000' + h.toString(16)).slice(-8);
    var b = ('00000000' + (Math.imul(h, 0x9e3779b9) >>> 0).toString(16)).slice(-8);
    var c = ('00000000' + (Math.imul(h, 0x85ebca6b) >>> 0).toString(16)).slice(-8);
    return a + b + c;
  }

  function collectSignals() {
    var p = [
      navigator.userAgent || '',
      navigator.language || '',
      String(screen && screen.width) + 'x' + String(screen && screen.height) + '@' + String(screen && screen.colorDepth),
      String(new Date().getTimezoneOffset()),
      String(navigator.hardwareConcurrency || ''),
      navigator.platform || '',
      navigator.maxTouchPoints != null ? String(navigator.maxTouchPoints) : ''
    ];
    try {
      var c = document.createElement('canvas');
      c.width = 220;
      c.height = 48;
      var ctx = c.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#0a0a12';
        ctx.fillRect(0, 0, 220, 48);
        ctx.fillStyle = '#8eb4ff';
        ctx.font = '16px sans-serif';
        ctx.fillText('Mulberry/EXO', 8, 28);
        ctx.strokeStyle = '#e8e8f0';
        ctx.beginPath();
        ctx.arc(182, 24, 11, 0, Math.PI * 1.65);
        ctx.stroke();
        p.push(c.toDataURL().slice(-140));
      }
    } catch (e) {}
    return p.join('|');
  }

  function getOrCreateId() {
    try {
      var existing = localStorage.getItem(LS_KEY);
      if (existing && String(existing).length >= 24) return String(existing);
      var raw = 'MB|' + collectSignals() + '|' + (Date.now() & 0xfffffff).toString(36);
      var id = 'mdev_' + simpleHash(raw) + '_' + simpleHash(raw + '|mulberry');
      localStorage.setItem(LS_KEY, id);
      return id;
    } catch (e) {
      return 'mdev_fallback_' + String(Date.now());
    }
  }

  window.MulberryDevice = {
    getId: getOrCreateId,
    headers: function () {
      return { 'X-Mulberry-Device-Id': getOrCreateId() };
    }
  };
})();
