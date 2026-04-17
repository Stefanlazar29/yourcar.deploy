-- vehicle_insights: răspunsuri analiză business (Groq) + cache 24h per user/VIN/întrebare
-- Rulează manual pe SQLite existent dacă init_db() nu a fost reapelat:
--   sqlite3 dev.db < backend/migrations/001_vehicle_insights.sql

CREATE TABLE IF NOT EXISTS vehicle_insights (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  vin TEXT NOT NULL,
  created_at TEXT NOT NULL,
  question TEXT NOT NULL,
  question_hash TEXT NOT NULL,
  analysis_json TEXT NOT NULL,
  score REAL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_vehicle_insights_cache
  ON vehicle_insights(user_id, vin, question_hash, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vehicle_insights_user_vin
  ON vehicle_insights(user_id, vin, created_at DESC);
