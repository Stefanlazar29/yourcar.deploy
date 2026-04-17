"""DDL inițial PostgreSQL (Supabase) — echivalent schema SQLite din database.init_db."""

from __future__ import annotations

from typing import List


def postgres_ddl() -> List[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS users (
          id SERIAL PRIMARY KEY,
          identifier TEXT UNIQUE,
          email TEXT,
          phone TEXT,
          password_hash TEXT,
          created_at TEXT,
          role TEXT,
          device_hwid_hash TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS cars (
          id SERIAL PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id),
          make TEXT,
          model TEXT,
          year TEXT,
          fuel TEXT,
          plate TEXT,
          vin TEXT,
          series TEXT,
          ycr_id TEXT,
          ycr_code TEXT,
          km_actuali INTEGER,
          rca_expiry TEXT,
          itp_expiry TEXT,
          ycs_score DOUBLE PRECISION,
          updated_at TEXT,
          mlbr_code TEXT,
          profile_narrative TEXT,
          profile_narrative_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS vehicle_brains (
          vin TEXT PRIMARY KEY,
          brain_data TEXT NOT NULL,
          last_sync TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS exo_daily_insights (
          id SERIAL PRIMARY KEY,
          vin TEXT NOT NULL,
          insight_text TEXT NOT NULL,
          insight_type TEXT DEFAULT 'general',
          raw_context TEXT,
          created_at TEXT NOT NULL,
          engine TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS daily_insight_cards (
          id SERIAL PRIMARY KEY,
          vin TEXT NOT NULL,
          user_id INTEGER REFERENCES users(id),
          tag TEXT NOT NULL DEFAULT 'AI INSIGHT',
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          image_url TEXT,
          card_kind TEXT NOT NULL DEFAULT 'article',
          sort_order INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          expires_at TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          essence TEXT,
          reading_text TEXT,
          frame_images TEXT
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_daily_insight_cards_vin ON daily_insight_cards(vin, is_active, created_at DESC);",
        """
        CREATE TABLE IF NOT EXISTS daily_insight_opinions (
          id SERIAL PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id),
          card_id INTEGER NOT NULL REFERENCES daily_insight_cards(id) ON DELETE CASCADE,
          body TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_daily_insight_opinions_card ON daily_insight_opinions(card_id, created_at DESC);",
        """
        CREATE TABLE IF NOT EXISTS exo_health_checks (
          vin TEXT PRIMARY KEY,
          checked_at TEXT NOT NULL,
          ok INTEGER NOT NULL DEFAULT 1
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
          user_id INTEGER PRIMARY KEY REFERENCES users(id),
          prefs_json TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS exo_scheduler_state (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          last_cycle_at TEXT,
          last_cycle_insights INTEGER DEFAULT 0,
          last_cycle_duration_sec DOUBLE PRECISION,
          last_cycle_vehicles INTEGER DEFAULT 0,
          last_cycle_errors INTEGER DEFAULT 0,
          updated_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
          id SERIAL PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id),
          thread_id TEXT NOT NULL,
          role TEXT NOT NULL,
          body TEXT NOT NULL,
          meta_json TEXT,
          created_at TEXT NOT NULL
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_thread ON chat_messages(user_id, thread_id, created_at);",
        """
        CREATE TABLE IF NOT EXISTS vehicle_insights (
          id SERIAL PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id),
          vin TEXT NOT NULL,
          created_at TEXT NOT NULL,
          question TEXT NOT NULL,
          question_hash TEXT NOT NULL,
          analysis_json TEXT NOT NULL,
          score DOUBLE PRECISION
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_vehicle_insights_cache
        ON vehicle_insights(user_id, vin, question_hash, created_at DESC);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_vehicle_insights_user_vin
        ON vehicle_insights(user_id, vin, created_at DESC);
        """,
        """
        CREATE TABLE IF NOT EXISTS market_intel_sources (
          id SERIAL PRIMARY KEY,
          model_key TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_title TEXT,
          source_type TEXT NOT NULL,
          lang TEXT,
          raw_excerpt TEXT,
          fetched_at TEXT NOT NULL
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_market_intel_sources_model
        ON market_intel_sources(model_key, fetched_at DESC);
        """,
        """
        CREATE TABLE IF NOT EXISTS market_intel_synthesis (
          model_key TEXT PRIMARY KEY,
          synthesis_ro TEXT NOT NULL,
          synthesis_json TEXT,
          sources_count INTEGER DEFAULT 0,
          groq_model TEXT,
          updated_at TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS mlbr_files (
          id SERIAL PRIMARY KEY,
          mlbr_id TEXT UNIQUE NOT NULL,
          vin TEXT UNIQUE NOT NULL,
          file_data TEXT NOT NULL,
          signature TEXT NOT NULL,
          generated_at TEXT NOT NULL,
          is_locked INTEGER DEFAULT 1,
          views INTEGER DEFAULT 0,
          last_viewed TEXT
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_mlbr_files_vin ON mlbr_files(vin);",
        "CREATE INDEX IF NOT EXISTS idx_mlbr_files_mlbr ON mlbr_files(mlbr_id);",
        """
        CREATE TABLE IF NOT EXISTS auth_audit (
          id SERIAL PRIMARY KEY,
          created_at TEXT NOT NULL,
          status TEXT NOT NULL,
          user_id INTEGER,
          session_hash TEXT NOT NULL,
          path TEXT,
          ip_hash TEXT,
          encrypted_identifier TEXT,
          encrypted_ip TEXT,
          encrypted_user_agent TEXT
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_auth_audit_user_time ON auth_audit(user_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_auth_audit_status_time ON auth_audit(status, created_at);",
    ]
