"""
Mulberry Cloud — căi pe user+VIN, pipeline post-upload (BackgroundTasks) + legături SoftScore.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple

from backend import database
from backend.models import CloudFile, MulberryBrain

# Documente mașină vs istoric vs rapoarte (grid UI + subfoldere)
DOC_CATEGORY: Dict[str, str] = {
    "ITP": "vehicle_docs",
    "RCA": "vehicle_docs",
    "Talon": "vehicle_docs",
    "Service": "service_history",
    "RaportAI": "ai_reports",
    "Fotografie": "photos",
    "Altele": "misc",
}

ALLOWED_CLOUD_TYPES = tuple(DOC_CATEGORY.keys())

SAFE_NAME_RE = re.compile(r"[^\w\-.]", re.UNICODE)


def normalize_doc_type(doc_type: str) -> str:
    t = (doc_type or "").strip()
    if t not in ALLOWED_CLOUD_TYPES:
        return "Altele"
    return t


def category_for_type(doc_type: str) -> str:
    return DOC_CATEGORY.get(normalize_doc_type(doc_type), "misc")


def safe_upload_basename(name: str) -> str:
    s = SAFE_NAME_RE.sub("_", (name or "").strip())[:80]
    return s or "doc"


def storage_prefix(user_id: int, vin_clean: str, doc_type: str) -> str:
    cat = category_for_type(doc_type)
    return f"u{int(user_id)}/{vin_clean}/{cat}"


def abs_upload_path(upload_root: str, user_id: int, vin_clean: str, doc_type: str, stored_file: str) -> str:
    cat = category_for_type(doc_type)
    return os.path.join(upload_root, f"u{int(user_id)}", vin_clean, cat, stored_file)


def public_file_url(user_id: int, vin_clean: str, doc_type: str, stored_file: str) -> str:
    cat = category_for_type(doc_type)
    return f"/cloud/file/u{int(user_id)}/{vin_clean}/{cat}/{stored_file}"


def _read_pdf_text(path: str, max_chars: int = 12000) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            return ""
    try:
        reader = PdfReader(path)
        chunks: list[str] = []
        for page in reader.pages[:8]:
            t = page.extract_text() or ""
            if t:
                chunks.append(t)
            if sum(len(x) for x in chunks) >= max_chars:
                break
        text = "\n".join(chunks)[:max_chars]
        return text
    except Exception:
        return ""


def _normalize_expiry_date(raw: Optional[str]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{2})[./](\d{2})[./](\d{4})$", s)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{mo}-{d}"
    return None


def _groq_extract_expiry(text: str, kind: str) -> Optional[str]:
    """Extrage o singură dată de expirare ISO din textul documentului (PDF)."""
    snippet = (text or "")[:6000]
    if len(snippet) < 20:
        return None
    try:
        from backend import ai_proxy
    except Exception:
        return None
    system = (
        "Ești extractor de date pentru documente auto RO. Răspunde DOAR cu JSON: "
        '{"expiry":"YYYY-MM-DD"} sau {"expiry":null}. '
        f"Extrage data de EXPIRARE / valabilitate finală pentru documentul de tip {kind}. "
        "Dacă sunt mai multe date, alege expirarea poliței/atestatului (nu data emiterii)."
    )
    try:
        reply = ai_proxy.complete_chat(
            system,
            [{"role": "user", "content": snippet}],
            task="json_structured",
            max_completion_tokens=120,
        )
        m = re.search(r"\{[^}]+\}", reply, re.S)
        raw = m.group(0) if m else reply
        data = json.loads(raw)
        return _normalize_expiry_date(data.get("expiry"))
    except Exception:
        return None


def _maybe_service_market_overlay_stub(user_id: int, vin: str, text: str, path: str) -> None:
    """
    B2B (viitor): facturi service → bonus pret_mediu_eur / overlay market_intel per flotă.
    Punct de extensie Groq: detectare „distribuție”, „-kit”, „ambreiaj” etc.
    """
    _ = (user_id, vin, text, path)
    # Intenționat neimplimentat — evităm scrieri în market_intel fără contract date.


def run_post_upload_pipeline(
    user_id: int,
    vin: str,
    doc_type: str,
    abs_path: str,
    *,
    original_name: str,
) -> None:
    """Rulează după răspunsul HTTP: extragere date document + mașină + SoftScore insight."""
    vin_norm = (vin or "").strip().upper()
    dtype = normalize_doc_type(doc_type)
    ext = os.path.splitext(abs_path)[1].lower()

    text = ""
    if ext == ".pdf":
        text = _read_pdf_text(abs_path)

    if dtype in ("RCA", "ITP") and text:
        exp = _groq_extract_expiry(text, dtype)
        if exp:
            if dtype == "RCA":
                database.patch_car_expiry_dates(user_id, vin_norm, rca_expiry=exp)
            else:
                database.patch_car_expiry_dates(user_id, vin_norm, itp_expiry=exp)

    if dtype == "Service" and text:
        _maybe_service_market_overlay_stub(user_id, vin_norm, text, abs_path)

    try:
        from backend import softscore_insight

        softscore_insight.persist_multifactor_insight_for_vehicle(user_id, vin_norm)
    except Exception:
        pass


def persist_cloud_upload_v2(
    *,
    upload_root: str,
    user_id: int,
    vin: str,
    doc_type: str,
    file_body: bytes,
    original_filename: str,
) -> Tuple[dict, str]:
    """
    Scrie fișierul sub uploads/u{user_id}/{vin}/{categorie}/ și actualizează MulberryBrain.
    Returnează (json_response_dict, absolute_path_for_background).
    """
    dtype = normalize_doc_type(doc_type)
    vin_clean = re.sub(r"[^\w]", "", vin)[:20] or "default"
    if len((vin or "").strip()) < 10:
        raise ValueError("VIN invalid.")

    car = database.get_car_by_user_and_vin(user_id, (vin or "").strip().upper())
    if not car:
        raise PermissionError("VIN nu aparține utilizatorului curent.")

    ext = os.path.splitext(original_filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".pdf"):
        raise ValueError("Tip fișier invalid.")

    unique = uuid.uuid4().hex[:10]
    safe = safe_upload_basename(os.path.basename(original_filename or "doc"))
    stored = f"{unique}_{safe}"
    if not stored.lower().endswith(ext):
        stored += ext

    dest_dir = os.path.dirname(abs_upload_path(upload_root, user_id, vin_clean, dtype, stored))
    os.makedirs(dest_dir, exist_ok=True)
    abs_path = abs_upload_path(upload_root, user_id, vin_clean, dtype, stored)

    with open(abs_path, "wb") as f:
        f.write(file_body)

    brain = database.get_vehicle_brain(vin.strip().upper())
    if not brain:
        brain = MulberryBrain(
            vin=vin.strip().upper(),
            owner_email="unknown@mulberry.local",
            mlbr_code=f"MLBR-{vin_clean[-4:]}-{vin_clean[:4]}",
        )
    rel_key = f"{category_for_type(dtype)}/{stored}"
    next_id = max([d.id for d in brain.cloud_files], default=0) + 1
    brain.cloud_files.append(
        CloudFile(
            id=next_id,
            type=dtype,
            filename=rel_key,
            verified=False,
            uploaded_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
    )
    from backend.engine import sync_vehicle_brain

    brain = sync_vehicle_brain(brain)
    database.update_vehicle_brain(vin.strip().upper(), brain)

    out = {
        "id": next_id,
        "type": dtype,
        "filename": rel_key,
        "category": category_for_type(dtype),
        "verified": False,
        "url": public_file_url(user_id, vin_clean, dtype, stored),
        "pending_processing": True,
    }
    return out, abs_path
