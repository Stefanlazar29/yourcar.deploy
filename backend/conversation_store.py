"""
Memorie conversații pe termen lung: JSON per proiect, cheiat după user id / email.
Fișier: data/conversations.json (lângă rădăcina proiectului).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONV_PATH = DATA_DIR / "conversations.json"

_lock = Lock()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_turn(
    user_key: str,
    user_message: str,
    assistant_reply: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Adaugă o tură user + assistant în istoricul utilizatorului."""
    key = (user_key or "guest").strip() or "guest"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with _lock:
        data: Dict[str, List[Dict[str, Any]]] = {}
        if CONV_PATH.is_file():
            try:
                data = json.loads(CONV_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        thread = data.get(key)
        if not isinstance(thread, list):
            thread = []
        entry_user = {"ts": _utc_iso(), "role": "user", "text": user_message}
        entry_asst = {
            "ts": _utc_iso(),
            "role": "assistant",
            "text": assistant_reply,
            "meta": meta or {},
        }
        thread.append(entry_user)
        thread.append(entry_asst)
        # limitează la ultimele 500 mesaje per user (250 perechi)
        if len(thread) > 500:
            thread = thread[-500:]
        data[key] = thread
        CONV_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
