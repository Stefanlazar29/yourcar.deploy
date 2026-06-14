/* offline/ai.js — Mulberry AI Assistant (chat cu backend + MiniMax /chat) */

(function() {
  window.askMulberry = async function() {
    var inputEl = document.getElementById('assistant-input');
    var outEl = document.getElementById('assistant-response');
    if (!inputEl) return;
    var question = (inputEl.value || '').trim();
    if (!question) {
      window.showToast('Scrie o întrebare pentru Mulberry Assistant.');
      return;
    }
    if (!window.api || typeof window.api.sendMessageToExo !== 'function') {
      window.location.href = 'mulberry_chat.html?q=' + encodeURIComponent(question);
      return;
    }
    var tok = window.api.getToken ? window.api.getToken() : '';
    if (!tok) {
      window.showToast('Conectează-te pentru a folosi MulberryExoTerra.');
      return;
    }
    if (outEl) {
      outEl.textContent = 'Se gândește…';
      outEl.style.opacity = '0.7';
    }
    try {
      var data = await window.api.sendMessageToExo(question, true);
      var reply = (data && data.reply) ? String(data.reply) : 'Fără răspuns.';
      if (data && data.digital_twin_alert) {
        try {
          sessionStorage.setItem('mulberry_twin_alert', JSON.stringify(data.digital_twin_alert));
        } catch (e2) {}
      }
      if (outEl) {
        outEl.style.opacity = '1';
        if (window.api.streamTypeText) {
          await window.api.streamTypeText(outEl, reply, { delayMs: 10, chunk: 4 });
        } else {
          outEl.textContent = reply;
        }
      }
      inputEl.value = '';
    } catch (e) {
      var msg = (e && e.message) ? e.message : 'Eroare chat';
      if (outEl) {
        outEl.textContent = msg;
        outEl.style.opacity = '1';
      }
      window.showToast(msg);
    }
  };
  
  // Enter key trigger (adăugat după load DOM)
  document.addEventListener('DOMContentLoaded', function() {
    var inp = document.getElementById('assistant-input');
    if (inp) {
      inp.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') window.askMulberry();
      });
    }
  });
})();
