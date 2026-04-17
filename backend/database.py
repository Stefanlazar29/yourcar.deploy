"""
database.py — SQLite local (dev) sau PostgreSQL (Supabase / DATABASE_URL).
Tabele: users, cars, exo_*, chat, MLBR, auth_audit, …"""

import hashlib
import os
import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple, Union


DB_PATH = os.getenv("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "dev.db"))


def _uses_postgres() -> bool:
    return bool((os.getenv("DATABASE_URL") or "").strip())


def connect() -> Union[sqlite3.Connection, Any]:
    if _uses_postgres():
        from backend.pg_adapter import connect_pg

        return connect_pg()
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def _init_db_postgres() -> None:
    from backend.pg_adapter import connect_pg, run_ddl_pg
    from backend.schema_postgres import postgres_ddl

    print("[DB] Init PostgreSQL (Supabase / DATABASE_URL)")
    con = connect_pg()
    try:
        run_ddl_pg(con, postgres_ddl())
        raw = con._conn
        cur = raw.cursor()
        cur.execute(
            "INSERT INTO exo_scheduler_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
        )
        cur.close()
        raw.commit()
        con.execute(
            """
            UPDATE users
            SET identifier =
              CASE
                WHEN identifier IS NOT NULL AND identifier != '' THEN identifier
                WHEN email IS NOT NULL AND email != '' THEN lower(email)
                WHEN phone IS NOT NULL AND phone != '' THEN replace(replace(replace(replace(phone,' ',''), chr(9), ''), chr(10), ''), chr(13), '')
                ELSE NULL
              END
            WHERE identifier IS NULL OR identifier = '';
            """
        )
        con.commit()
        print("[DB] PostgreSQL tables OK (users, cars, vehicle_brains, exo_*).")
    except Exception as e:
        print(f"[DB] init_db_postgres error: {e}")
        raise
    finally:
        con.close()


def init_db() -> None:
    if _uses_postgres():
        _init_db_postgres()
        return
    con = connect()
    try:
        print(f"[DB] Init SQLite: {DB_PATH}")
        # Create tables if missing
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              identifier TEXT UNIQUE,
              email TEXT,
              phone TEXT,
              password_hash TEXT,
              created_at TEXT
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS cars (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
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
              ycs_score REAL,
              updated_at TEXT,
              FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        
        # Tabel pentru MulberryBrain (VIN-centric JSON storage)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicle_brains (
              vin TEXT PRIMARY KEY,
              brain_data TEXT NOT NULL,
              last_sync TEXT
            );
            """
        )

        # EXO-Observer: Daily Insights + Health Checks
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS exo_daily_insights (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              vin TEXT NOT NULL,
              insight_text TEXT NOT NULL,
              insight_type TEXT DEFAULT 'general',
              raw_context TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_insight_cards (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              vin TEXT NOT NULL,
              user_id INTEGER,
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
              reading_text TEXT
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_insight_cards_vin ON daily_insight_cards(vin, is_active, created_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_insight_opinions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              card_id INTEGER NOT NULL,
              body TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id),
              FOREIGN KEY(card_id) REFERENCES daily_insight_cards(id) ON DELETE CASCADE
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_insight_opinions_card ON daily_insight_opinions(card_id, created_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS exo_health_checks (
              vin TEXT PRIMARY KEY,
              checked_at TEXT NOT NULL,
              ok INTEGER NOT NULL DEFAULT 1
            );
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
              user_id INTEGER PRIMARY KEY,
              prefs_json TEXT NOT NULL DEFAULT '{}',
              updated_at TEXT,
              FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS exo_scheduler_state (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              last_cycle_at TEXT,
              last_cycle_insights INTEGER DEFAULT 0,
              last_cycle_duration_sec REAL,
              last_cycle_vehicles INTEGER DEFAULT 0,
              last_cycle_errors INTEGER DEFAULT 0,
              updated_at TEXT
            );
            """
        )
        con.execute("INSERT OR IGNORE INTO exo_scheduler_state (id) VALUES (1);")

        # Chat Mulberry Assistant — mesaje per user + thread (Style Gemini / istoric)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              thread_id TEXT NOT NULL,
              role TEXT NOT NULL,
              body TEXT NOT NULL,
              meta_json TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_thread ON chat_messages(user_id, thread_id, created_at);"
        )

        # Insight-uri analiză business (Groq) — cache per user + VIN + întrebare (24h)
        con.execute(
            """
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
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_vehicle_insights_cache "
            "ON vehicle_insights(user_id, vin, question_hash, created_at DESC);"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_vehicle_insights_user_vin "
            "ON vehicle_insights(user_id, vin, created_at DESC);"
        )

        # Intel piață model (ex. Škoda Fabia 6Y) — surse Wikipedia + sinteză Groq, refresh periodic
        con.execute(
            """
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
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_market_intel_sources_model "
            "ON market_intel_sources(model_key, fetched_at DESC);"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS market_intel_synthesis (
              model_key TEXT PRIMARY KEY,
              synthesis_ro TEXT NOT NULL,
              synthesis_json TEXT,
              sources_count INTEGER DEFAULT 0,
              groq_model TEXT,
              updated_at TEXT NOT NULL
            );
            """
        )

        # MLBR Digital File — document imuabil per vehicul
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mlbr_files (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              mlbr_id TEXT UNIQUE NOT NULL,
              vin TEXT UNIQUE NOT NULL,
              file_data TEXT NOT NULL,
              signature TEXT NOT NULL,
              generated_at TEXT NOT NULL,
              is_locked INTEGER DEFAULT 1,
              views INTEGER DEFAULT 0,
              last_viewed TEXT
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mlbr_files_vin ON mlbr_files(vin);"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mlbr_files_mlbr ON mlbr_files(mlbr_id);"
        )
        con.execute("DROP TRIGGER IF EXISTS mlbr_file_immutable;")
        con.execute(
            """
            CREATE TRIGGER mlbr_file_immutable
            BEFORE UPDATE ON mlbr_files
            FOR EACH ROW
            WHEN (
              OLD.vin IS NOT NEW.vin OR OLD.mlbr_id IS NOT NEW.mlbr_id OR OLD.signature IS NOT NEW.signature
              OR OLD.file_data IS NOT NEW.file_data OR OLD.generated_at IS NOT NEW.generated_at
              OR OLD.is_locked IS NOT NEW.is_locked
            )
            BEGIN
              SELECT RAISE(ABORT, 'MLBR file is immutable');
            END;
            """
        )

        # Lightweight migrations for older dev.db
        def _has_col(table: str, col: str) -> bool:
            rows = con.execute(f"PRAGMA table_info({table});").fetchall()
            return any(r["name"] == col for r in rows)

        def _add_col(table: str, col: str, ddl: str) -> None:
            if not _has_col(table, col):
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl};")

        _add_col("users", "identifier", "TEXT")
        _add_col("users", "email", "TEXT")
        _add_col("users", "phone", "TEXT")
        _add_col("users", "password_hash", "TEXT")
        _add_col("users", "created_at", "TEXT")
        _add_col("users", "role", "TEXT")
        _add_col("users", "device_hwid_hash", "TEXT")

        _add_col("cars", "km_actuali", "INTEGER")
        _add_col("cars", "rca_expiry", "TEXT")
        _add_col("cars", "itp_expiry", "TEXT")
        _add_col("cars", "ycs_score", "REAL")
        _add_col("cars", "updated_at", "TEXT")
        _add_col("cars", "mlbr_code", "TEXT")
        _add_col("cars", "profile_narrative", "TEXT")
        _add_col("cars", "profile_narrative_at", "TEXT")

        _add_col("daily_insight_cards", "essence", "TEXT")
        _add_col("daily_insight_cards", "reading_text", "TEXT")
        _add_col("daily_insight_cards", "frame_images", "TEXT")

        _add_col("exo_daily_insights", "engine", "TEXT")

        # Backfill identifier for existing rows that had only email/phone
        con.execute(
            """
            UPDATE users
            SET identifier =
              CASE
                WHEN identifier IS NOT NULL AND identifier != '' THEN identifier
                WHEN email IS NOT NULL AND email != '' THEN lower(email)
                WHEN phone IS NOT NULL AND phone != '' THEN replace(replace(replace(replace(phone,' ',''),'\t',''),'\n',''),'\r','')
                ELSE NULL
              END
            WHERE identifier IS NULL OR identifier = '';
            """
        )
        con.commit()
        print("[DB] Tables OK (users, cars, vehicle_brains, exo_*).")
    except Exception as e:
        print(f"[DB] init_db error: {e}")
        raise
    finally:
        con.close()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def normalize_identifier(raw: str) -> str:
    s = (raw or "").strip()
    if "@" in s:
        return s.lower()
    # telefon: scoatem spații
    return "".join(ch for ch in s if ch not in " \t\r\n")


def normalize_phone(raw: str) -> str:
    """Extrage doar cifrele din telefon (pentru Parola 2)."""
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def mlbr_code_from_vin(vin: str) -> str:
    """
    Cod MLBR stabil pentru același VIN (hash scurt SHA-256, format MLBR-XXXX-XXXX).
    Aliniat la logica din js/offline/appDB.js (mlbrCodeFromVin).
    """
    v = (vin or "").strip().upper().replace(" ", "")
    if not v:
        return "MLBR-0000-0000"
    digest = hashlib.sha256(v.encode("utf-8")).hexdigest()
    return f"MLBR-{digest[:4].upper()}-{digest[4:8].upper()}"


@dataclass
class UserRow:
    id: int
    identifier: str
    email: Optional[str]
    phone: Optional[str]
    password_hash: str
    created_at: str
    role: Optional[str] = "user"
    device_hwid_hash: Optional[str] = None


def _user_row_from_db(row: Any) -> UserRow:
    role_val = row["role"] if "role" in row.keys() and row["role"] else "user"
    dev = None
    if "device_hwid_hash" in row.keys():
        dev = row["device_hwid_hash"]
    return UserRow(
        id=row["id"],
        identifier=row["identifier"],
        email=row["email"],
        phone=row["phone"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
        role=role_val,
        device_hwid_hash=dev,
    )


def hash_device_fingerprint(device_raw: str) -> str:
    """Hash stabil pentru X-Mulberry-Device-Id (fără stocare în clar)."""
    raw = (device_raw or "").strip().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_user_by_identifier(identifier: str) -> Optional[UserRow]:
    ident = normalize_identifier(identifier)
    con = connect()
    try:
        row = con.execute("SELECT * FROM users WHERE identifier = ? LIMIT 1", (ident,)).fetchone()
        if not row:
            return None
        return _user_row_from_db(row)
    finally:
        con.close()


def get_user_by_id(user_id: int) -> Optional[UserRow]:
    con = connect()
    try:
        row = con.execute("SELECT * FROM users WHERE id = ? LIMIT 1", (int(user_id),)).fetchone()
        if not row:
            return None
        return _user_row_from_db(row)
    finally:
        con.close()


def set_user_device_hwid(user_id: int, hw_hash: Optional[str]) -> None:
    con = connect()
    try:
        con.execute(
            "UPDATE users SET device_hwid_hash = ? WHERE id = ?",
            (hw_hash, int(user_id)),
        )
        con.commit()
    finally:
        con.close()


@dataclass
class CarRow:
    id: int
    user_id: int
    ycr_id: Optional[str]
    make: Optional[str]
    model: Optional[str]
    year: Optional[str]
    fuel: Optional[str]
    plate: Optional[str]
    vin: Optional[str]
    series: Optional[str]
    ycr_code: Optional[str]
    km_actuali: Optional[int]
    rca_expiry: Optional[str]
    itp_expiry: Optional[str]
    ycs_score: Optional[float]
    updated_at: Optional[str]
    mlbr_code: Optional[str] = None
    profile_narrative: Optional[str] = None
    profile_narrative_at: Optional[str] = None


def get_first_car() -> Optional[CarRow]:
    con = connect()
    try:
        row = con.execute("SELECT * FROM cars ORDER BY id ASC LIMIT 1").fetchone()
        if not row:
            return None
        return CarRow(**{k: row[k] for k in row.keys()})
    finally:
        con.close()


def get_car_for_user(user_id: int) -> Optional[CarRow]:
    """Returnează prima mașină înregistrată pentru user."""
    con = connect()
    try:
        row = con.execute("SELECT * FROM cars WHERE user_id = ? ORDER BY id ASC LIMIT 1", (user_id,)).fetchone()
        if not row:
            return None
        return CarRow(**{k: row[k] for k in row.keys()})
    finally:
        con.close()


def get_car_by_vin(vin: str) -> Optional[CarRow]:
    """Returnează mașina asociată (make/model/year) după VIN."""
    vin_norm = (vin or "").strip().upper()
    if not vin_norm:
        return None
    con = connect()
    try:
        row = con.execute("SELECT * FROM cars WHERE vin = ? LIMIT 1", (vin_norm,)).fetchone()
        if not row:
            return None
        return CarRow(**{k: row[k] for k in row.keys()})
    finally:
        con.close()


def resolve_mlbr_id_for_car(car: CarRow) -> str:
    """MLBR canonic pentru card / QR — ycr_id, coloană mlbr sau tabel mlbr_files."""
    if not car:
        return ""
    for cand in (getattr(car, "ycr_id", None), getattr(car, "mlbr_code", None)):
        if cand and str(cand).strip():
            return str(cand).strip()
    vin = (car.vin or "").strip().upper()
    if vin:
        row = mlbr_get_by_vin(vin)
        if row and row.get("mlbr_id"):
            return str(row["mlbr_id"])
    return ""


def get_car_by_user_and_vin(user_id: int, vin: str) -> Optional[CarRow]:
    """Mașina utilizatorului pentru VIN-ul dat."""
    vin_norm = (vin or "").strip().upper()
    if not vin_norm:
        return None
    con = connect()
    try:
        row = con.execute(
            "SELECT * FROM cars WHERE user_id = ? AND vin = ? LIMIT 1",
            (user_id, vin_norm),
        ).fetchone()
        if not row:
            return None
        return CarRow(**{k: row[k] for k in row.keys()})
    finally:
        con.close()


def set_car_ycr_id_for_vin(user_id: int, vin: str, ycr_id: str) -> None:
    con = connect()
    try:
        con.execute(
            "UPDATE cars SET ycr_id = ?, updated_at = ? WHERE user_id = ? AND vin = ?",
            (ycr_id, _now_iso(), user_id, (vin or "").strip().upper()),
        )
        con.commit()
    finally:
        con.close()


def patch_car_expiry_dates(
    user_id: int,
    vin: str,
    *,
    rca_expiry: Optional[str] = None,
    itp_expiry: Optional[str] = None,
) -> None:
    """Actualizează doar câmpurile de expirare furnizate (ex. după OCR / AI pe document Cloud)."""
    vin_norm = (vin or "").strip().upper()
    if not vin_norm:
        return
    pairs: List[tuple[str, str]] = []
    if rca_expiry is not None:
        pairs.append(("rca_expiry", str(rca_expiry).strip()[:32]))
    if itp_expiry is not None:
        pairs.append(("itp_expiry", str(itp_expiry).strip()[:32]))
    if not pairs:
        return
    con = connect()
    try:
        sets = ", ".join(f"{k}=?" for k, _ in pairs) + ", updated_at=?"
        vals = [v for _, v in pairs] + [_now_iso(), user_id, vin_norm]
        con.execute(
            f"UPDATE cars SET {sets} WHERE user_id=? AND vin=?",
            tuple(vals),
        )
        con.commit()
    finally:
        con.close()


def create_user(identifier: str, password_hash: str, phone: Optional[str] = None, role: str = "user") -> UserRow:
    ident = normalize_identifier(identifier)
    email = ident if "@" in ident else None
    phone_val = phone if phone else (None if "@" in ident else ident)
    con = connect()
    try:
        con.execute(
            "INSERT INTO users(identifier,email,phone,password_hash,created_at,role) VALUES(?,?,?,?,?,?)",
            (ident, email, phone_val, password_hash, _now_iso(), role),
        )
        con.commit()
        row = con.execute("SELECT * FROM users WHERE identifier = ? LIMIT 1", (ident,)).fetchone()
        if not row:
            raise RuntimeError("create_user: rând lipsă după INSERT")
        return _user_row_from_db(row)
    finally:
        con.close()


def upsert_car_for_user(user_id: int, payload: dict) -> None:
    con = connect()
    try:
        existing = con.execute("SELECT id FROM cars WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
        fields = {
            "make": payload.get("make"),
            "model": payload.get("model"),
            "year": payload.get("year"),
            "fuel": payload.get("fuel"),
            "plate": payload.get("plate"),
            "vin": payload.get("vin"),
            "series": payload.get("series"),
            "ycr_id": payload.get("ycr_id"),
            "ycr_code": payload.get("ycr_code"),
            "mlbr_code": payload.get("mlbr_code"),
            "km_actuali": payload.get("km_actuali"),
            "rca_expiry": payload.get("rca_expiry"),
            "itp_expiry": payload.get("itp_expiry"),
            "ycs_score": payload.get("ycs_score"),
            "updated_at": _now_iso(),
        }
        if existing:
            sets = ", ".join([f"{k}=?" for k in fields.keys()])
            con.execute(
                f"UPDATE cars SET {sets} WHERE user_id=?",
                tuple(fields.values()) + (user_id,),
            )
        else:
            cols = ", ".join(["user_id"] + list(fields.keys()))
            qs = ", ".join(["?"] * (1 + len(fields)))
            con.execute(
                f"INSERT INTO cars({cols}) VALUES({qs})",
                (user_id,) + tuple(fields.values()),
            )
        con.commit()
    finally:
        con.close()


def sync_vehicle_from_client(user_id: int, raw: dict) -> dict:
    """
    Sincronizează vehiculul din obiectul frontend (marca/model/vin local sau API).
    - Dacă există rând pentru user_id + VIN → UPDATE.
    - Altfel, dacă există rând fără VIN → UPDATE (baseline).
    - Altfel → INSERT.
    """
    vin = (raw.get("vin") or "").strip().upper()
    if not vin or len(vin) != 17:
        raise ValueError("VIN invalid (17 caractere).")
    mlbr = mlbr_code_from_vin(vin)
    make = raw.get("marca") or raw.get("make")
    model = raw.get("model")
    year = raw.get("an") if raw.get("an") is not None else raw.get("year")
    fuel = raw.get("combustibil") or raw.get("fuel")
    plate_raw = raw.get("nr") if raw.get("nr") is not None else raw.get("plate")
    plate = (str(plate_raw).strip().upper() if plate_raw not in (None, "") else "") or None
    series = raw.get("serie") or raw.get("series")

    existing = get_car_by_user_and_vin(user_id, vin)
    fields = {
        "make": make,
        "model": model,
        "year": str(year) if year is not None else None,
        "fuel": fuel,
        "plate": plate,
        "vin": vin,
        "series": series,
        "ycr_code": mlbr,
        "mlbr_code": mlbr,
        "updated_at": _now_iso(),
    }
    con = connect()
    try:
        if existing:
            sets = ", ".join([f"{k}=?" for k in fields.keys()])
            con.execute(
                f"UPDATE cars SET {sets} WHERE user_id=? AND vin=?",
                tuple(fields.values()) + (user_id, vin),
            )
        else:
            orphan = con.execute(
                "SELECT id FROM cars WHERE user_id=? AND (vin IS NULL OR trim(vin)='') LIMIT 1",
                (user_id,),
            ).fetchone()
            if orphan:
                sets = ", ".join([f"{k}=?" for k in fields.keys()])
                con.execute(
                    f"UPDATE cars SET {sets} WHERE id=?",
                    tuple(fields.values()) + (orphan["id"],),
                )
            else:
                cols = ", ".join(["user_id"] + list(fields.keys()))
                qs = ", ".join(["?"] * (1 + len(fields)))
                con.execute(
                    f"INSERT INTO cars({cols}) VALUES({qs})",
                    (user_id,) + tuple(fields.values()),
                )
        con.commit()
    finally:
        con.close()
    return {"status": "SYNC_COMPLETE", "vin": vin, "mlbr_code": mlbr}


# ────────────────────────────────────────────────────────────────
# MulberryBrain (VIN-centric orchestrator storage)
# ────────────────────────────────────────────────────────────────

def get_vehicle_brain(vin: str) -> Optional["MulberryBrain"]:
    """Încarcă MulberryBrain din DB bazat pe VIN"""
    con = connect()
    try:
        row = con.execute("SELECT brain_data FROM vehicle_brains WHERE vin = ? LIMIT 1", (vin,)).fetchone()
        if not row:
            return None
        
        # Import lazy pentru a evita circularitatea
        from backend.models import MulberryBrain
        data = json.loads(row["brain_data"])
        return MulberryBrain(**data)
    finally:
        con.close()


def get_all_cars_with_vin():
    """Returnează toate mașinile cu VIN pentru EXO Research."""
    con = connect()
    try:
        rows = con.execute(
            "SELECT * FROM cars WHERE vin IS NOT NULL AND vin != '' ORDER BY id ASC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def count_cars() -> int:
    """Număr total înregistrări în `cars` (inventar flotă)."""
    con = connect()
    try:
        row = con.execute("SELECT COUNT(*) AS n FROM cars").fetchone()
        return int(row["n"]) if row else 0
    finally:
        con.close()


def insert_exo_insight(
    vin: str,
    insight_text: str,
    insight_type: str = "general",
    raw_context: str = None,
    engine: str = "exo_intelligence",
) -> None:
    """
    engine: exo_intelligence (MiniMax per vehicul) | exo_research (crawler) |
            exo_research_ollama (legacy) | manual
    """
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO exo_daily_insights(vin, insight_text, insight_type, raw_context, engine, created_at)
            VALUES(?,?,?,?,?,?)
            """,
            (vin, insight_text, insight_type, raw_context or "", engine or "exo_intelligence", _now_iso()),
        )
        con.commit()
    finally:
        con.close()


