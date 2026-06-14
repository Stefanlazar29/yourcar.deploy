var pendingChatFiles = [];

var SUGGESTION_CARDS = [
  { label: 'Adaugă ITP', sub: 'Documente la zi, fără griji pe drum', href: 'mulberry_cloud.html', icon: 'M4 16v1a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1m-4-8l-4-4m0 0L8 8m4-4v12' },
  { label: 'Raport lunar', sub: 'Nu uita de revizie – setează un reminder', href: 'reminder.html', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z' },
  { label: 'Ghid service', sub: 'Întrebări tehnice și întreținere', href: 'mulberry.html', icon: 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z' },
  { label: 'Încarcă RCA', sub: 'Asigură-te rapid – în Cloud', href: 'mulberry_cloud.html', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0 1 12 2.944a11.955 11.955 0 0 1 8.618 3.04A12.02 12.02 0 0 1 2 12c0 5.523 4.477 10 10 10' }
];

function getChatHistoryEl() {
  return document.getElementById('chat-history');
}

function closeSidebar() {
  var sidebar = document.getElementById('chat-sidebar');
  var overlay = document.getElementById('sidebar-overlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('show');
}

function resizeChatTextarea() {
  var ta = document.getElementById('chat-input');
  if (!ta || ta.tagName !== 'TEXTAREA') return;
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
}

function syncComposerSendState() {
  var ta = document.getElementById('chat-input');
  var btn = document.getElementById('chat-send-btn');
  if (!btn || !ta) return;
  var has = ((ta.value || '').trim().length > 0) || pendingChatFiles.length > 0;
  btn.disabled = !!ta.disabled || !has;
}

function renderAttachPreview() {
  var el = document.getElementById('chat-attach-preview');
  if (!el) return;
  el.querySelectorAll('img').forEach(function(img) {
    if (img.src && img.src.indexOf('blob:') === 0) URL.revokeObjectURL(img.src);
  });
  el.innerHTML = '';
  pendingChatFiles.slice(0, 6).forEach(function(file) {
    var chip = document.createElement('div');
    chip.className = 'chat-attach-chip';
    if (file.type && file.type.indexOf('image/') === 0) {
      var img = document.createElement('img');
      img.alt = '';
      img.src = URL.createObjectURL(file);
      chip.appendChild(img);
    }
    var lab = document.createElement('span');
    lab.textContent = (file.name || 'fișier').slice(0, 40);
    lab.style.cssText = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0';
    chip.appendChild(lab);
    var rm = document.createElement('button');
    rm.type = 'button'; rm.className = 'rm';
    rm.setAttribute('aria-label', 'Elimină atașament');
    rm.textContent = '×';
    rm.onclick = function() {
      var i = pendingChatFiles.indexOf(file);
      if (i >= 0) pendingChatFiles.splice(i, 1);
      renderAttachPreview();
    };
    chip.appendChild(rm);
    el.appendChild(chip);
  });
  syncComposerSendState();
}

function appendSuggestionCards(container) {
  var wrap = document.createElement('div');
  wrap.className = 'chat-suggestion-cards';
  SUGGESTION_CARDS.forEach(function(s) {
    var a = document.createElement('a');
    a.className = 'chat-suggestion-card';
    a.href = s.href;
    a.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="' + s.icon + '"/></svg><span>' + s.label + '</span>';
    a.title = s.sub;
    wrap.appendChild(a);
  });
  container.appendChild(wrap);
}

function updateChatJumpFab() {
  var el = getChatHistoryEl();
  var btn = document.getElementById('chat-jump-latest');
  if (!el || !btn) return;
  var gap = el.scrollHeight - el.scrollTop - el.clientHeight;
  btn.hidden = gap < 96 || el.scrollHeight <= el.clientHeight + 8;
}

function scrollChatToBottom() {
  if (window.MulberryChatScroll && typeof window.MulberryChatScroll.scrollToLatest === 'function') {
    window.MulberryChatScroll.scrollToLatest();
  } else if (window.MulberryChatScroll && typeof window.MulberryChatScroll.scrollToBottom === 'function') {
    window.MulberryChatScroll.scrollToBottom('chat-history');
  } else {
    var el = getChatHistoryEl();
    if (el) el.scrollTop = el.scrollHeight;
  }
  setTimeout(updateChatJumpFab, 0);
  requestAnimationFrame(function() { requestAnimationFrame(updateChatJumpFab); });
}

function scrollToLatestMulberryReply() {
  var hist = getChatHistoryEl();
  if (!hist) return;
  var nodes = hist.querySelectorAll('.exo-reply-wrap, .chat-msg-wrap.assistant, .gemini-flow');
  var last = nodes.length ? nodes[nodes.length - 1] : null;
  if (last && typeof last.scrollIntoView === 'function') last.scrollIntoView({ behavior: 'smooth', block: 'end' });
  scrollChatToBottom();
  setTimeout(updateChatJumpFab, 350);
}

function showPinnedUserPrompt(displayText, attachNames) {
  var wrap = document.getElementById('chat-pinned-user');
  var body = document.getElementById('chat-pinned-body');
  var attEl = document.getElementById('chat-pinned-attach');
  if (!wrap || !body) return;
  body.textContent = (displayText || '').trim() || (attachNames && attachNames.length ? '' : '…');
  if (attEl) {
    if (attachNames && attachNames.length) { attEl.textContent = '📦 ' + attachNames.join(', '); attEl.hidden = false; }
    else { attEl.textContent = ''; attEl.hidden = true; }
  }
  wrap.classList.add('is-generating');
  wrap.hidden = false;
  updateChatJumpFab();
}

function hidePinnedUserPrompt() {
  var wrap = document.getElementById('chat-pinned-user');
  if (!wrap) return;
  wrap.classList.remove('is-generating');
  wrap.hidden = true;
  var attEl = document.getElementById('chat-pinned-attach');
  if (attEl) { attEl.textContent = ''; attEl.hidden = true; }
}

function streamExoReply(bodyEl, fullText, opts, done) {
  opts = opts || {};
  var delay = opts.delayMs != null ? opts.delayMs : 6;
  var chunk = opts.chunk != null ? opts.chunk : 2;
  bodyEl.textContent = '';
  var textSpan = document.createElement('span');
  textSpan.className = 'exo-stream-live';
  var cursor = document.createElement('span');
  cursor.className = 'exo-type-cursor';
  cursor.setAttribute('aria-hidden', 'true');
  bodyEl.appendChild(textSpan);
  bodyEl.appendChild(cursor);
  var i = 0;
  function step() {
    if (i >= fullText.length) {
      if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
      scrollChatToBottom();
      if (done) done();
      return;
    }
    i = Math.min(i + chunk, fullText.length);
    textSpan.textContent = fullText.slice(0, i);
    scrollChatToBottom();
    setTimeout(step, delay);
  }
  step();
}

function addMessageBubble(text, isUser, canReport, skipSuggestions, attachNames) {
  var messagesEl = getChatHistoryEl();
  if (!messagesEl) return;
  var wrap = document.createElement('div');
  wrap.className = 'chat-msg-wrap msg-fade-in' + (isUser ? ' user' : ' assistant');
  var msgDiv = document.createElement('div');
  msgDiv.className = isUser ? 'chat-msg user-msg' : 'chat-msg assistant-msg';
  msgDiv.textContent = (text || '').trim() || (attachNames && attachNames.length ? '' : text);
  if (isUser && attachNames && attachNames.length) {
    var attEl = document.createElement('div');
    attEl.className = 'chat-user-attachments';
    attachNames.forEach(function(nm) {
      var sp = document.createElement('span');
      sp.textContent = '📎 ' + nm;
      attEl.appendChild(sp);
    });
    msgDiv.appendChild(attEl);
  }
  wrap.appendChild(msgDiv);
  if (!isUser && canReport) {
    var reportBtn = document.createElement('button');
    reportBtn.className = 'chat-report-btn';
    reportBtn.textContent = 'Raportează problema';
    reportBtn.onclick = function() { window.showReportModal && window.showReportModal(); };
    wrap.appendChild(reportBtn);
  }
  if (!isUser && !skipSuggestions) appendSuggestionCards(wrap);
  messagesEl.appendChild(wrap);
  scrollChatToBottom();
}

function addExoAssistantBlock(fullText, canReport, skipSuggestions, skipTypewriter, onComplete) {
  var messagesEl = getChatHistoryEl();
  if (!messagesEl) return;
  var outer = document.createElement('div');
  outer.className = 'exo-reply-wrap msg-fade-in';
  var block = document.createElement('div');
  block.className = 'exo-reply-block';
  var label = document.createElement('div');
  label.className = 'exo-reply-label';
  label.textContent = 'MulberryEXO';
  var body = document.createElement('div');
  body.className = 'exo-reply-body';
  block.appendChild(label);
  block.appendChild(body);
  outer.appendChild(block);
  messagesEl.appendChild(outer);
  scrollChatToBottom();

  function afterText() {
    if (canReport) {
      var reportBtn = document.createElement('button');
      reportBtn.className = 'chat-report-btn';
      reportBtn.style.marginTop = '12px';
      reportBtn.textContent = 'Raportează problema';
      reportBtn.onclick = function() { window.showReportModal && window.showReportModal(); };
      outer.appendChild(reportBtn);
    }
    if (!skipSuggestions) appendSuggestionCards(outer);
    scrollChatToBottom();
    if (onComplete) onComplete();
  }

  if (skipTypewriter) { body.textContent = fullText; afterText(); }
  else { streamExoReply(body, fullText, { delayMs: 5, chunk: 2 }, afterText); }
}

function mountGeminiGeneratingFlow(vehicle) {
  var marca = (vehicle && vehicle.marca) ? String(vehicle.marca).trim() : '';
  var model = (vehicle && vehicle.model) ? String(vehicle.model).trim() : '';
  var step1 = 'Analizează filtrele și contextul vehiculului…';
  var step2 = marca || model
    ? 'Se compară rezultatele cu datele din profil (' + marca + (model ? ' ' + model : '') + ')…'
    : 'Se compară rezultatele cu datele din profil și istoricul conversației…';
  var step3 = 'Mulberry scrie răspunsul…';

  var wrap = document.createElement('div');
  wrap.className = 'gemini-flow msg-fade-in';
  wrap.setAttribute('role', 'status');
  wrap.setAttribute('aria-live', 'polite');
  wrap.innerHTML =
    '<div class="gemini-flow-head"><span class="gemini-orb" aria-hidden="true"></span><span>Mulberry</span></div>' +
    '<ul class="gemini-steps" role="list">' +
    '<li data-step="1"><span class="g-dot" aria-hidden="true"></span><span class="gemini-step-txt"></span></li>' +
    '<li data-step="2"><span class="g-dot" aria-hidden="true"></span><span class="gemini-step-txt"></span></li>' +
    '<li data-step="3"><span class="g-dot" aria-hidden="true"></span><span class="gemini-step-txt"></span></li>' +
    '</ul><div class="gemini-shimmer-bar" aria-hidden="true"></div>';

  var txts = wrap.querySelectorAll('.gemini-step-txt');
  if (txts[0]) txts[0].textContent = step1;
  if (txts[1]) txts[1].textContent = step2;
  if (txts[2]) txts[2].textContent = step3;

  var hist = getChatHistoryEl();
  if (!hist) return { el: wrap, destroy: function() {} };
  hist.appendChild(wrap);
  scrollChatToBottom();

  var items = wrap.querySelectorAll('.gemini-steps li');
  var timeouts = [];
  function arm(fn, ms) { timeouts.push(setTimeout(fn, ms)); }
  function setPhase(n) {
    for (var i = 0; i < items.length; i++) {
      items[i].classList.remove('is-active', 'is-done');
      if (i + 1 < n) items[i].classList.add('is-done');
      else if (i + 1 === n) items[i].classList.add('is-active');
    }
    scrollChatToBottom();
  }
  setPhase(1);
  arm(function() { setPhase(2); }, 850);
  arm(function() { setPhase(3); }, 2100);

  return {
    el: wrap,
    destroy: function() {
      timeouts.forEach(function(id) { clearTimeout(id); });
      if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
    }
  };
}

function renderMessages(messages) {
  hidePinnedUserPrompt();
  var messagesEl = getChatHistoryEl();
  if (!messagesEl) return;
  messagesEl.innerHTML = '';
  (messages || []).forEach(function(m) {
    if (m.role === 'user') addMessageBubble(m.text, true, false, false);
    else addExoAssistantBlock(m.text, true, true, true, null);
  });
  scrollChatToBottom();
  refreshChatHeaderSubject();
}

function renderSidebar() {
  var list = loadConversations();
  var currentId = getCurrentId();
  var active = list.filter(function(c) { return !c.archived; });
  var archived = list.filter(function(c) { return c.archived; });
  function byUpdatedDesc(a, b) { return new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0); }
  active.sort(byUpdatedDesc);
  archived.sort(byUpdatedDesc);

  var listEl = document.getElementById('conversation-list');
  var archEl = document.getElementById('archived-list');
  var sectionArch = document.getElementById('section-archived');
  if (!listEl) return;
  listEl.innerHTML = '';
  archEl.innerHTML = '';
  sectionArch.style.display = archived.length ? 'block' : 'none';

  active.forEach(function(c) {
    var div = document.createElement('div');
    div.className = 'sidebar-conv' + (c.id === currentId ? ' active' : '');
    div.innerHTML = '<span class="conv-title">' + (c.title || 'Conversație nouă') + '</span><button type="button" class="conv-archive" title="Mută în Librarie"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 8v13H3V8M1 3h22v5H1V3z"/><path d="M10 12h4"/></svg></button>';
    div.onclick = function(e) { if (!e.target.closest('.conv-archive')) selectConversation(c.id); };
    div.querySelector('.conv-archive').onclick = function(e) { e.stopPropagation(); archiveConversation(c.id); };
    listEl.appendChild(div);
  });

  archived.forEach(function(c) {
    var div = document.createElement('div');
    div.className = 'sidebar-conv';
    div.innerHTML = '<span class="conv-title">' + (c.title || 'Salvată în Librarie') + '</span>';
    div.onclick = function() {
      c.archived = false; c.updatedAt = new Date().toISOString();
      saveConversations(list); setCurrentId(c.id);
      renderMessages(c.messages); renderSidebar();
    };
    archEl.appendChild(div);
  });
}

function refreshChatHeaderSubject() {
  var c = getCurrentConversation();
  var sub = document.querySelector('.chat-subtitle');
  if (sub && c && c.title && c.title !== 'Conversație nouă') sub.textContent = c.title;
  else if (sub) sub.textContent = 'Co-pilot auto · conversația e memorată';
}

function renderReminderRail() {
  var rail = document.getElementById('chat-reminder-rail');
  if (!rail) return;
  var v = window.AppDB && window.AppDB.getSavedVehicle ? window.AppDB.getSavedVehicle() : {};
  var rem = v.reminders || [];
  var pending = rem.filter(function(r) { return (r.status || 'pending') === 'pending'; });
  rail.innerHTML = '';
  if (!pending.length) { rail.style.display = 'none'; return; }
  rail.style.display = 'flex';
  pending.slice(0, 5).forEach(function(r) {
    var p = document.createElement('span');
    p.className = 'chat-reminder-pill';
    p.textContent = (r.task || r.title || 'Reminder').slice(0, 42);
    p.title = r.task || r.title || '';
    rail.appendChild(p);
  });
}
