var STORAGE_KEY = 'mulberry_conversations';
var CURRENT_KEY = 'mulberry_current_conversation_id';

function loadConversations() {
  try { var raw = localStorage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : []; } catch (e) { return []; }
}

function saveConversations(list) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); } catch (e) {}
}

function getCurrentId() {
  return localStorage.getItem(CURRENT_KEY) || '';
}

function setCurrentId(id) {
  try { localStorage.setItem(CURRENT_KEY, id || ''); } catch (e) {}
}

function genId() {
  return 'c_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
}

function getCurrentConversation() {
  var list = loadConversations();
  var id = getCurrentId();
  return list.find(function(c) { return c.id === id; }) || null;
}

function ensureCurrentConversation() {
  var list = loadConversations();
  var id = getCurrentId();
  var conv = list.find(function(c) { return c.id === id && !c.archived; });
  if (conv) { setCurrentId(conv.id); return conv; }
  conv = { id: genId(), title: 'Conversație nouă', messages: [], archived: false, updatedAt: new Date().toISOString() };
  list.unshift(conv);
  saveConversations(list);
  setCurrentId(conv.id);
  return conv;
}

function summarizeTitleThreeWords(raw) {
  var s = (raw || '').trim().replace(/\s+/g, ' ');
  if (!s) return 'Conversație nouă';
  var part = s.split(/[.!?\n]/)[0].trim();
  var tokens = part.split(/[\s,;:·…\/]+/).filter(function(t) {
    return t && t.replace(/^['"„«»]+|['"„»]+$/g, '').length > 0;
  });
  var words = [];
  for (var i = 0; i < tokens.length && words.length < 3; i++) {
    var w = tokens[i].replace(/^['"„«»\(\[\{]+|['"„»\)\]\}]+$/g, '');
    if (w) words.push(w);
  }
  if (!words.length) return 'Conversație nouă';
  var out = words.join(' ');
  if (out.length > 42) out = out.slice(0, 39) + '…';
  return out.charAt(0).toUpperCase() + out.slice(1);
}

function addMessageToConv(role, text) {
  var conv = getCurrentConversation();
  if (!conv) conv = ensureCurrentConversation();
  conv.messages.push({ role: role, text: text });
  conv.updatedAt = new Date().toISOString();
  if (role === 'user') conv.title = summarizeTitleThreeWords(text);
  var list = loadConversations();
  var idx = list.findIndex(function(c) { return c.id === conv.id; });
  if (idx >= 0) list[idx] = conv; else list.unshift(conv);
  saveConversations(list);
  renderSidebar();
  if (role === 'user') refreshChatHeaderSubject();
}

function archiveConversation(id) {
  var list = loadConversations();
  var conv = list.find(function(c) { return c.id === id; });
  if (!conv) return;
  conv.archived = true;
  conv.updatedAt = new Date().toISOString();
  if (getCurrentId() === id) {
    var next = list.find(function(c) { return !c.archived && c.id !== id; });
    setCurrentId(next ? next.id : '');
    renderMessages(next ? next.messages : []);
  }
  saveConversations(list);
  renderSidebar();
}

function selectConversation(id) {
  var list = loadConversations();
  var conv = list.find(function(c) { return c.id === id; });
  if (!conv) return;
  setCurrentId(conv.id);
  renderMessages(conv.messages);
  refreshChatHeaderSubject();
  renderReminderRail();
  renderSidebar();
  closeSidebar();
  loadServerChatHistory();
}

function newConversation() {
  hidePinnedUserPrompt();
  var conv = { id: genId(), title: 'Conversație nouă', messages: [], archived: false, updatedAt: new Date().toISOString() };
  var list = loadConversations();
  list.unshift(conv);
  saveConversations(list);
  setCurrentId(conv.id);
  renderSidebar();
  renderMessages(conv.messages);
  refreshChatHeaderSubject();
  renderReminderRail();
  closeSidebar();
  loadServerChatHistory();
  return conv;
}
