"""
MLBR Digital File — document de identitate vehicul, semnat HMAC-SHA256 (imuabil).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

MLBR_SECRET = (os.getenv("MLBR_SECRET") or "schimba-cu-secret-puternic-in-productie").strip()
MLBR_PUBLIC_BASE = (os.getenv("MLBR_PUBLIC_BASE") or "https://id.mulberry.ro").rstrip("/")


def normalize_mlbr_id(raw: Optional[str]) -> str:
  """Format canonic pentru URL și DB: MLBR-XXXX-XXXX (fără spații duble)."""
  if not raw:
    return ""
  s = str(raw).strip().upper()
  s = re.sub(r"\s+", "-", s)
  s = re.sub(r"-+", "-", s)
  return s


def new_mlbr_id() -> str:
  """ID unic stil MLBR-AB12-CD34."""
  a = secrets.token_hex(2).upper()
  b = secrets.token_hex(2).upper()
  return f"MLBR-{a}-{b}"


def _public_verify_url(mlbr_id: str, vin: Optional[str] = None) -> str:
  """Link canonic scan QR: {MLBR_PUBLIC_BASE}/v/{MLBR-ID} (pagină publică, fără login)."""
  _ = vin  # compat API; calea publică folosește doar ID-ul unității
  mid = quote(normalize_mlbr_id(mlbr_id), safe="")
  return f"{MLBR_PUBLIC_BASE.rstrip('/')}/v/{mid}"


def generate_mlbr_file(
  car: Dict[str, Any],
  user: Dict[str, Any],
  *,
  mlbr_id_override: Optional[str] = None,
) -> Dict[str, Any]:
  """
  Construiește payload-ul semnat. `mlbr_id_override` dacă există deja (ex. ycr_id).
  """
  mlbr_id = normalize_mlbr_id(mlbr_id_override) or new_mlbr_id()
  uid = (user.get("identifier") or user.get("email") or user.get("id") or "unknown")
  payload: Dict[str, Any] = {
    "mlbr_id": mlbr_id,
    "vin": (car.get("vin") or "").strip().upper(),
    "plate": (car.get("plate") or "").strip(),
    "make": (car.get("make") or "").strip(),
    "model": (car.get("model") or "").strip(),
    "series": (car.get("series") or "").strip(),
    "year": car.get("year"),
    "fuel": (car.get("fuel") or "").strip(),
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "generated_by": str(uid),
    "version": "1.0",
    "verify_url": _public_verify_url(mlbr_id, car.get("vin")),
  }

  canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
  signature = hmac.new(
    MLBR_SECRET.encode("utf-8"),
    canonical.encode("utf-8"),
    hashlib.sha256,
  ).hexdigest()
  out = dict(payload)
  out["signature"] = signature
  return out


def verify_mlbr_file(file_data: Dict[str, Any]) -> bool:
  """Verifică HMAC pe payload fără a modifica dict-ul sursă."""
  data = {k: v for k, v in file_data.items()}
  sig = data.pop("signature", None)
  if not sig:
    return False
  canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
  expected = hmac.new(
    MLBR_SECRET.encode("utf-8"),
    canonical.encode("utf-8"),
    hashlib.sha256,
  ).hexdigest()
  return hmac.compare_digest(sig, expected)


def public_safe_payload(file_data: Dict[str, Any]) -> Dict[str, Any]:
  """Date pentru API public (fără date sensibile excesive)."""
  fd = dict(file_data)
  fd.pop("signature", None)
  gb = fd.pop("generated_by", None)
  if gb and "@" in str(gb):
    pre = str(gb).split("@")[0]
    fd["generated_by_masked"] = pre[:2] + "***@" + str(gb).split("@", 1)[-1]
  else:
    fd["generated_by_masked"] = "***"
  return fd
