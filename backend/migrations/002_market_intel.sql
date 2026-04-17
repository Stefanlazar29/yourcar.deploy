-- Intel piață per model (Fabia 6Y etc.): surse + sinteză Groq
-- sqlite3 dev.db < backend/migrations/002_market_intel.sql

CREATE TABLE IF NOT EXISTS market_intel_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_key TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_title TEXT,
  source_type TEXT NOT NULL,
  lang TEXT,
  raw_excerpt TEXT,
  fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_intel_sources_model
  ON market_intel_sources(model_key, fetched_at DESC);

CREATE TABLE IF NOT EXISTS market_intel_synthesis (
  model_key TEXT PRIMARY KEY,
  synthesis_ro TEXT NOT NULL,
  synthesis_json TEXT,
  sources_count INTEGER DEFAULT 0,
  groq_model TEXT,
  updated_at TEXT NOT NULL
);
