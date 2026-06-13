/** mulberry_styled_qr.js — generare QR code stilizat pentru vehicul. */
(function () {
  window.MulberryQR = {
    generate: function (containerId, data) {
      var el = document.getElementById(containerId);
      if (!el) return;
      /* Fallback simplu dacă librăria vendor lipsește */
      if (window.QRCodeStyling) {
        var qr = new window.QRCodeStyling({
          width: 200, height: 200, data: data,
          dotsOptions: { color: '#E1FF00', type: 'rounded' },
          backgroundOptions: { color: '#080808' }
        });
        qr.append(el);
      } else {
        el.innerHTML = '<p style="color:#888;font-size:12px">QR indisponibil</p>';
      }
    }
  };
})();
