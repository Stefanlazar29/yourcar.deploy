/**
 * QR stilizat (module + finders rotunjite), aliniat la referința vizuală Mulberry:
 * negru pe galben saturat, densitate redusă (ECC L), zonă liniște (margin).
 * Necesită js/vendor/qr-code-styling.umd.js (global QRCodeStyling).
 */
(function (global) {
  var DEFAULTS = {
    width: 48,
    height: 48,
    /** Galben din referință (aprox. #F7D735) — distinct de neon card dacă e nevoie */
    backgroundColor: '#F7D735',
    foregroundColor: '#000000',
    /** Zonă liniște în jurul codului (px) */
    margin: 4,
    errorCorrectionLevel: 'L'
  };

  function paint(containerEl, dataString, opts) {
    if (!containerEl || !dataString) return null;
    opts = opts || {};
    var w = opts.width != null ? opts.width : DEFAULTS.width;
    var h = opts.height != null ? opts.height : DEFAULTS.height;
    var bg = opts.backgroundColor != null ? opts.backgroundColor : DEFAULTS.backgroundColor;
    var fg = opts.foregroundColor != null ? opts.foregroundColor : DEFAULTS.foregroundColor;
    var margin = opts.margin != null ? opts.margin : DEFAULTS.margin;
    var ecc = opts.errorCorrectionLevel != null ? opts.errorCorrectionLevel : DEFAULTS.errorCorrectionLevel;

    containerEl.innerHTML = '';

    if (global.QRCodeStyling) {
      try {
        var qr = new global.QRCodeStyling({
          width: w,
          height: h,
          type: 'canvas',
          data: dataString,
          margin: margin,
          qrOptions: {
            errorCorrectionLevel: ecc
          },
          dotsOptions: {
            type: 'extra-rounded',
            color: fg
          },
          cornersSquareOptions: {
            type: 'extra-rounded',
            color: fg
          },
          cornersDotOptions: {
            type: 'dot',
            color: fg
          },
          backgroundOptions: {
            color: bg,
            round: 0
          }
        });
        qr.append(containerEl);
        try {
          containerEl.title = dataString;
        } catch (e1) {}
        return qr;
      } catch (e2) {
        console.warn('[MulberryStyledQR]', e2);
      }
    }

    if (global.QRCode) {
      var cl = global.QRCode.CorrectLevel && global.QRCode.CorrectLevel.L;
      new global.QRCode(containerEl, {
        text: dataString,
        width: w,
        height: h,
        colorDark: fg,
        colorLight: bg,
        correctLevel: cl
      });
    }
    return null;
  }

  global.MulberryStyledQR = {
    paint: paint,
    defaults: DEFAULTS
  };
})(typeof window !== 'undefined' ? window : this);