def get_last_exo_intelligence_insight_at(vin: str) -> Optional[str]:
    """Ultimul insight din ciclul EXO Intelligence (pentru rotație cost API)."""
    vin_norm = (vin or "").strip().upper()
    if not vin_norm:
        return None
    con = connect()
    try:
        row = con.execute(
            """
            SELECT MAX(created_at) AS m FROM exo_daily_insights
            WHERE vin = ? AND COALESCE(engine, 'exo_intelligence') = 'exo_intelligence'
            """,
            (vin_norm,),
        ).fetchone()
        return row["m"] if row and row["m"] else None
    finally:
        con.close()


def get_exo_insights(vin: str, limit: int = 5) -> list:
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT insight_text, insight_type, created_at, engine
            FROM exo_daily_insights
            WHERE vin = ?
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (vin, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def replace_daily_insight_cards_for_vin(
    vin: str,
    user_id: Optional[int],
    cards: List[dict],
) -> None:
    """Înlocuiește cardurile Daily Insights pentru VIN (batch nightly sau refresh manual)."""
    vin_n = (vin or "").strip().upper()
    if not vin_n:
        return
    con = connect()
    try:
        con.execute("DELETE FROM daily_insight_cards WHERE vin = ?", (vin_n,))
        now = _now_iso()
        for i, c in enumerate(cards):
            title = (c.get("title") or "").strip()
            url = (c.get("url") or "").strip()
            if not title or not url:
                continue
            fi = c.get("frame_images")
            if fi is not None and not isinstance(fi, str):
                try:
                    fi = json.dumps(fi, ensure_ascii=False)
                except Exception:
                    fi = None
            elif isinstance(fi, str):
                fi = fi.strip() or None
            con.execute(
                """
                INSERT INTO daily_insight_cards(
                  vin, user_id, tag, title, url, image_url, card_kind, sort_order, created_at, is_active,
                  essence, reading_text, frame_images
                ) VALUES (?,?,?,?,?,?,?,?,?,1,?,?,?)
                """,
                (
                    vin_n,
                    user_id,
                    ((c.get("tag") or "AI INSIGHT").strip())[:64],
                    title[:500],
                    url[:2000],
                    ((c.get("image_url") or "").strip() or None),
                    ((c.get("kind") or c.get("card_kind") or "article").strip())[:32],
                    i,
                    now,
                    ((c.get("essence") or "").strip() or None),
                    ((c.get("reading_text") or "").strip() or None),
                    (fi[:12000] if fi else None),
                ),
            )
        con.commit()
    finally:
        con.close()


def get_daily_insight_cards_for_vin(vin: str, limit: int = 8) -> List[dict]:
    vin_n = (vin or "").strip().upper()
    if not vin_n:
        return []
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT id, tag, title, url, image_url, card_kind, sort_order, created_at,
                   essence, reading_text, frame_images
            FROM daily_insight_cards
            WHERE vin = ? AND is_active = 1
            ORDER BY sort_order ASC, datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (vin_n, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_recent_daily_insight_titles(vin: str, limit: int = 24) -> List[str]:
    """Titluri din batch-uri anterioare — folosite ca SUBIECTE_DE_EVITAT la generare MulberryEXO (fără repetări)."""
    vin_n = (vin or "").strip().upper()
    if not vin_n:
        return []
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT title FROM daily_insight_cards
            WHERE vin = ? AND is_active = 1
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (vin_n, max(1, min(limit, 80))),
        ).fetchall()
        out: List[str] = []
        for r in rows:
            t = (r["title"] or "").strip()
            if t and t not in out:
                out.append(t)
        return out
    finally:
        con.close()


def get_daily_insight_card_id_by_vin_sort(vin: str, sort_order: int) -> Optional[int]:
    vin_n = (vin or "").strip().upper()
    if not vin_n:
        return None
    con = connect()
    try:
        row = con.execute(
            """
            SELECT id FROM daily_insight_cards
            WHERE vin = ? AND sort_order = ? AND is_active = 1
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 1
            """,
            (vin_n, int(sort_order)),
        ).fetchone()
        return int(row["id"]) if row else None
    finally:
        con.close()


def daily_insight_card_belongs_to_vin(card_id: int, vin: str) -> bool:
    vin_n = (vin or "").strip().upper()
    if not vin_n or not card_id:
        return False
    con = connect()
    try:
        row = con.execute(
            "SELECT 1 AS o FROM daily_insight_cards WHERE id = ? AND vin = ? AND is_active = 1 LIMIT 1",
            (int(card_id), vin_n),
        ).fetchone()
        return bool(row)
    finally:
        con.close()


def insert_daily_insight_opinion(user_id: int, card_id: int, body: str) -> Tuple[int, str]:
    now = _now_iso()
    con = connect()
    try:
        cur = con.execute(
            """
            INSERT INTO daily_insight_opinions(user_id, card_id, body, created_at)
            VALUES (?,?,?,?)
            """,
            (int(user_id), int(card_id), (body or "").strip()[:8000], now),
        )
        con.commit()
        return int(cur.lastrowid), now
    finally:
        con.close()


def list_daily_insight_opinions_for_card(card_id: int, limit: int = 80) -> List[dict]:
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT o.id, o.body, o.created_at, u.identifier, u.email
            FROM daily_insight_opinions o
            JOIN users u ON u.id = o.user_id
            WHERE o.card_id = ?
            ORDER BY datetime(o.created_at) DESC
            LIMIT ?
            """,
            (int(card_id), max(1, min(limit, 200))),
        ).fetchall()
        out: List[dict] = []
        for r in rows:
            ident = (r["identifier"] or "").strip()
            em = (r["email"] or "").strip()
            if em and "@" in em:
                disp = em.split("@")[0][:32]
            elif ident:
                disp = ident[:32]
            else:
                disp = "utilizator"
            out.append(
                {
                    "id": int(r["id"]),
                    "body": r["body"],
                    "created_at": r["created_at"],
                    "author_display": disp,
                }
            )
        return out
    finally:
        con.close()


def latest_daily_insight_batch_created_at(vin: str) -> Optional[str]:
    vin_n = (vin or "").strip().upper()
    if not vin_n:
        return None
    con = connect()
    try:
        row = con.execute(
            "SELECT MAX(created_at) AS m FROM daily_insight_cards WHERE vin = ?",
            (vin_n,),
        ).fetchone()
        return row["m"] if row and row["m"] else None
    finally:
        con.close()


def upsert_exo_health(vin: str, ok: bool) -> None:
    con = connect()
    try:
        con.execute(
            "INSERT OR REPLACE INTO exo_health_checks(vin, checked_at, ok) VALUES(?,?,?)",
            (vin, _now_iso(), 1 if ok else 0),
        )
        con.commit()
    finally:
        con.close()


def get_exo_health(vin: str) -> Optional[dict]:
    con = connect()
    try:
        row = con.execute(
            "SELECT checked_at, ok FROM exo_health_checks WHERE vin = ? LIMIT 1",
            (vin,),
        ).fetchone()
        if not row:
            return None
        return {"checked_at": row["checked_at"], "ok": bool(row["ok"])}
    finally:
        con.close()


def get_user_preferences(user_id: int) -> dict:
    """Preferințe EXO per user (JSON)."""
    con = connect()
    try:
        row = con.execute(
            "SELECT prefs_json FROM user_preferences WHERE user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        if row and row["prefs_json"]:
            try:
                return json.loads(row["prefs_json"])
            except Exception:
                pass
    finally:
        con.close()
    return {
        "usage": "mixed",
        "budget": "medium",
        "concerns": [],
        "location": "Romania",
    }


def upsert_user_preferences(user_id: int, prefs: dict) -> None:
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO user_preferences(user_id, prefs_json, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                prefs_json = excluded.prefs_json,
                updated_at = excluded.updated_at
            """,
            (user_id, json.dumps(prefs or {}, ensure_ascii=False), _now_iso()),
        )
        con.commit()
    finally:
        con.close()


