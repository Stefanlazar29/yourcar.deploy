/* offline/cloud.js — Mulberry Cloud (funcționalități PDF / Upload) */

(function() {
  // Helper pentru a citi datele vehiculului
  function getVehicleData() {
    return window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
  }

  // 1) Generare PDF (minimalist)
  window.generateReportPDF = function() {
    var vehicle = getVehicleData();
    var reportContent = [
      '--- Raport Vehicul Mulberry ---',
      'Cod MLBR: ' + (vehicle.mlbr_code || 'N/A'),
      'Marca: ' + (vehicle.marca || 'N/A'),
      'Model: ' + (vehicle.model || 'N/A'),
      'An: ' + (vehicle.an || 'N/A'),
      'VIN: ' + (vehicle.vin || 'N/A'),
      'Nr. înmatriculare: ' + (vehicle.nr || 'N/A'),
      '----------------------------',
      'Generat la: ' + (new Date()).toLocaleString()
    ].join('\n');

    // Simulăm descărcarea unui fișier TXT
    var blob = new Blob([reportContent], { type: 'text/plain;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'Mulberry_Report_' + (vehicle.mlbr_code || '_') + '.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    window.showToast('✅ Raport PDF (TXT) generat cu succes!', true);
  };

  // 2) Încărcare Documente (frontend + backend placeholder)
  window.handleFileUpload = async function(event) {
    var file = event.target.files[0];
    if (!file) return;

    window.showToast('⏳ Se încarcă documentul: ' + file.name + '...');
    console.log('[Cloud] Document selectat:', file);

    // Aici ar veni logica de upload către FastAPI
    // Ex: var formData = new FormData(); formData.append('file', file);
    // await fetch('/upload/document', { method: 'POST', body: formData });

    // Simulăm un upload reușit și o verificare AI
    setTimeout(async function() {
      window.showToast('✅ Document încărcat și verificat de AI (SIMULARE)!', true);
      // Aici poți adăuga o bifă vizuală în UI, sau actualiza statusul
      console.log('[Cloud] Verificare AI: documentul pare OK.');
    }, 1500);
  };

  // UX: "Descarcă / Digital History"
  window.openCloudFiles = function() {
    if (typeof window.generateReportPDF === 'function') {
      window.generateReportPDF();
      return;
    }
    window.showToast('Funcția de descărcare nu este încărcată.');
  };

  // Alte funcții Cloud (dacă e necesar)
  window.showMulberryCloud = function() {
    window.showToast('Mulberry Cloud: Urmează UI dedicat.');
    // Logica de afișare a unei interfețe dedicate Cloud
  };

})();