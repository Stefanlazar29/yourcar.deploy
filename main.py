#!/usr/bin/env python3
"""
Mulberry API — punct de intrare Railway / Nixpacks.

IMPORTANT: Aplicația FastAPI este în backend/main.py → modul Uvicorn: backend.main:app
(Nu folosi „main:app” — nu există app în acest fișier.)

Railway setează PORT; serverul trebuie să asculte EXACT pe acel port (altfel 502/404 în browser).
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))


def setup_railway_environment() -> int:
    """Pregătește căi date + returnează portul numeric pentru Uvicorn."""
    raw_port = os.environ.get("PORT", "9000")
    try:
        port = int(str(raw_port).strip())
    except ValueError:
        port = 9000
    if port < 1 or port > 65535:
        port = 9000

    data_dir = "/data" if os.path.exists("/data") else str(ROOT_DIR / "data")
    os.makedirs(data_dir, exist_ok=True)

    for subdir in ("uploads", "chroma_db"):
        os.makedirs(os.path.join(data_dir, subdir), exist_ok=True)

    os.environ.setdefault("SQLITE_PATH", os.path.join(data_dir, "mulberry.db"))
    os.environ.setdefault("AUTH_AUDIT_PATH", os.path.join(data_dir, "auth_audit.db"))
    os.environ.setdefault("CHROMA_PERSIST_PATH", os.path.join(data_dir, "chroma_db"))
    os.environ.setdefault("MULBERRY_UPLOAD_DIR", os.path.join(data_dir, "uploads"))

    return port


if __name__ == "__main__":
    port = setup_railway_environment()

    print(f"[Mulberry] PORT={port} (din $PORT pe Railway, fallback 9000 local)")
    print(f"[Mulberry] SQLITE_PATH={os.environ.get('SQLITE_PATH', 'N/A')}")
    print("[Mulberry] Pornesc Uvicorn: backend.main:app pe 0.0.0.0")

    try:
        import uvicorn

        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            access_log=True,
        )
    except ImportError:
        print("ERROR: uvicorn lipsește. Rulează: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR la pornire: {e}")
        sys.exit(1)
