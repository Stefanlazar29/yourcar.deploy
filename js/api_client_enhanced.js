/* api_client_enhanced.js — Mock fallback + timeout redus pentru producție Vercel */
(function() {

  /** Wrapper cu timeout redus și fallback mock pentru API lente */
  function fetchWithMockFallback(url, options) {
    options = options || {};
    var timeout = (window.Config && window.Config.apiTimeout) || 3000;
    var enableMock = (window.Config && window.Config.enableMockFallback) || false;

    // Promise cu timeout
    var fetchPromise = fetch(url, options);
    var timeoutPromise = new Promise(function(_, reject) {
      setTimeout(function() {
        reject(new Error('API_TIMEOUT_' + timeout + 'ms'));
      }, timeout);
    });

    return Promise.race([fetchPromise, timeoutPromise])
      .then(function(response) {
        if (!response.ok) {
          throw new Error('API_HTTP_' + response.status);
        }
        return response.json();
      })
      .catch(function(error) {
        console.warn('[API] Railway timeout/error, trying mock fallback:', error.message);
        
        if (!enableMock || !window.MockData) {
          throw error;
        }

        // Mock fallback based pe URL pattern
        if (url.includes('/me/vehicles')) {
          return window.MockData.getVehicles();
        }
        if (url.includes('/me')) {
          return window.MockData.getMe();
        }
        if (url.includes('/cars/softscore') || url.includes('/softscore')) {
          return window.MockData.getSoftScore();
        }
        if (url.includes('/reports/latest')) {
          return window.MockData.getLatestReport();
        }
        if (url.includes('/assistant/exo') || url.includes('/chat')) {
          var body = null;
          try {
            body = JSON.parse(options.body || '{}');
          } catch (e) {}
          var message = (body && body.message) || 'test';
          return window.MockData.getChatResponse(message);
        }

        // Pentru alte endpoint-uri, aruncă eroarea originală
        throw error;
      });
  }

  /** Enhanced API object cu mock fallback */
  if (typeof window.API === 'object' && window.API.authenticatedRequest) {
    // Wrap metoda existentă
    var originalAuthRequest = window.API.authenticatedRequest;
    
    window.API.authenticatedRequestWithFallback = function(method, endpoint, data, customHeaders) {
      var token = window.API.getToken();
      if (!token) {
        return Promise.reject(new Error('No auth token'));
      }

      var url = window.API_BASE + endpoint;
      var headers = Object.assign({
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
      }, customHeaders || {});

      var options = {
        method: method,
        headers: headers
      };

      if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        options.body = typeof data === 'string' ? data : JSON.stringify(data);
      }

      return fetchWithMockFallback(url, options);
    };

    // Alias pentru compatibilitate
    window.API.getWithFallback = function(endpoint, customHeaders) {
      return this.authenticatedRequestWithFallback('GET', endpoint, null, customHeaders);
    };

    window.API.postWithFallback = function(endpoint, data, customHeaders) {
      return this.authenticatedRequestWithFallback('POST', endpoint, data, customHeaders);
    };
  }

  /** Helper pentru verificare rapidă API status */
  window.checkApiHealth = function() {
    var healthUrl = window.API_BASE + '/health';
    var startTime = Date.now();
    
    return fetch(healthUrl, { 
      method: 'GET',
      signal: AbortSignal.timeout(2000) // 2s pentru health check
    })
    .then(function(response) {
      var latency = Date.now() - startTime;
      return {
        ok: response.ok,
        status: response.status,
        latency: latency,
        url: healthUrl,
        backend: 'railway'
      };
    })
    .catch(function(error) {
      return {
        ok: false,
        status: 0,
        latency: Date.now() - startTime,
        url: healthUrl,
        error: error.message,
        backend: 'offline'
      };
    });
  };

})();