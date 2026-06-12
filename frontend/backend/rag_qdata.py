"""
RAG QData — profil vehicul din SQLite + brain → embeddings ChromaDB + injecție în prompt EXO.

Colecție: mulberry_vehicle_memory (metadata: vin, user_id, source, confidence).
Feedback loop (scor încredere): pregătit pentru viitor — vezi boost_confidence_placeholder().
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from backend import database
from backend import vector_store


def _norm_vin(v: str) -> str:
    return (v or "").strip().upper()


def build_qdata_text_from_car(car: database.CarRow, brain: Optional[Any] = None) -> str:
    """
    Text canonic pentru embedding: descriere lizibilă a vehiculului (QData / fișă Mulberry).
    """
    lines: List[str] = []
    vin = _norm_vin(car.vin or "")
    lines.append(f"Vehicul Mulberry — VIN {vin}.")
    lines.append(
        f"Marcă și model: {car.make or '—'} {car.model or ''}. Serie/generație: {car.series or '—'}."
    )
    lines.append(f"An fabricație: {car.year or '—'}. Combustibil declarat: {car.fuel or '—'}.")
    lines.append(f"Număr înmatriculare: {car.plate or '—'}.")
    km = car.km_actuali
    lines.append(f"Kilometraj înregistrat: {km if km is not None else '—'} km.")
    lines.append(f"RCA expiră: {car.rca_expiry or '—'}. ITP expiră: {car.itp_expiry or '—'}.")
    if car.ycs_score is not None:
        lines.append(f"YCS / scor intern card: {car.ycs_score}.")
    if car.mlbr_code:
        lines.append(f"Cod MLBR asociat: {car.mlbr_code}.")
    if brain is not None:
        try:
            ss = float(getattr(brain, "soft_score", 0) or 0)
            st = getattr(brain, "status_health", None) or "—"
            lines.append(f"Mulberry Brain — SoftScore: {ss:.1f}%. Stare: {st}.")
            cfs = getattr(brain, "cloud_files", None) or []
            if cfs:
                n = len(cfs)
                nv = sum(1 for d in cfs if getattr(d, "verified", False))
                lines.append(f"Documente Cloud: {nv}/{n} verificate în dosar.")
            rem = getattr(brain, "reminders", None) or []
            if rem:
                lines.append(f"Reminder-uri active în brain: {len(rem)}.")
        except Exception:
            pass
    lines.append(
        f"Actualizare profil QData (SQLite): {car.updated_at or datetime.now(timezone.utc).isoformat()}."
    )
    return "\n".join(lines).strip()


def build_qdata_text_brain_only(brain: Any) -> str:
    """Dacă lipsește rândul `cars`, folosim doar brain-ul JSON."""
    vin = _norm_vin(getattr(brain, "vin", "") or "")
    lines = [
        f"Vehicul Mulberry — VIN {vin} (doar date brain, fără rând complet în cars).",
        f"Marcă/model: {getattr(brain, 'marca', '—')} {getattr(brain, 'model', '')}. "
        f"An: {getattr(brain, 'an', '—')}. Serie: {getattr(brain, 'series', '—')}.",
        f"SoftScore brain: {getattr(brain, 'soft_score', 0)}. Status: {getattr(brain, 'status_health', '—')}.",
    ]
    return "\n".join(lines).strip()


def upsert_vehicle_qdata_embedding(vin: str) -> tuple[bool, str]:
    """
    Construiește textul QData și îl salvează/actualizează în Chroma (upsert).
    Returnează (ok, mesaj).
    """
    vin_n = _norm_vin(vin)
    if len(vin_n) != 17:
        return False, "VIN invalid (trebuie 17 caractere)."

    car = database.get_car_by_vin(vin_n)
    brain = database.get_vehicle_brain(vin_n)

    if car:
        text = build_qdata_text_from_car(car, brain)
        uid = car.user_id
    elif brain:
        text = build_qdata_text_brain_only(brain)
        uid = None
    else:
        return False, f"Nu există vehicul sau brain pentru VIN {vin_n}."

    ok = vector_store.upsert_vehicle_qdata(
        vin_n,
        text,
        user_id=uid,
        confidence=1.0,
        source="qdata_sqlite",
    )
    if not ok:
        return False, "ChromaDB indisponibil sau eroare la upsert (vezi log)."
    return True, f"Embedding salvat pentru {vin_n} ({len(text)} caractere)."


def query_vehicle_memory_for_message(vin: str, user_message: str, n_results: int = 4) -> List[dict]:
    """Fragmente relevante din memoria vehiculului pentru mesajul curent (căutare semantică)."""
    return vector_store.query_vehicle_memory(_norm_vin(vin), user_message, n_results=n_results)


# Limite pentru injecție în prompt (evită „Wikipedia” la fiecare „hello”)
_RAG_INJECT_MAX_TOTAL = 1400
_RAG_CHROMA_MAX_SNIPPET = 320
_RAG_CHROMA_N_RESULTS = 1


def _expiry_compact(label: str, raw: Optional[str]) -> str:
    """O linie scurtă: dată + EXPIRAT sau zile rămase."""
    s = (raw or "").strip()
    if not s:
        return f"{label}: necunoscut"
    head = s[:10]
    try:
        d = date.fromisoformat(head)
        today = date.today()
        if d < today:
            return f"{label}: EXPIRAT (era {head})"
        delta = (d - today).days
        return f"{label}: {head} (~{delta} zile)"
    except ValueError:
        return f"{label}: {s[:24]}"


def _inject_chroma_enabled() -> bool:
    return os.getenv("MULBERRY_RAG_INJECT_CHROMA", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def build_memory_injection_block(vin: str, user_message: str) -> str:
    """
    Capsulă scurtă pentru system prompt: km, SoftScore, RCA/ITP (expirat/zile).
    Opțional un singur fragment Chroma trunchiat (MULBERRY_RAG_INJECT_CHROMA=0 îl dezactivează).
    Nu trimite blocuri lungi de embedding la fiecare mesaj.
    """
    vin = _norm_vin(vin)
    if not vin or not (user_message or "").strip():
        return ""

    car = database.get_car_by_vin(vin)
    brain = database.get_vehicle_brain(vin)
    if not car and not brain:
        return ""

    lines: List[str] = [
        "MEMORIE COMPACTĂ (RAG Mulberry — doar reper; nu extinde artificial):",
    ]
    if car:
        km = car.km_actuali
        lines.append(f"- Kilometraj: {km if km is not None else '—'} km.")
        lines.append(f"- {_expiry_compact('RCA', car.rca_expiry)}; {_expiry_compact('ITP', car.itp_expiry)}.")
        if car.ycs_score is not None:
            lines.append(f"- YCS/scor card: {car.ycs_score}.")
    if brain:
        try:
            ss = float(getattr(brain, "soft_score", 0) or 0)
            st = getattr(brain, "status_health", None) or "—"
            lines.append(f"- SoftScore brain: {ss:.1f}% (stare: {st}).")
            cfs = getattr(brain, "cloud_files", None) or []
            if cfs:
                n = len(cfs)
                nv = sum(1 for d in cfs if getattr(d, "verified", False))
                lines.append(f"- Documente Cloud: {nv}/{n} verificate.")
        except Exception:
            pass

    if _inject_chroma_enabled():
        try:
            hits = query_vehicle_memory_for_message(
                vin, user_message, n_results=_RAG_CHROMA_N_RESULTS
            )
            if hits:
                t = (hits[0].get("text") or "").strip()
                if t:
                    t = re.sub(r"\s+", " ", t)[:_RAG_CHROMA_MAX_SNIPPET]
                    lines.append(f"- Fragment vectorial (scurt): {t}")
        except Exception:
            pass

    out = "\n".join(lines).strip()
    if len(out) > _RAG_INJECT_MAX_TOTAL:
        out = out[: _RAG_INJECT_MAX_TOTAL].rstrip() + "…"
    return out


def boost_confidence_placeholder(vin: str, doc_fragment_id: str, delta: float = 0.1) -> None:
    """
    Rezervat pentru bucla de feedback: crește scorul de încredere când utilizatorul confirmă (ex. „mulțumesc, așa e”).
    Implementare: update metadata în Chroma sau tabel auxiliar — viitor.
    """
    # pylint: disable=unused-argument
    return
