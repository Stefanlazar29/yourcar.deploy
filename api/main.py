"""
Entry Vercel (Serverless) — FastAPI din backend.main.

Înainte de orice import backend: normalizează DATABASE_URL (postgres:// → postgresql://,
sslmode=require pentru hosturi non-locale) și dezactivează APScheduler (serverless).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from backend.pg_adapter import apply_database_url_to_environ  # noqa: E402

apply_database_url_to_environ()
os.environ.setdefault("SKIP_AP_SCHEDULER", "1")
# Fișier temporar RAG local — pe Vercel folosește /tmp (ephemeral)
os.environ.setdefault("CHROMA_PERSIST_PATH", "/tmp/mulberry_chroma")

from backend.main import app # noqa: E402

__all__ = ["app"]
