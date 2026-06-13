/** soft.js — calcule YCS SoftScore. */
(function () {
  window.MulberrySoft = {
    calculate: function (data) {
      return Promise.resolve({ score: data && data.ycs_score || null, label: 'N/A' });
    }
  };
})();