def update_exo_scheduler_state(
    last_cycle_at: str,
    insights: int,
    duration_sec: float,
    vehicles: int,
    errors: int,
) -> None:
    """Ultimul ciclu EXO Intelligence (MiniMax), un singur rând id=1."""
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO exo_scheduler_state(
                id, last_cycle_at, last_cycle_insights, last_cycle_duration_sec,
                last_cycle_vehicles, last_cycle_errors, updated_at
            )
            VALUES(1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_cycle_at = excluded.last_cycle_at,
                last_cycle_insights = excluded.last_cycle_insights,
                last_cycle_duration_sec = excluded.last_cycle_duration_sec,
                last_cycle_vehicles = excluded.last_cycle_vehicles,
                last_cycle_errors = excluded.last_cycle_errors,
                updated_at = excluded.updated_at
            """,
            (last_cycle_at, insights, duration_sec, vehicles, errors, _now_iso()),
        )
        con.commit()
    finally:
        con.close()


def get_exo_scheduler_state() -> dict:
    con = connect()
    try:
        row = con.execute("SELECT * FROM exo_scheduler_state WHERE id = 1").fetchone()
        if not row:
            return {}
        return dict(row)
    finally:
        con.close()


def update_vehicle_brain(vin: str, brain: "MulberryBrain") -> None:
    """Salvează/actualizează MulberryBrain în DB"""
    con = connect()
    try:
        brain_json = brain.model_dump_json()
        last_sync = brain.last_sync
        
        existing = con.execute("SELECT vin FROM vehicle_brains WHERE vin = ? LIMIT 1", (vin,)).fetchone()
        
        if existing:
            con.execute(
                "UPDATE vehicle_brains SET brain_data = ?, last_sync = ? WHERE vin = ?",
                (brain_json, last_sync, vin),
            )
        else:
            con.execute(
                "INSERT INTO vehicle_brains(vin, brain_data, last_sync) VALUES(?, ?, ?)",
                (vin, brain_json, last_sync),
            )
        
        con.commit()
    finally:
        con.close()


def append_chat_message(
    user_id: int,
    thread_id: str,
    role: str,
    body: str,
    meta: Optional[dict] = None,
) -> None:
    """Persistă un mesaj chat (user sau assistant) în SQLite."""
    tid = (thread_id or "default").strip()[:128] or "default"
    r = (role or "user").strip().lower()
    if r not in ("user", "assistant", "system"):
        r = "user"
    meta_s = json.dumps(meta, ensure_ascii=False) if meta else None
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO chat_messages(user_id, thread_id, role, body, meta_json, created_at)
            VALUES(?,?,?,?,?,?)
            """,
            (user_id, tid, r, body or "", meta_s, _now_iso()),
        )
        con.commit()
    finally:
        con.close()


