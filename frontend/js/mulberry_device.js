/** mulberry_device.js — identificare și persistență device. */
(function () {
  function getDeviceId() {
    var id = localStorage.getItem('mulberry_device_id');
    if (!id) {
      id = 'dev-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem('mulberry_device_id', id);
    }
    return id;
  }
  window.MulberryDevice = { id: getDeviceId() };
})();
