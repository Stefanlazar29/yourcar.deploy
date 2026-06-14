/**
 * mulberry_groq_chat.js — Motor chat Groq direct din browser
 *
 * FEATURES:
 *  - Streaming răspuns (token cu token) prin Groq API
 *  - Animații stil Gemini (thinking pipeline → typewriter stream)
 *  - Self-coding: detectează cod în răspuns, afișează cu syntax highlight
 *  - Context vehicul Mulberry injectat automat
 *  - Fallback la /assistant/exo dacă Groq nu e configurat în browser
 *
 * UTILIZARE:
 *  <script src="js/mulberry_groq_chat.js"></script>
 *  window.MulberryGroqChat.init({ containerId: 'chat-history', ... })
 *
 * CONFIGURARE (opțional — dacă vrei Groq direct din browser):
 *  window.MULBERRY_GROQ_KEY = 'gsk_...'   ← NU pune în producție publică
 *  window.MULBERRY_GROQ_MODEL = 'llama-3.3-70b-versatile'
 *
 *  Fără cheie → rutează automat prin backend /assistant/exo (recomandat)
 */

(function (global) {
  'use strict';

  /* ══════════════════════════════════════════════════════════
     CONFIGURARE
  ══════════════════════════════════════════════════════════ */
  var GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions';
  var DEFAULT_MODEL = 'llama-3.3-70b-versatile';

  var SYSTEM_PROMPT = [
    'Ești MulberryEXO — expert auto personal, analitic, direct.',
    'Răspunzi în română. Fără salutări sau fraze de umplutură.',
    'Când dai cod, folosești fenced blocks ```language ... ```.',
    'La probleme tehnice auto: cauze probabile → cost estimat RON → urgență.',
    'Dacă nu știi ceva, spui explicit — nu inventezi date.',
    'Ton: inginer senior, nu customer support.'
  ].join('\n');

  /* ══════════════════════════════════════════════════════════
     PIPELINE STEPS (animație Gemini)
  ══════════════════════════════════════════════════════════ */
  var PIPELINE_STEPS = [
    'Citesc contextul vehiculului…',
    'Analizez întrebarea și istoricul…',
    'Consult baza de cunoștințe auto…',
    'Formulez răspunsul…',
  ];

  /* ══════════════════════════════════════════════════════════
     UTILITĂȚI
  ══════════════════════════════════════════════════════════ */
  function getToken() {
    if (global.api && typeof global.api.getToken === 'function') {
      var t = global.api.getToken();
      if (t && String(t).indexOf('eyJ') === 0) return String(t).trim();
    }
    var t2 = global.localStorage.getItem('mulberry_session') || global.localStorage.getItem('yourcar_token') || '';
    t2 = String(t2 || '').trim();
    return t2.indexOf('eyJ') === 0 ? t2 : '';
  }

  function getApiBase() {
    return (global.Config && global.Config.apiBaseUrl) || global.API_BASE || 'http://127.0.0.1:9000';
  }

  /** Derulare la ultimul mesaj după layout (compatibil cu MulberryChatScroll din mulberry_chat.js). */
  function scrollContainerToBottom(container) {
    if (!container) return;
    if (global.MulberryChatScroll && typeof global.MulberryChatScroll.scrollToBottom === 'function') {
      global.MulberryChatScroll.scrollToBottom(container);
      return;
    }
    function go() {
      container.scrollTop = container.scrollHeight;
    }
    go();
    requestAnimationFrame(function () {
      go();
      requestAnimationFrame(go);
    });
  }

  function mergeAuthHeaders(base) {
    var h = Object.assign({}, base || {});
    try {
      var dh = global.MulberryDevice && global.MulberryDevice.headers ? global.MulberryDevice.headers() : {};
      Object.keys(dh).forEach(function (k) {
        h[k] = dh[k];
      });
    } catch (e) {}
    return h;
  }

  function getGroqKey() {
    return String(global.MULBERRY_GROQ_KEY || '').trim();
  }

  function getModel() {
    return String(global.MULBERRY_GROQ_MODEL || DEFAULT_MODEL).trim();
  }

  function getVehicleContext() {
    try {
      var v = global.AppDB && global.AppDB.getSavedVehicle ? global.AppDB.getSavedVehicle() : {};
      return v || {};
    } catch (e) {
      return {};
    }
  }

  function buildSystemWithVehicle() {
    var v = getVehicleContext();
    var lines = [SYSTEM_PROMPT];
    if (v.vin || v.marca) {
      lines.push('\nVEHICUL UTILIZATOR:');
      if (v.marca) lines.push('- Marcă/Model: ' + v.marca + ' ' + (v.serie || v.series || '') + ' ' + (v.model || ''));
      if (v.an) lines.push('- An: ' + v.an);
      if (v.vin) lines.push('- VIN: ' + v.vin);
      var plate = v.nr || v.plate;
      if (plate) lines.push('- Nr înmatriculare: ' + plate);
      if (v.combustibil || v.fuel) lines.push('- Combustibil: ' + (v.combustibil || v.fuel));
      if (v.soft_score != null && v.soft_score !== '') lines.push('- SoftScore (context app): ' + v.soft_score + '%');
    }
    return lines.join('\n');
  }

  /* ══════════════════════════════════════════════════════════
     SYNTAX HIGHLIGHT minimal (fără dependențe)
  ══════════════════════════════════════════════════════════ */
  var TOKEN_RULES = [
    { re: /(\/\/[^\n]*|#[^\n]*)/g, cls: 'hl-comment' },
    { re: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)/g, cls: 'hl-string' },
    {
      re: /\b(function|return|const|let|var|if|else|for|while|class|import|export|from|async|await|def|print|elif|pass|try|except|raise|in|not|and|or|True|False|None)\b/g,
      cls: 'hl-kw',
    },
    { re: /\b(\d+\.?\d*)\b/g, cls: 'hl-num' },
  ];

  function highlightCode(code, lang) {
    var escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    var result = escaped;
    TOKEN_RULES.forEach(function (rule) {
      result = result.replace(rule.re, '<span class="' + rule.cls + '">$1</span>');
    });
    return result;
  }

  /* ══════════════════════════════════════════════════════════
     PARSER MARKDOWN → HTML minimal
  ══════════════════════════════════════════════════════════ */
  function parseMarkdown(text) {
    var parts = text.split(/(```[\s\S]*?```)/g);
    var html = parts.map(function (part) {
      var codeMatch = part.match(/^```(\w*)\n?([\s\S]*?)```$/);
      if (codeMatch) {
        var lang = codeMatch[1] || 'text';
        var code = codeMatch[2] || '';
        return (
          '<div class="mgc-code-block">' +
          '<div class="mgc-code-lang">' +
          lang.toUpperCase() +
          '</div>' +
          '<button type="button" class="mgc-copy-btn" onclick="MulberryGroqChat._copyCode(this)" title="Copiază">⎘</button>' +
          '<pre class="mgc-pre"><code>' +
          highlightCode(code, lang) +
          '</code></pre>' +
          '</div>'
        );
      }
      return part
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code class="mgc-inline-code">$1</code>')
        .replace(/^#{1,3}\s+(.+)$/gm, '<div class="mgc-heading">$1</div>')
        .replace(/^[-•]\s+(.+)$/gm, '<div class="mgc-bullet">$1</div>')
        .replace(/\n\n+/g, '<br><br>')
        .replace(/\n/g, '<br>');
    });
    return html.join('');
  }

  /* ══════════════════════════════════════════════════════════
     CSS INJECTAT O SINGURĂ DATĂ
  ══════════════════════════════════════════════════════════ */
  var CSS_INJECTED = false;
  function injectStyles() {
    if (CSS_INJECTED) return;
    CSS_INJECTED = true;
    var style = document.createElement('style');
    style.id = 'mgc-styles';
    style.textContent = [
      '.mgc-pipeline{align-self:flex-start;max-width:420px;width:100%;margin:4px 0 12px;padding:16px 18px 18px;border-radius:20px;background:linear-gradient(145deg,rgba(16,18,14,.98),rgba(8,10,7,.99));border:1px solid rgba(225,255,0,.2);box-shadow:0 12px 40px rgba(0,0,0,.5);position:relative;overflow:hidden;}',
      '.mgc-pipeline::before{content:"";position:absolute;inset:-40% -20%;background:radial-gradient(ellipse at 30% 20%,rgba(225,255,0,.1),transparent 55%);animation:mgcAura 4s ease-in-out infinite;pointer-events:none;}',
      '@keyframes mgcAura{0%,100%{opacity:.5}50%{opacity:1}}',
      '.mgc-pipeline-brand{font-size:11px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:rgba(225,255,0,.9);margin-bottom:14px;display:flex;align-items:center;gap:8px;position:relative;z-index:1;}',
      '.mgc-pipeline-brand::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,rgba(225,255,0,.5),transparent);animation:mgcLine 2s ease-in-out infinite;}',
      '@keyframes mgcLine{0%,100%{opacity:.4}50%{opacity:1}}',
      '.mgc-steps{list-style:none;margin:0;padding:0;position:relative;z-index:1;}',
      '.mgc-step{display:flex;align-items:flex-start;gap:10px;font-size:13px;color:rgba(255,255,255,.4);padding:8px 0 8px 14px;border-left:2px solid rgba(255,255,255,.08);margin-left:11px;transition:color .3s,border-color .3s;}',
      '.mgc-step:last-child{border-left-color:transparent;}',
      '.mgc-step.active{color:rgba(255,255,255,.95);border-left-color:rgba(225,255,0,.7);}',
      '.mgc-step.done{color:rgba(225,255,0,.7);border-left-color:rgba(225,255,0,.25);}',
      '.mgc-step-n{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:6px;font-size:11px;font-weight:700;background:rgba(255,255,255,.08);color:rgba(255,255,255,.4);flex-shrink:0;margin-left:-25px;margin-right:4px;}',
      '.mgc-step.active .mgc-step-n{background:rgba(225,255,0,.2);color:#E1FF00;box-shadow:0 0 12px rgba(225,255,0,.35);animation:mgcNpulse 1.2s ease-in-out infinite;}',
      '.mgc-step.done .mgc-step-n{background:rgba(225,255,0,.12);color:#E1FF00;}',
      '@keyframes mgcNpulse{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}',
      '.mgc-scanline{position:absolute;left:0;right:0;bottom:0;height:2px;background:linear-gradient(90deg,transparent,rgba(225,255,0,.6),transparent);animation:mgcScan 2.2s linear infinite;opacity:.7;}',
      '@keyframes mgcScan{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}',
      '.mgc-stream-wrap{align-self:flex-start;max-width:100%;width:100%;margin:4px 0 16px;}',
      '.mgc-stream-block{padding:16px 20px 20px;border-radius:14px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);border-left:3px solid #E1FF00;box-shadow:0 8px 32px rgba(0,0,0,.25);}',
      '.mgc-stream-label{font-size:10px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:rgba(225,255,0,.8);margin-bottom:10px;display:flex;align-items:center;gap:8px;}',
      '.mgc-cursor{display:inline-block;width:2px;height:1.1em;background:#E1FF00;border-radius:1px;margin-left:2px;vertical-align:text-bottom;animation:mgcBlink .7s step-end infinite;}',
      '@keyframes mgcBlink{0%,100%{opacity:1}50%{opacity:0}}',
      '.mgc-stream-body{font-size:14px;line-height:1.65;color:rgba(255,255,255,.92);word-break:break-word;}',
      '.mgc-code-block{position:relative;margin:12px 0;border-radius:10px;background:#0d0f0c;border:1px solid rgba(225,255,0,.15);overflow:hidden;}',
      '.mgc-code-lang{font-size:10px;font-weight:700;letter-spacing:.12em;color:rgba(225,255,0,.6);padding:8px 14px;border-bottom:1px solid rgba(255,255,255,.06);}',
      '.mgc-copy-btn{position:absolute;top:6px;right:8px;background:rgba(225,255,0,.1);border:1px solid rgba(225,255,0,.25);color:rgba(225,255,0,.8);border-radius:6px;padding:3px 8px;font-size:12px;cursor:pointer;}',
      '.mgc-copy-btn:hover{background:rgba(225,255,0,.2);}',
      '.mgc-pre{margin:0;padding:14px;overflow-x:auto;font-family:"JetBrains Mono","Fira Code",monospace;font-size:13px;line-height:1.5;color:rgba(255,255,255,.88);}',
      '.mgc-inline-code{font-family:monospace;background:rgba(225,255,0,.1);border-radius:4px;padding:1px 5px;font-size:.9em;}',
      '.mgc-heading{font-weight:700;font-size:15px;color:#fff;margin:12px 0 6px;}',
      '.mgc-bullet{padding-left:16px;position:relative;margin:4px 0;}.mgc-bullet::before{content:"·";position:absolute;left:4px;color:#E1FF00;}',
      '.hl-comment{color:#5a6654;font-style:italic;}',
      '.hl-string{color:#a8d98a;}',
      '.hl-kw{color:#7aa8ff;font-weight:600;}',
      '.hl-num{color:#e8b86d;}',
      '.mgc-error-block{align-self:flex-start;padding:12px 16px;border-radius:12px;background:rgba(255,60,60,.08);border:1px solid rgba(255,60,60,.25);color:rgba(255,160,160,.9);font-size:13px;margin:4px 0 12px;}',
    ].join('');
    document.head.appendChild(style);
  }

  function mountPipeline(container) {
    var el = document.createElement('div');
    el.className = 'mgc-pipeline';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');

    var stepsHtml = PIPELINE_STEPS.map(function (txt, i) {
      return (
        '<li class="mgc-step" data-step="' +
        i +
        '">' +
        '<span class="mgc-step-n">' +
        (i + 1) +
        '</span>' +
        txt +
        '</li>'
      );
    }).join('');

    el.innerHTML =
      '<div class="mgc-pipeline-brand">MulberryEXO · Processing</div>' +
      '<ul class="mgc-steps">' +
      stepsHtml +
      '</ul>' +
      '<div class="mgc-scanline"></div>';

    container.appendChild(el);
    scrollContainerToBottom(container);

    var steps = el.querySelectorAll('.mgc-step');
    var timers = [];
    var current = 0;

    function advance(n) {
      for (var i = 0; i < steps.length; i++) {
        steps[i].classList.remove('active', 'done');
        if (i < n) steps[i].classList.add('done');
        if (i === n) steps[i].classList.add('active');
      }
      scrollContainerToBottom(container);
    }

    advance(0);
    PIPELINE_STEPS.forEach(function (_, i) {
      if (i === 0) return;
      timers.push(
        setTimeout(function () {
          advance(i);
        }, 700 * i)
      );
    });

    return {
      el: el,
      destroy: function () {
        timers.forEach(clearTimeout);
        if (el.parentNode) el.parentNode.removeChild(el);
      },
    };
  }

  function mountStreamBlock(container) {
    var outer = document.createElement('div');
    outer.className = 'mgc-stream-wrap';

    var block = document.createElement('div');
    block.className = 'mgc-stream-block';

    var label = document.createElement('div');
    label.className = 'mgc-stream-label';
    label.innerHTML = 'MulberryEXO <span class="mgc-cursor"></span>';

    var body = document.createElement('div');
    body.className = 'mgc-stream-body';

    block.appendChild(label);
    block.appendChild(body);
    outer.appendChild(block);
    container.appendChild(outer);
    scrollContainerToBottom(container);

    var fullText = '';
    var done = false;

    return {
      el: outer,
      appendChunk: function (chunk) {
        fullText += chunk;
        body.textContent = fullText;
        scrollContainerToBottom(container);
      },
      finalize: function () {
        if (done) return;
        done = true;
        label.innerHTML = 'MulberryEXO';
        body.innerHTML = parseMarkdown(fullText);
        scrollContainerToBottom(container);
      },
      getText: function () {
        return fullText;
      },
    };
  }

  function showError(container, msg) {
    var el = document.createElement('div');
    el.className = 'mgc-error-block';
    el.textContent = '[EXO] ' + msg;
    container.appendChild(el);
    scrollContainerToBottom(container);
    return el;
  }

  async function callGroqStream(messages, onChunk, onDone, onError) {
    var key = getGroqKey();
    if (!key) {
      onError('GROQ_KEY_MISSING');
      return;
    }

    try {
      var resp = await fetch(GROQ_ENDPOINT, {
        method: 'POST',
        headers: {
          Authorization: 'Bearer ' + key,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: getModel(),
          messages: messages,
          max_tokens: 1500,
          temperature: 0.45,
          stream: true,
        }),
      });

      if (!resp.ok) {
        var errData = await resp.json().catch(function () {
          return {};
        });
        onError('Groq API ' + resp.status + ': ' + ((errData.error && errData.error.message) || 'Unknown'));
        return;
      }

      var reader = resp.body.getReader();
      var decoder = new TextDecoder('utf-8');
      var buffer = '';

      while (true) {
        var result = await reader.read();
        if (result.done) break;
        buffer += decoder.decode(result.value, { stream: true });

        var lines = buffer.split('\n');
        buffer = lines.pop();

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line || line === 'data: [DONE]') continue;
          if (line.indexOf('data: ') === 0) {
            try {
              var json = JSON.parse(line.slice(6));
              var delta = json.choices && json.choices[0] && json.choices[0].delta;
              var content = delta && delta.content;
              if (content) onChunk(content);
            } catch (e) {}
          }
        }
      }
      onDone();
    } catch (err) {
      onError((err && err.message) || String(err));
    }
  }

  async function callBackend(messages, vehicle, onChunk, onDone, onError, backendOpts) {
    backendOpts = backendOpts || {};
    var token = getToken();
    var base = String(getApiBase()).replace(/\/+$/, '');
    var history = messages.slice(0, -1).map(function (m) {
      return { role: m.role, content: m.content };
    });
    var lastMsg = messages[messages.length - 1];

    try {
      var headers = mergeAuthHeaders({
        'Content-Type': 'application/json',
      });
      if (token) headers.Authorization = 'Bearer ' + token;

      var body = {
        user_id: (global.AppDB && global.AppDB.currentUser && global.AppDB.currentUser.id) || 'guest',
        message: lastMsg.content,
        vin: vehicle.vin || null,
        context: {
          marca: vehicle.marca || null,
          model: vehicle.model || null,
          series: vehicle.serie || vehicle.series || null,
          fuel: vehicle.combustibil || vehicle.fuel || null,
          cloud_files: vehicle.cloud_files || [],
          reminders: vehicle.reminders || [],
          history: history,
        },
      };
      if (backendOpts.threadId) body.thread_id = backendOpts.threadId;

      var resp = await fetch(base + '/assistant/exo', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(body),
      });

      if (resp.status === 403) {
        onError('Backend 403 — politică dispozitiv');
        return;
      }
      if (!resp.ok) {
        onError('Backend ' + resp.status);
        return;
      }

      var data = await resp.json();
      var reply = (data.reply || '').trim();

      var i = 0;
      var chunk = 6;
      function tick() {
        if (i >= reply.length) {
          onDone();
          return;
        }
        onChunk(reply.slice(i, i + chunk));
        i += chunk;
        setTimeout(tick, 8);
      }
      tick();
    } catch (err) {
      onError((err && err.message) || String(err));
    }
  }

  function sendMessage(opts) {
    injectStyles();

    var container = opts.container;
    var userMessage = String(opts.userMessage || '').trim();
    var history = opts.history || [];
    var vehicle = getVehicleContext();

    if (!container || !userMessage) return;

    var messages = [{ role: 'system', content: buildSystemWithVehicle() }]
      .concat(history.slice(-10))
      .concat([{ role: 'user', content: userMessage }]);

    var pipeline = mountPipeline(container);

    var useGroq = !!getGroqKey();

    var backendOpts = { threadId: opts.threadId || null };

    setTimeout(function () {
      pipeline.destroy();

      var stream = mountStreamBlock(container);

      function onChunk(chunk) {
        stream.appendChunk(chunk);
      }

      function onDone() {
        stream.finalize();
        if (opts.onComplete) opts.onComplete(stream.getText());
      }

      function onError(msg) {
        if (stream.el.parentNode) stream.el.parentNode.removeChild(stream.el);
        var errMsg = 'Eroare: ' + msg;
        if (msg === 'GROQ_KEY_MISSING') {
          errMsg =
            'GROQ_API_KEY lipsește. Setează window.MULBERRY_GROQ_KEY sau configurează backend-ul.';
        } else if (msg.indexOf('Failed to fetch') !== -1 || msg.indexOf('NetworkError') !== -1) {
          errMsg = 'Backend offline. Pornește uvicorn pe portul 9000 (sau verifică Config.apiBaseUrl).';
        }
        showError(container, errMsg);
        if (opts.onError) opts.onError(errMsg);
      }

      if (useGroq) {
        callGroqStream(messages, onChunk, onDone, onError);
      } else {
        callBackend(messages, vehicle, onChunk, onDone, onError, backendOpts);
      }
    }, PIPELINE_STEPS.length * 700 + 200);
  }

  var SelfCoding = {
    extractBlocks: function (text) {
      var blocks = [];
      var re = /```(\w*)\n?([\s\S]*?)```/g;
      var match;
      while ((match = re.exec(text)) !== null) {
        blocks.push({ lang: match[1] || 'text', code: match[2].trim() });
      }
      return blocks;
    },

    executeJS: function (code) {
      try {
        var fn = new Function(code);
        var result = fn();
        return { ok: true, result: result };
      } catch (e) {
        return { ok: false, error: e.message };
      }
    },

    refactorCode: function (opts) {
      var prompt = [
        'Refactorizează următorul cod conform instrucțiunii:',
        '',
        'INSTRUCȚIUNE: ' + opts.instruction,
        '',
        '```',
        opts.code,
        '```',
        '',
        'Răspunde DOAR cu blocul de cod refactorizat, fără explicații suplimentare.',
      ].join('\n');

      sendMessage({
        container: opts.container,
        history: [],
        userMessage: prompt,
        onComplete: function (text) {
          var blocks = SelfCoding.extractBlocks(text);
          if (blocks.length && opts.onResult) {
            opts.onResult(blocks[0]);
          }
        },
      });
    },
  };

  function init(opts) {
    injectStyles();

    if (opts.groqKey) global.MULBERRY_GROQ_KEY = opts.groqKey;
    if (opts.model) global.MULBERRY_GROQ_MODEL = opts.model;

    var container = document.getElementById(opts.containerId);
    var inputEl = document.getElementById(opts.inputId);
    var sendBtn = document.getElementById(opts.sendBtnId);

    if (!container || !inputEl) {
      console.warn('[MulberryGroqChat] containerId sau inputId invalid.');
      return;
    }

    var conversationHistory = [];

    function doSend() {
      var text = String(inputEl.value || '').trim();
      if (!text) return;

      var userBubble = document.createElement('div');
      userBubble.className = 'chat-msg user-msg msg-fade-in';
      userBubble.textContent = text;
      container.appendChild(userBubble);
      scrollContainerToBottom(container);

      inputEl.value = '';
      if (inputEl.tagName === 'TEXTAREA') {
        inputEl.style.height = 'auto';
      }
      if (sendBtn) sendBtn.disabled = true;

      var userTurn = { role: 'user', content: text };

      sendMessage({
        container: container,
        history: conversationHistory.slice(),
        userMessage: text,
        threadId: opts.threadId || null,
        onComplete: function (reply) {
          conversationHistory.push(userTurn);
          conversationHistory.push({ role: 'assistant', content: reply });
          if (sendBtn) sendBtn.disabled = false;
          inputEl.focus();
        },
        onError: function () {
          if (sendBtn) sendBtn.disabled = false;
          inputEl.focus();
        },
      });
    }

    if (sendBtn) sendBtn.addEventListener('click', doSend);
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        doSend();
      }
    });

    return {
      send: doSend,
      clearHistory: function () {
        conversationHistory = [];
      },
      getHistory: function () {
        return conversationHistory.slice();
      },
      selfCoding: SelfCoding,
    };
  }

  global.MulberryGroqChat = {
    init: init,
    send: sendMessage,
    selfCoding: SelfCoding,
    injectStyles: injectStyles,
    _copyCode: function (btn) {
      var pre = btn.parentElement && btn.parentElement.querySelector('pre');
      if (!pre) return;
      var txt = pre.textContent || '';
      if (global.navigator.clipboard && global.navigator.clipboard.writeText) {
        global.navigator.clipboard.writeText(txt).then(function () {
          btn.textContent = '✓';
          setTimeout(function () {
            btn.textContent = '⎘';
          }, 1500);
        }).catch(function () {
          btn.textContent = '!';
          setTimeout(function () {
            btn.textContent = '⎘';
          }, 1500);
        });
      }
    },
  };
})(typeof window !== 'undefined' ? window : globalThis);
