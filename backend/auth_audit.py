import base64
import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


AUTH_AUDIT_DB_PATH = os.getenv(
    "AUTH_AUDIT_PATH",
    os.path.join(os.path.dirname(__file__), "auth_audit.db"),
)


@dataclass
class AuditSecuritySnapshot:
    last_login_at: Optional[str]
    security_alerts: List[str]


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(AUTH_AUDIT_DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def _resolve_aes_key() -> bytes:
    """
    AUTH_AUDIT_KEY poate fi:
    - base64-url (32 bytes decode)
    - hex (64 chars)
    - text arbitrar (derivat SHA-256).
    """
    raw = (os.getenv("AUTH_AUDIT_KEY", "") or "").strip()
    if raw:
        try:
            key = base64.urlsafe_b64decode(raw.encode("utf-8"))
            if len(key) == 32:
                return key
        except Exception:
            pass
        try:
            key = bytes.fromhex(raw)
            if len(key) == 32:
                return key
        except ValueError:
            pass
        return hashlib.sha256(raw.encode("utf-8")).digest()
    # fallback deterministic din JWT_SECRET, ca să nu pierdem decriptarea între restarturi
    jwt_secret = os.getenv("JWT_SECRET", "schimba-ma")
    return hashlib.sha256(("auth-audit|" + jwt_secret).encode("utf-8")).digest()


def _encrypt_text(value: str) -> str:
    plain = (value or "").encode("utf-8")
    nonce = os.urandom(12)
    aesgcm = AESGCM(_resolve_aes_key())
    ct = aesgcm.encrypt(nonce, plain, None)
    payload = nonce + ct
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decrypt_text(token: str) -> str:
    try:
        raw = base64.urlsafe_b64decode((token or "").encode("ascii"))
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(_resolve_aes_key())
        out = aesgcm.decrypt(nonce, ct, None)
        return out.decode("utf-8")
    except Exception:
        return ""


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def init_auth_audit_db() -> None:
    con = _connect()
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_auth_audit_user_time ON auth_audit(user_id, created_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_auth_audit_status_time ON auth_audit(status, created_at)")
        con.commit()
    finally:
        con.close()


def make_session_hash(identifier: str, ip: str, user_agent: str) -> str:
    seed = "|".join(
        [
            _now_iso(),
            identifier or "",
            ip or "",
            user_agent or "",
            secrets.token_hex(8),
        ]
    )
    return _sha256(seed)


def log_auth_attempt(
    *,
    identifier: str,
    status: str,
    user_id: Optional[int],
    ip_address: str,
    user_agent: str,
    path: str = "/auth/login",
    session_hash: Optional[str] = None,
) -> str:
    sess = session_hash or make_session_hash(identifier, ip_address, user_agent)
    con = _connect()
    try:
        con.execute(
            """
            INSERT INTO auth_audit(
              created_at, status, user_id, session_hash, path, ip_hash,
              encrypted_identifier, encrypted_ip, encrypted_user_agent
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                _now_iso(),
                status,
                user_id,
                sess,
                path,
                _sha256(ip_address or ""),
                _encrypt_text(identifier or ""),
                _encrypt_text(ip_address or ""),
                _encrypt_text(user_agent or ""),
            ),
        )
        con.commit()
        return sess
    finally:
        con.close()


def audit_events_last_hours(hours: int = 24) -> List[dict]:
    """Evenimente din auth_audit din ultimele `hours` ore (UTC)."""
    cutoff_dt = datetime.utcnow() - timedelta(hours=max(1, int(hours)))
    cutoff = cutoff_dt.isoformat(timespec="seconds")
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT id, created_at, status, user_id, path
            FROM auth_audit
            WHERE created_at >= ?
            ORDER BY id ASC
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def audit_summary_for_archive() -> dict:
    """Snapshot agregat pentru arhive zilnice (fără decriptare PII în clar)."""
    con = _connect()
    try:
        counts: dict = {}
        for row in con.execute("SELECT status, COUNT(*) AS n FROM auth_audit GROUP BY status"):
            counts[row["status"]] = row["n"]
        recent = con.execute(
            """
            SELECT id, created_at, status, user_id, path
            FROM auth_audit
            ORDER BY id DESC
            LIMIT 120
            """
        ).fetchall()
        return {
            "counts_by_status": counts,
            "recent_events": [dict(r) for r in recent],
        }
    finally:
        con.close()


def get_security_snapshot(user_id: int, current_ip: str) -> AuditSecuritySnapshot:
    con = _connect()
    try:
        last_success = con.execute(
            """
            SELECT created_at, encrypted_ip
            FROM auth_audit
            WHERE user_id = ? AND status = 'SUCCESS'
            ORDER BY id DESC
            LIMIT 2
            """,
            (user_id,),
        ).fetchall()
        if not last_success:
            return AuditSecuritySnapshot(last_login_at=None, security_alerts=[])

        last_login_at = last_success[0]["created_at"]
        alerts: List[str] = []
        if len(last_success) > 1:
            prev_ip = _decrypt_text(last_success[1]["encrypted_ip"])
            if prev_ip and current_ip and prev_ip != current_ip:
                alerts.append("Last login from unknown IP.")
        return AuditSecuritySnapshot(last_login_at=last_login_at, security_alerts=alerts)
    finally:
        con.close()
