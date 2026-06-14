var _ATT_B64_SOFT_MAX = 480000;
var apiBase = (window.Config && window.Config.apiBaseUrl) || 'http://46.225.100.151:8080';

function getChatToken() {
  if (window.api && typeof window.api.getToken === 'function') {
    var t = window.api.getToken();
    if (t && String(t).indexOf('eyJ') === 0) return String(t).trim();
  }
  var t2 = localStorage.getItem('mulberry_session') || localStorage.getItem('yourcar_token') || '';
  t2 = (t2 && String(t2).trim()) || '';
  return (t2.indexOf('eyJ') === 0) ? t2 : '';
}

function deviceHeaders() {
  try { return window.MulberryDevice && window.MulberryDevice.headers ? window.MulberryDevice.headers() : {}; }
  catch (e) { return {}; }
}

function mergeAuthHeaders(base) {
  var h = Object.assign({}, base || {});
  var dh = deviceHeaders();
  Object.keys(dh).forEach(function(k) { h[k] = dh[k]; });
  return h;
}

function readFileAsBase64(file) {
  return new Promise(function(resolve, reject) {
    var r = new FileReader();
    r.onload = function() {
      var s = String(r.result || '');
      var j = s.indexOf(',');
      resolve(j >= 0 ? s.slice(j + 1) : s);
    };
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

function compressImageToJpeg(file, maxW, maxB64Len) {
  return new Promise(function(resolve) {
    maxW = maxW || 1280; maxB64Len = maxB64Len || _ATT_B64_SOFT_MAX;
    var url = URL.createObjectURL(file);
    var img = new Image();
    img.onload = function() {
      URL.revokeObjectURL(url);
      var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
      var scale = w > maxW ? maxW / w : 1;
      var cw = Math.max(1, Math.round(w * scale)), ch = Math.max(1, Math.round(h * scale));
      var c = document.createElement('canvas');
      c.width = cw; c.height = ch;
      c.getContext('2d').drawImage(img, 0, 0, cw, ch);
      var q = 0.88;
      function attempt() {
        var du = c.toDataURL('image/jpeg', q);
        var b64 = du.split(',')[1] || '';
        if (b64.length > maxB64Len && q > 0.45) { q -= 0.08; attempt(); }
        else { var base = (file.name || 'image').replace(/\.[^.]+$/, ''); resolve({ name: base + '.jpg', mime: 'image/jpeg', data_base64: b64 }); }
      }
      attempt();
    };
    img.onerror = function() {
      URL.revokeObjectURL(url);
      readFileAsBase64(file).then(function(b64) { resolve({ name: file.name || 'fișier', mime: file.type || 'application/octet-stream', data_base64: b64 }); });
    };
    img.src = url;
  });
}

function fileToAttachment(file) {
  if (file.type && file.type.indexOf('image/') === 0) return compressImageToJpeg(file);
  return readFileAsBase64(file).then(function(b64) {
    return { name: file.name || 'fișier', mime: file.type || 'application/octet-stream', data_base64: b64 };
  });
}

function setChatLocked(locked) {
  ['chat-input','chat-send-btn','chat-attach-btn','chat-file-input'].forEach(function(id) {
    var el = document.getElementById(id); if (el) el.disabled = !!locked;
  });
}

function showDeviceLock() {
  var el = document.getElementById('device-lock-screen');
  if (!el) return;
  el.classList.add('is-visible'); el.setAttribute('aria-hidden', 'false');
  setChatLocked(true);
  var err = document.getElementById('device-lock-err'); if (err) err.textContent = '';
  try {
    var token = getChatToken();
    if (token) {
      fetch(apiBase + '/me', { headers: { Authorization: 'Bearer ' + token } })
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(d) {
          if (d && d.identifier) { var idEl = document.getElementById('device-lock-ident'); if (idEl && !idEl.value) idEl.value = d.identifier; }
        }).catch(function() {});
    }
  } catch (e) {}
}

function hideDeviceLock() {
  var el = document.getElementById('device-lock-screen');
  if (!el) return;
  el.classList.remove('is-visible'); el.setAttribute('aria-hidden', 'true');
  setChatLocked(false);
}

async function probeChatSession() {
  var token = getChatToken();
  if (!token) return true;
  try {
    var r = await fetch(apiBase + '/auth/session-probe', { headers: mergeAuthHeaders({ Authorization: 'Bearer ' + token }) });
    if (r.status === 403) { showDeviceLock(); return false; }
    return true;
  } catch (e) { return true; }
}

async function loadServerChatHistory() {
  var tid = getCurrentId();
  var token = getChatToken();
  if (!token || !tid) return;
  try {
    var r = await fetch(apiBase + '/assistant/chat/history?thread_id=' + encodeURIComponent(tid), {
      headers: mergeAuthHeaders({ Authorization: 'Bearer ' + token })
    });
    if (r.status === 403) { showDeviceLock(); return; }
    if (!r.ok) return;
    var data = await r.json();
    if (!data.messages || !data.messages.length) return;
    var list = loadConversations();
    var conv = list.find(function(c) { return c.id === tid; });
    if (!conv) return;
    conv.messages = data.messages.map(function(m) { return { role: m.role, text: m.text }; });
    saveConversations(list);
    renderMessages(conv.messages);
    renderSidebar();
  } catch (e) { console.warn('[Chat] istoric server:', e); }
}

async function sendMessage() {
  var inputEl = document.getElementById('chat-input');
  if (!inputEl) return;
  var text = (inputEl.value || '').trim();
  var files = pendingChatFiles.slice(0, 4);
  if (!text && !files.length) return;

  var attachPayload = [], attachNames = [];
  for (var fi = 0; fi < files.length; fi++) {
    try {
      var one = await fileToAttachment(files[fi]);
      if (one && one.data_base64 && one.data_base64.length > _ATT_B64_SOFT_MAX) {
        (window.showToast || alert)('Un fișier este prea mare după procesare.');
        return;
      }
      attachPayload.push(one);
      attachNames.push(one.name || files[fi].name || 'fișier');
    } catch (e1) { (window.showToast || alert)('Nu am putut citi un fișier atașat.'); return; }
  }
  pendingChatFiles.length = 0;
  renderAttachPreview();

  var histClear = getChatHistoryEl();
  if (histClear) histClear.innerHTML = '';

  var conv = getCurrentConversation() || ensureCurrentConversation();
  var persistUser = text || '[Fișiere atașate]';
  if (attachNames.length) persistUser += ' · ' + attachNames.join(', ');
  addMessageBubble(text || '', true, false, false, attachNames.length ? attachNames : null);
  addMessageToConv('user', persistUser);
  showPinnedUserPrompt(text || '', attachNames.length ? attachNames : null);
  inputEl.value = '';
  resizeChatTextarea();
  syncComposerSendState();

  conv = getCurrentConversation();
  var vehicle = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
  var pipeline = mountGeminiGeneratingFlow(vehicle);

  try {
    var headers = mergeAuthHeaders({ 'Content-Type': 'application/json' });
    var token = getChatToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;

    var body = {
      user_id: (window.AppDB && window.AppDB.currentUser && window.AppDB.currentUser.id) || 'guest',
      thread_id: getCurrentId(),
      message: text,
      vin: vehicle.vin || null,
      context: {
        marca: vehicle.marca || null, model: vehicle.model || null,
        series: vehicle.series || null, fuel: vehicle.combustibil || vehicle.fuel || null,
        cloud_files: vehicle.cloud_files || [], reminders: vehicle.reminders || [], history: []
      }
    };
    if (attachPayload.length) body.attachments = attachPayload;

    var res = await fetch(apiBase + '/assistant/exo', { method: 'POST', headers: headers, body: JSON.stringify(body) });
    if (res.status === 403) { pipeline.destroy(); hidePinnedUserPrompt(); showDeviceLock(); return; }
    if (!res.ok) {
      var errDetail = 'HTTP ' + res.status;
      try { var ej = await res.json(); if (ej && ej.detail != null) errDetail = typeof ej.detail === 'string' ? ej.detail : JSON.stringify(ej.detail); } catch (ej2) {}
      throw new Error(errDetail);
    }
    var data = await res.json();
    var reply = (data.reply || 'Nu am putut răspunde.').trim();
    if (data.digital_twin_alert) { try { sessionStorage.setItem('mulberry_twin_alert', JSON.stringify(data.digital_twin_alert)); } catch (e1) {} }
    pipeline.destroy();
    addExoAssistantBlock(reply, true, false, false, function() { addMessageToConv('assistant', reply); hidePinnedUserPrompt(); });

  } catch (err) {
    console.error('[Chat]', err);
    pipeline.destroy(); hidePinnedUserPrompt();
    var errStr = String(err && err.message ? err.message : err);
    var errMsg;
    if (errStr.indexOf('401') !== -1) { errMsg = 'Sesiune expirată. Te reconectezi...'; setTimeout(function() { window.location.href = 'mulberry.html'; }, 2000); }
    else if (errStr.indexOf('Failed to fetch') !== -1 || errStr.indexOf('NetworkError') !== -1) errMsg = 'Backend offline — verifică ' + apiBase + '/health';
    else if (errStr.indexOf('500') !== -1) errMsg = 'Eroare server. Verifică GROQ_API_KEY în backend/.env';
    else if (errStr.indexOf('503') !== -1) errMsg = 'AI indisponibil momentan. Încearcă din nou.';
    else errMsg = 'Mulberry nu este disponibil. ' + errStr;
    addExoAssistantBlock(errMsg, false, true, true, null);
    addMessageToConv('assistant', errMsg);
  }
}

window.showReportModal = function() { var el = document.getElementById('report-modal'); if (el) el.classList.add('active'); };
window.closeReportModal = function() { var el = document.getElementById('report-modal'); if (el) el.classList.remove('active'); };

window.submitReport = async function() {
  var comp = document.getElementById('report-component');
  var desc = document.getElementById('report-desc');
  if (!comp || !desc) return;
  var component = (comp.value || '').trim(), fault = (desc.value || '').trim();
  if (!component || !fault) { (window.showToast || alert)('Completează componenta și descrierea.'); return; }
  var token = getChatToken();
  if (!token) { (window.showToast || alert)('Trebuie să fii conectat pentru a raporta.'); return; }
  try {
    var r = await fetch(apiBase + '/assistant/report', {
      method: 'POST',
      headers: mergeAuthHeaders({ 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }),
      body: JSON.stringify({ component: component, fault_description: fault })
    });
    var data = r.ok ? await r.json() : null;
    if (!r.ok) throw new Error((data && data.detail) ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : 'Eroare');
    window.closeReportModal(); desc.value = '';
    (window.showToast || alert)('Mulțumim! Raportul a fost salvat.');
  } catch (e) { (window.showToast || alert)((e && e.message) || 'Eroare la raportare.'); }
};
