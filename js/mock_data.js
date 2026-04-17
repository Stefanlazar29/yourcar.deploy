/* mock_data.js — Date simulate pentru fallback rapid */
(function() {
  'use strict';

  // Mock data pentru vehicul și rapoarte când Railway e lent/offline
  var MOCK_VEHICLE_DATA = {
    id: 'mock-001',
    marca: 'Dacia',
    model: 'Logan',
    an: 2019,
    combustibil: 'benzina',
    nr: 'B 123 MLB',
    vin: 'UU1ZZZSCZHA123456',
    serie: 'MCV',
    culoare: 'Albastru',
    km: 85000,
    cmc: 1200,
    putere: 75,
    norma: 'Euro 6',
    masa: 1150,
    locuri: 5,
    combustibilCapacitate: 50,
    combustibilConsum: 6.8,
    lastSync: new Date().toISOString(),
    verified: true
  };

  var MOCK_REPORTS = [
    {
      id: 'rpt-001',
      type: 'Verificare generală',
      date: '2026-04-15',
      status: 'completed',
      summary: 'Starea tehnică este bună. Recomandat schimb ulei în următoarele 2000 km.',
      details: {
        engine: { status: 'good', notes: 'Funcționare optimă' },
        brakes: { status: 'fair', notes: 'Uzură normală, verificare în 6 luni' },
        suspension: { status: 'good', notes: 'Fără probleme detectate' },
        electrical: { status: 'excellent', notes: 'Sistem complet funcțional' }
      }
    },
    {
      id: 'rpt-002',
      type: 'Inspecție tehnică',
      date: '2026-03-20',
      status: 'passed',
      summary: 'ITP valid până la 20.03.2027. Toate sistemele în parametrii.',
      details: {
        emissions: { status: 'passed', value: '0.21% CO' },
        lights: { status: 'passed', notes: 'Toate funcționale' },
        steering: { status: 'passed', notes: 'Direcție precisă' }
      }
    }
  ];

  var MOCK_SOFTSCORE = {
    total: 87,
    hub: 92,
    cloud: 83,
    breakdown: {
      maintenance: 85,
      performance: 90,
      safety: 88,
      efficiency: 86
    },
    lastUpdate: new Date().toISOString(),
    trend: '+2'
  };

  var MOCK_USER_DATA = {
    id: 'user-mock',
    email: 'demo@mulberry.autos',
    name: 'Demo User',
    role: 'user',
    preferences: {
      notifications: true,
      language: 'ro',
      units: 'metric'
    }
  };

  /** Mock pentru /me endpoint */
  window.MockData = {
    vehicle: MOCK_VEHICLE_DATA,
    reports: MOCK_REPORTS,
    softscore: MOCK_SOFTSCORE,
    user: MOCK_USER_DATA,

    /** Simulate API delay */
    withDelay: function(data, ms) {
      ms = ms || (Math.random() * 800 + 200); // 200-1000ms
      return new Promise(function(resolve) {
        setTimeout(function() { resolve(data); }, ms);
      });
    },

    /** Mock pentru GET /me */
    getMe: function() {
      return this.withDelay({
        id: this.user.id,
        identifier: this.user.email,
        email: this.user.email,
        role: this.user.role,
        preferences: this.user.preferences
      });
    },

    /** Mock pentru GET /me/vehicles */
    getVehicles: function() {
      return this.withDelay([this.vehicle]);
    },

    /** Mock pentru GET /cars/softscore */
    getSoftScore: function() {
      return this.withDelay({
        score: this.softscore.total,
        hub_score: this.softscore.hub,
        cloud_score: this.softscore.cloud,
        breakdown: this.softscore.breakdown,
        last_update: this.softscore.lastUpdate,
        trend: this.softscore.trend
      });
    },

    /** Mock pentru GET /reports/latest */
    getLatestReport: function() {
      return this.withDelay(this.reports[0]);
    },

    /** Mock pentru chat */
    getChatResponse: function(message) {
      var responses = [
        'Înțeleg întrebarea ta despre ' + (message.slice(0, 20) + '...') + '. Analizez datele vehiculului...',
        'Pe baza istoricului tău, recomand verificarea sistemului menționat.',
        'Această informație este disponibilă în secțiunea rapoarte. Vrei să o deschid?',
        'Status actual: toate sistemele funcționează în parametrii normali.'
      ];
      var randomResponse = responses[Math.floor(Math.random() * responses.length)];

      return this.withDelay({
        reply: randomResponse,
        thread_id: 'mock-thread-' + Date.now(),
        timestamp: new Date().toISOString()
      }, 1500);
    }
  };

  /** Auto-populate localStorage cu date mock dacă e gol */
  window.MockData.populateIfEmpty = function() {
    try {
      var storageKey = (window.Config && window.Config.storageKey) || 'mulberry_v1_db';
      var existing = localStorage.getItem(storageKey);

      if (!existing || existing === '{}' || existing === 'null') {
        console.log('[MockData] Populez localStorage cu date simulate...');
        var mockStorage = {
          vehicle: this.vehicle,
          user: this.user,
          reports: this.reports,
          softscore: this.softscore,
          lastMockUpdate: new Date().toISOString()
        };
        localStorage.setItem(storageKey, JSON.stringify(mockStorage));
      }
    } catch (e) {
      console.warn('[MockData] Nu pot popula localStorage:', e);
    }
  };

  // Auto-init mock data în dev sau când API nu răspunde
  document.addEventListener('DOMContentLoaded', function() {
    if (window.Config && window.Config.enableMockFallback) {
      window.MockData.populateIfEmpty();
    }
  });

})();
