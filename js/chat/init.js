document.addEventListener('DOMContentLoaded', function() {
  var _histScroll = getChatHistoryEl();
  if (_histScroll) _histScroll.addEventListener('scroll', updateChatJumpFab, { passive: true });

  var _jumpBtn = document.getElementById('chat-jump-latest');
  if (_jumpBtn) _jumpBtn.addEventListener('click', scrollToLatestMulberryReply);

  document.getElementById('btn-new-chat').addEventListener('click', newConversation);
  document.getElementById('chat-send-btn').addEventListener('click', sendMessage);

  var _chatIn = document.getElementById('chat-input');
  var _chatFi = document.getElementById('chat-file-input');
  var _chatAb = document.getElementById('chat-attach-btn');

  if (_chatAb && _chatFi) {
    _chatAb.addEventListener('click', function() { if (!_chatAb.disabled) _chatFi.click(); });
    _chatFi.addEventListener('change', function() {
      var list = _chatFi.files;
      if (!list || !list.length) return;
      for (var i = 0; i < list.length && pendingChatFiles.length < 6; i++) pendingChatFiles.push(list[i]);
      _chatFi.value = '';
      renderAttachPreview();
    });
  }

  if (_chatIn) {
    _chatIn.addEventListener('input', function() { resizeChatTextarea(); syncComposerSendState(); });
    _chatIn.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
  }

  document.getElementById('toggle-sidebar').addEventListener('click', function() {
    var sidebar = document.getElementById('chat-sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('show', sidebar.classList.contains('open'));
  });

  document.getElementById('sidebar-overlay').addEventListener('click', function() {
    document.getElementById('chat-sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('show');
  });

  var _dlf = document.getElementById('device-lock-form');
  if (_dlf) _dlf.addEventListener('submit', async function(ev) {
    ev.preventDefault();
    var ident = (document.getElementById('device-lock-ident').value || '').trim();
    var pass = document.getElementById('device-lock-pass').value || '';
    var errEl = document.getElementById('device-lock-err');
    if (errEl) errEl.textContent = '';
    try {
      var newId = window.MulberryDevice && window.MulberryDevice.getId ? window.MulberryDevice.getId() : '';
      var r = await fetch(apiBase + '/auth/device/approve', {
        method: 'POST',
        headers: mergeAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ identifier: ident, password: pass, new_device_id: newId })
      });
      var data = await r.json().catch(function() { return {}; });
      if (!r.ok) {
        var msg = data.detail;
        if (typeof msg !== 'string') msg = msg ? JSON.stringify(msg) : 'Eroare la confirmare';
        throw new Error(msg);
      }
      if (data.access_token && window.api && window.api.setToken) window.api.setToken(data.access_token);
      hideDeviceLock();
      document.getElementById('device-lock-pass').value = '';
      await probeChatSession();
      loadServerChatHistory();
    } catch (e) { if (errEl) errEl.textContent = (e && e.message) || 'Eroare'; }
  });

  resizeChatTextarea();
  syncComposerSendState();

  probeChatSession().then(function() {
    var conv = ensureCurrentConversation();
    renderSidebar();
    renderMessages(conv.messages);
    refreshChatHeaderSubject();
    renderReminderRail();
    loadServerChatHistory();
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q');
    if (q) {
      var ci = document.getElementById('chat-input');
      if (ci) ci.value = q;
      resizeChatTextarea();
      syncComposerSendState();
      sendMessage();
    }
  });
});
