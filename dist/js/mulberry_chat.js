/**
 * Mulberry Chat — utilitar scroll (încărcat înainte de corpul paginii).
 * Conversația principală este în mulberry_chat.html; aici doar API reutilizabil.
 */
(function (global) {
  'use strict';

  /**
   * Rezolvă zona scrollabilă a chatului (clasă dedicată sau #chat-history).
   */
  function resolveChatScrollContainer(containerId) {
    if (typeof containerId === 'string' && containerId) {
      var byId = document.getElementById(containerId);
      if (byId) return byId;
    }
    if (containerId && containerId.nodeType === 1) {
      return containerId;
    }
    return (
      document.querySelector('.chat-messages-container') ||
      document.getElementById('chat-history')
    );
  }

  /**
   * UX chat: urmărește automat ultimul răspuns (jos în listă).
   * Apelează după append la răspunsul serverului sau la sfârșitul stream-ului.
   */
  function scrollToLatest() {
    var chatWindow = resolveChatScrollContainer();
    if (!chatWindow) return;
    function go() {
      chatWindow.scrollTop = chatWindow.scrollHeight;
    }
    go();
    requestAnimationFrame(function () {
      go();
      requestAnimationFrame(go);
    });
  }

  /**
   * Derulează containerul de mesaje la ultimul mesaj (după layout).
   * Dublu requestAnimationFrame ajută când flex/scroll-behavior amână scrollHeight final.
   */
  function scrollToBottom(containerId) {
    var el = resolveChatScrollContainer(containerId);
    if (!el) return;
    function go() {
      el.scrollTop = el.scrollHeight;
    }
    go();
    requestAnimationFrame(function () {
      go();
      requestAnimationFrame(go);
    });
  }

  global.MulberryChatScroll = {
    scrollToBottom: scrollToBottom,
    scrollToLatest: scrollToLatest,
    resolveChatScrollContainer: resolveChatScrollContainer,
  };
})(typeof window !== 'undefined' ? window : globalThis);
