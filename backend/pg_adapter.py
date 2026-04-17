"""
Adaptator PostgreSQL (psycopg2) compatibil cu apelurile tip sqlite3 din database.py:
connect().execute(...).fetchone() / fetchall(), commit(), close().
"""

from __future__ import annotations

import os
import re
from typing import Any, List, Optional, Sequence, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_engine = None


def _ensure_postgres_sslmode_require(url: str) -> str:
    """
    Supabase / Vercel: conexiunea Postgres cere TLS.
    Dacă lipsește sslmode din query, adaugă sslmode=require (nu altera URL-uri locale).
    """
    if not url:
        return url
    low = url.lower()
    if not (low.startswith("postgresql://") or low.startswith("postgres://")):
        return url
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1"):
            return url
        q = parse_qsl(parsed.query, keep_blank_values=True)
        if any(k.lower() == "sslmode" for k, _ in q):
            return url
        q = list(q) + [("sslmode", "require")]
        new_query = urlencode(q)
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )
    except Exception:
        if "sslmode=" in url.lower():
            return url
        sep = "&" if "?" in url else "?"
        return url + sep + "sslmode=require"


def normalize_database_url(url: Optional[str] = None) -> str:
    u = (url or os.getenv("DATABASE_URL") or "").strip()
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]
    u = _ensure_postgres_sslmode_require(u)
    return u


def apply_database_url_to_environ() -> None:
    """Apelat la boot (ex. api/main pe Vercel): repară postgres:// și sslmode în os.environ."""
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return
    os.environ["DATABASE_URL"] = normalize_database_url(raw)


class _PGCursorShim:
    __slots__ = ("_cur",)

    def __init__(self, cur: Any) -> None:
        self._cur = cur

    def __iter__(self) -> Any:
        return iter(self._cur)

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> Any:
        return self._cur.fetchall()


class PGConnection:
    """Conexiune psycopg2 cu API apropiat de sqlite3.Connection pentru interogări simple."""

    __slots__ = ("_conn",)

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, sql: str, params: Union[Sequence[Any], Tuple] = ()) -> _PGCursorShim:
        from psycopg2.extras import RealDictCursor

        sql_pg, args = adapt_sqlite_sql_to_postgres(sql, params)
        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql_pg, args)
        return _PGCursorShim(cur)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def connect_pg() -> PGConnection:
    """Conexiune DBAPI prin SQLAlchemy (pool NullPool — potrivit serverless)."""
    global _engine
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    url = normalize_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL lipsește pentru PostgreSQL.")
    if _engine is None:
        _engine = create_engine(url, poolclass=NullPool, future=True)
    return PGConnection(_engine.raw_connection())


def adapt_sqlite_sql_to_postgres(sql: str, params: Union[Sequence[Any], Tuple]) -> Tuple[str, Tuple]:
    """Traduce placeholder-e ? în %s și câteva funcții SQLite uzuale."""
    s = (sql or "").strip()
    if not s:
        return s, tuple(params) if params is not None else ()

    args = tuple(params) if params is not None else ()
    n_q = s.count("?")
    if n_q != len(args):
        raise ValueError(
            f"Placeholder count mismatch: {n_q} ? vs {len(args)} params in SQL snippet: {s[:120]!r}"
        )

    s = s.replace("?", "%s")

    # ORDER BY datetime(col) — SQLite; în PG created_at e TEXT ISO → sortare lexicografică e OK
    s = re.sub(r"\bdatetime\s*\(\s*([a-zA-Z0-9_.]+)\s*\)", r"\1", s, flags=re.I)

    # INSERT OR IGNORE (caz folosit: exo_scheduler_state)
    if re.match(r"^INSERT\s+OR\s+IGNORE\s+", s, re.I):
        s = re.sub(r"^INSERT\s+OR\s+IGNORE\s+", "INSERT ", s, count=1, flags=re.I)
        s = s.rstrip().rstrip(";") + " ON CONFLICT (id) DO NOTHING"

    # INSERT OR REPLACE INTO exo_health_checks
    if re.search(r"INSERT\s+OR\s+REPLACE\s+INTO\s+exo_health_checks", s, re.I):
        s = re.sub(r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", s, count=1, flags=re.I)
        s = (
            s.rstrip().rstrip(";")
            + " ON CONFLICT (vin) DO UPDATE SET checked_at = EXCLUDED.checked_at, ok = EXCLUDED.ok"
        )

    return s, args


def run_ddl_pg(conn: PGConnection, statements: List[str]) -> None:
    raw = conn._conn
    cur = raw.cursor()
    try:
        for stmt in statements:
            st = (stmt or "").strip()
            if not st:
                continue
            cur.execute(st)
        raw.commit()
    finally:
        cur.close()