def list_chat_messages(user_id: int, thread_id: str, limit: int = 200) -> List[dict]:
    """Istoric mesaje pentru un thread, cronologic."""
    tid = (thread_id or "default").strip()[:128] or "default"
    lim = max(1, min(limit, 500))
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT role, body, created_at, meta_json FROM chat_messages
            WHERE user_id = ? AND thread_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (user_id, tid, lim),
        ).fetchall()
        out = []
        for row in rows:
            out.append(
                {
                    "role": row["role"],
                    "text": row["body"],
                    "created_at": row["created_at"],
                    "meta": json.loads(row["meta_json"]) if row["meta_json"] else None,
                }
            )
        return out
    finally:
        con.close()


def list_chat_threads(user_id: int, limit: int = 40) -> List[dict]:
    """Thread-uri distincte, cele mai recente primele."""
    lim = max(1, min(limit, 100))
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT thread_id, MAX(created_at) AS last_at
            FROM chat_messages
            WHERE user_id = ?
            GROUP BY thread_id
            ORDER BY last_at DESC
            LIMIT ?
            """,
            (user_id, lim),
        ).fetchall()
        return [{"thread_id": r["thread_id"], "updated_at": r["last_at"]} for r in rows]
    finally:
        con.close()


def list_recent_chat_messages_for_user(user_id: int, limit: int = 20) -> List[dict]:
    """Ultimele mesaje chat ale userului (toate thread-urile), ordine cronologică."""
    lim = max(1, min(int(limit), 80))
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT role, body, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, lim),
        ).fetchall()
        rev = list(reversed(rows))
        return [{"role": r["role"], "text": r["body"], "created_at": r["created_at"]} for r in rev]
    finally:
        con.close()


def set_car_profile_narrative(user_id: int, narrative: str, at_iso: Optional[str] = None) -> None:
    """Salvează textul generat pentru cardul MyMulberry (descriere profil)."""
    ts = at_iso or _now_iso()
    con = connect()
    try:
        con.execute(
            """
            UPDATE cars
            SET profile_narrative = ?, profile_narrative_at = ?, updated_at = ?
            WHERE user_id = ?
            """,
            ((narrative or "").strip(), ts, ts, user_id),
        )
        con.commit()
    finally:
        con.close()


# ────────────────────────────────────────────────────────────────
# MLBR Digital File
# ────────────────────────────────────────────────────────────────


def mlbr_get_by_vin(vin: str) -> Optional[dict]:
    vin_norm = (vin or "").strip().upper()
    if not vin_norm:
        return None
    con = connect()
    try:
        row = con.execute("SELECT * FROM mlbr_files WHERE vin = ? LIMIT 1", (vin_norm,)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        con.close()


def mlbr_get_by_mlbr_id(mlbr_id: str) -> Optional[dict]:
    if not mlbr_id:
        return None
    con = connect()
    try:
        row = con.execute("SELECT * FROM mlbr_files WHERE mlbr_id = ? LIMIT 1", (mlbr_id.strip(),)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        con.close()


def mlbr_insert(row: dict) -> None:
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO mlbr_files(mlbr_id, vin, file_data, signature, generated_at, is_locked, views, last_viewed)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                row["mlbr_id"],
                row["vin"],
                row["file_data"],
                row["signature"],
                row["generated_at"],
                row.get("is_locked", 1),
                row.get("views", 0),
                row.get("last_viewed"),
            ),
        )
        con.commit()
    finally:
        con.close()


def mlbr_increment_views(mlbr_id: str) -> int:
    mid = (mlbr_id or "").strip()
    con = connect()
    try:
        con.execute(
            """
            UPDATE mlbr_files
            SET views = COALESCE(views, 0) + 1, last_viewed = ?
            WHERE mlbr_id = ?
            """,
            (_now_iso(), mid),
        )
        con.commit()
        row = con.execute("SELECT views FROM mlbr_files WHERE mlbr_id = ? LIMIT 1", (mid,)).fetchone()
        return int(row["views"]) if row else 0
    finally:
        con.close()


# ── vehicle_insights (analiză business + cache) ───────────────────────────


def _vin_norm_insight(vin: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9]", "", (vin or "").strip()).upper()


def vehicle_insight_question_hash(question: str) -> str:
    n = " ".join((question or "").strip().lower().split())
    return hashlib.sha256(n.encode("utf-8")).hexdigest()


def vehicle_insight_get_cached(
    user_id: int,
    vin: str,
    question: str,
    *,
    hours: int = 24,
) -> Optional[dict]:
    """Răspuns cache dacă aceeași întrebare (normalizată) + VIN + user în fereastra `hours`."""
    v = _vin_norm_insight(vin)
    qh = vehicle_insight_question_hash(question)
    con = connect()
    try:
        row = con.execute(
            """
            SELECT id, analysis_json, score, created_at
            FROM vehicle_insights
            WHERE user_id = ? AND vin = ? AND question_hash = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, v, qh),
        ).fetchone()
        if not row:
            return None
        created = row["created_at"] or ""
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < datetime.now(timezone.utc) - timedelta(hours=hours):
                return None
        except Exception:
            return None
        try:
            payload = json.loads(row["analysis_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        reply = (payload.get("reply") or "").strip()
        if not reply:
            return None
        return {
            "id": int(row["id"]),
            "reply": reply,
            "score": row["score"],
            "created_at": created,
            "analysis": payload,
        }
    finally:
        con.close()


def vehicle_insight_insert(
    user_id: int,
    vin: str,
    question: str,
    analysis: dict,
    score: Optional[float] = None,
) -> int:
    v = _vin_norm_insight(vin)
    qh = vehicle_insight_question_hash(question)
    now = _now_iso()
    body = json.dumps(analysis, ensure_ascii=False)
    con = connect()
    try:
        cur = con.execute(
            """
            INSERT INTO vehicle_insights
            (user_id, vin, created_at, question, question_hash, analysis_json, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, v, now, question.strip(), qh, body, score),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def vehicle_insight_latest_for_vehicle(user_id: int, vin: str) -> Optional[dict]:
    """Ultimul insight pentru mașina reală a utilizatorului (siguranță: filtrare user + VIN)."""
    v = _vin_norm_insight(vin)
    con = connect()
    try:
        row = con.execute(
            """
            SELECT id, question, analysis_json, score, created_at
            FROM vehicle_insights
            WHERE user_id = ? AND vin = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, v),
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["analysis_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        reply = (payload.get("reply") or "").strip()
        if not reply and payload.get("softscore") is not None:
            mv = payload.get("market_value")
            cur = payload.get("currency") or "EUR"
            reply = f"SoftScore {payload.get('softscore')}/100 · ~{mv} {cur}"
        preview = (reply[:280] + "…") if len(reply) > 280 else reply
        return {
            "id": int(row["id"]),
            "question": row["question"],
            "reply": reply,
            "preview": preview,
            "score": row["score"],
            "created_at": row["created_at"],
            "within_24h": _insight_within_hours(row["created_at"], 24),
        }
    finally:
        con.close()


def vehicle_insight_latest_for_question(user_id: int, vin: str, question: str) -> Optional[dict]:
    v = _vin_norm_insight(vin)
    qh = vehicle_insight_question_hash(question)
    con = connect()
    try:
        row = con.execute(
            """
            SELECT id, question, analysis_json, score, created_at
            FROM vehicle_insights
            WHERE user_id = ? AND vin = ? AND question_hash = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, v, qh),
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["analysis_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        reply = (payload.get("reply") or "").strip()
        if not reply and payload.get("softscore") is not None:
            mv = payload.get("market_value")
            cur = payload.get("currency") or "EUR"
            reply = f"SoftScore {payload.get('softscore')}/100 · ~{mv} {cur}"
        preview = (reply[:280] + "…") if len(reply) > 280 else reply
        return {
            "id": int(row["id"]),
            "question": row["question"],
            "reply": reply,
            "preview": preview,
            "score": row["score"],
            "created_at": row["created_at"],
            "within_24h": _insight_within_hours(row["created_at"], 24),
            "analysis_json": row["analysis_json"],
        }
    finally:
        con.close()


def vehicle_insight_get_by_id(user_id: int, insight_id: int, expected_vin: str) -> Optional[dict]:
    """Citire insight doar dacă aparține userului și VIN-ul coincide cu mașina înregistrată."""
    v = _vin_norm_insight(expected_vin)
    con = connect()
    try:
        row = con.execute(
            """
            SELECT id, vin, question, analysis_json, score, created_at
            FROM vehicle_insights
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (insight_id, user_id),
        ).fetchone()
        if not row or _vin_norm_insight(row["vin"]) != v:
            return None
        try:
            payload = json.loads(row["analysis_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        return {
            "id": int(row["id"]),
            "vin": row["vin"],
            "question": row["question"],
            "reply": (payload.get("reply") or "").strip(),
            "analysis": payload,
            "score": row["score"],
            "created_at": row["created_at"],
        }
    finally:
        con.close()


def _insight_within_hours(created_at: str, hours: int) -> bool:
    try:
        dt = datetime.fromisoformat((created_at or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)
    except Exception:
        return False


# ── Intel piață per model (Wikipedia + Groq) ─────────────────────────────────


MODEL_KEY_SKODA_FABIA_6Y = "skoda_fabia_6y"


def market_intel_replace_sources(model_key: str, rows: List[dict]) -> None:
    """Înlocuiește sursele pentru un model (un batch / un refresh)."""
    con = connect()
    try:
        con.execute("DELETE FROM market_intel_sources WHERE model_key = ?", (model_key,))
        now = _now_iso()
        for r in rows:
            con.execute(
                """
                INSERT INTO market_intel_sources
                (model_key, source_url, source_title, source_type, lang, raw_excerpt, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_key,
                    (r.get("source_url") or "").strip(),
                    (r.get("source_title") or "")[:500],
                    (r.get("source_type") or "wikipedia")[:80],
                    (r.get("lang") or "")[:12],
                    (r.get("raw_excerpt") or "")[:120000],
                    now,
                ),
            )
        con.commit()
    finally:
        con.close()


def market_intel_set_synthesis(
    model_key: str,
    synthesis_ro: str,
    synthesis_json: Optional[str],
    sources_count: int,
    groq_model: Optional[str] = None,
) -> None:
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO market_intel_synthesis
            (model_key, synthesis_ro, synthesis_json, sources_count, groq_model, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_key) DO UPDATE SET
              synthesis_ro = excluded.synthesis_ro,
              synthesis_json = excluded.synthesis_json,
              sources_count = excluded.sources_count,
              groq_model = excluded.groq_model,
              updated_at = excluded.updated_at
            """,
            (
                model_key,
                synthesis_ro[:200000],
                synthesis_json[:500000] if synthesis_json else None,
                int(sources_count),
                (groq_model or "")[:120],
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def market_intel_get_synthesis(model_key: str) -> Optional[dict]:
    con = connect()
    try:
        row = con.execute(
            """
            SELECT model_key, synthesis_ro, synthesis_json, sources_count, groq_model, updated_at
            FROM market_intel_synthesis WHERE model_key = ? LIMIT 1
            """,
            (model_key,),
        ).fetchone()
        if not row:
            return None
        return {
            "model_key": row["model_key"],
            "synthesis_ro": row["synthesis_ro"],
            "synthesis_json": row["synthesis_json"],
            "sources_count": int(row["sources_count"] or 0),
            "groq_model": row["groq_model"],
            "updated_at": row["updated_at"],
        }
    finally:
        con.close()


def market_intel_list_sources(model_key: str, limit: int = 30) -> List[dict]:
    con = connect()
    try:
        cur = con.execute(
            """
            SELECT source_url, source_title, source_type, lang, substr(raw_excerpt,1,400) AS excerpt_preview, fetched_at
            FROM market_intel_sources
            WHERE model_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (model_key, limit),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()
