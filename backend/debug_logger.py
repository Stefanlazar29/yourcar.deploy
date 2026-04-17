"""
debug_logger.py — Telemetrie erori din frontend (401, etc.)
Endpoint: POST /log-error — primește erori din JS, salvează în errors.log
"""

import os
from datetime import datetime
from typing import Optional

ERRORS_LOG = os.path.join(os.path.dirname(__file__), "errors.log")


def log_error(
    message: str,
    status: Optional[int] = None,
    url: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    ts = datetime.utcnow().isoformat(timespec="seconds")
    line = f"[{ts}] status={status} url={url} msg={message}"
    if detail:
        line += f" detail={detail}"
    line += "\n"
    try:
        with open(ERRORS_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"[debug_logger] Nu s-a putut scrie în errors.log: {e}")


def read_recent_errors(limit: int = 50) -> list[str]:
    """Citește ultimele N linii din errors.log."""
    if not os.path.exists(ERRORS_LOG):
        return []
    try:
        with open(ERRORS_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-limit:] if lines else []
    except Exception:
        return []
