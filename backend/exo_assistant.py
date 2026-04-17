"""
MulberryEXO Assistant — răspunsuri prin AIProxy (Groq / fallback Ollama) cu context vehicul + piață + insights + carburant.

Model Groq: setează GROQ_MODEL_FAST (implicit llama-3.1-8b-instant în ai_proxy). Mock UI: MULBERRY_EXO_MOCK=1.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend import database
from backend import rag_qdata
from backend import valuation_engine
from backend import ai_proxy


def _fuel_map() -> Dict[str, str]:
    try:
        from backend.exo_research_engine import get_latest_fuel_prices

        raw = get_latest_fuel_prices()
    except Exception:
        raw = {}
    benz = raw.get("benzina") or raw.get("benzine") or "—"
    mot = raw.get("motorina") or raw.get("motorină") or "—"
    return {"benzina": str(benz), "motorina": str(mot)}


def _year_int(year: Any) -> Optional[int]:
    if year is None:
        return None
    try:
        return int(str(year).strip()[:4])
    except (TypeError, ValueError):
        return None


def _matches_skoda_fabia_6y(make: Any, model: Any, series: Any, year: Any) -> bool:
    """Prima generație Fabia (6Y / Mk1) sau an în interval tipic."""
    mk = (str(make or "").lower().replace("š", "s"))
    if "skoda" not in mk:
        return False
    md = (str(model or "").lower())
    if "fabia" not in md:
        return False
    sr = (str(series or "").lower().replace("š", "s"))
    if any(x in sr or x in md for x in ("6y", "mk1", "typ 6y")):
        return True
    y = _year_int(year)
    if y is not None and 1999 <= y <= 2007:
        return True
    return False


def _fabia_6y_market_intel_block(car: Any, brain: Any) -> str:
    make = getattr(car, "make", None) or (getattr(brain, "marca", None) if brain else None)
    model = getattr(car, "model", None) or (getattr(brain, "model", None) if brain else None)
    series = getattr(car, "series", None) or (getattr(brain, "series", None) if brain else None)
    year = getattr(car, "year", None) or (getattr(brain, "an", None) if brain else None)
    if not _matches_skoda_fabia_6y(make, model, series, year):
        return ""
    row = database.market_intel_get_synthesis(database.MODEL_KEY_SKODA_FABIA_6Y)
    if not row:
        return ""
    syn = (row.get("synthesis_ro") or "").strip()
    if not syn:
        return ""
    updated = row.get("updated_at") or "—"
    nsrc = row.get("sources_count") or 0
    return (
        f"CONTEXT MODEL PIAȚĂ — Škoda Fabia (gen. 6Y / Mk1, enciclopedic + sinteză AI):\n"
        f"{syn}\n"
        f"(Surse în server: {nsrc} fragmente Wikipedia; refresh sinteză: {updated}) "
        f"Indicativ pentru evaluare, nu înlocuiește date live Autovit."
    )


def _insights_block(vin: str, limit: int = 5) -> str:
    rows = database.get_exo_insights(vin.strip().upper(), limit=limit)
    if not rows:
        return "Nu există insights recente în baza Mulberry."
    lines = []
    for r in rows:
        t = (r.get("insight_text") or "").strip()
        if t:
            lines.append(f"• {t}")
    return "\n".join(lines) if lines else "Nu există insights recente."


def _multifactor_softscore_block(user_id: int, vin: str) -> str:
    """Ultimul SoftScore v1 din vehicle_insights — pentru explicații tip streamExoReply în conversație."""
    row = database.vehicle_insight_latest_for_question(
        user_id,
        vin.strip().upper(),
        valuation_engine.SOFTSCORE_INSIGHT_QUESTION_V1,
    )
    if not row:
        return ""
    reply = (row.get("reply") or "").strip()
    if reply:
        return f"SOFTSCORE MULTI-FACTOR (ultima evaluare salvată în Mulberry):\n{reply}"
    try:
        payload = json.loads(row.get("analysis_json") or "{}")
    except json.JSONDecodeError:
        payload = {}
    ss = payload.get("softscore")
    mv = payload.get("market_value")
    if ss is None:
        return ""
    cur = payload.get("currency") or "EUR"
    tail = f" Valoare estimativă ~{mv} {cur}." if mv is not None else ""
    return f"SOFTSCORE MULTI-FACTOR: {ss}/100.{tail}"


def _valuation_lines(car: Any, brain: Any) -> str:
    """Snapshot evaluare (Autovit + SoftScore real) — best-effort, poate eșua rapid."""
    try:
        snap = valuation_engine.snapshot_for_vehicle(car, brain)
    except Exception as e:
        return f"Evaluare piață live indisponibilă momentan ({e})."
    m = snap.get("market") or {}
    s = snap.get("soft_score_real") or {}
    lines = [
        f"SoftScore (model extins): {s.get('soft_score', '—')}% — {s.get('status_health', '')}",
    ]
    if m.get("error"):
        lines.append(f"Piață Autovit: {m.get('error')}")
    elif m.get("count"):
        lines.append(
            f"Piață Autovit (indicativ): ~{m.get('avg')} (median {m.get('median')}, n={m.get('count')}) — sursă {m.get('source')}"
        )
    br = s.get("breakdown") or {}
    if br:
        lines.append("Detalii scor: " + ", ".join(f"{k}={v}" for k, v in br.items()))
    return "\n".join(lines)


def build_exo_system_prompt(
    vin: str,
    car: Any,
    brain: Any,
    *,
    user_id: Optional[int] = None,
) -> str:
    make = getattr(car, "make", None) or (getattr(brain, "marca", None) if brain else None) or "—"
    model = getattr(car, "model", None) or (getattr(brain, "model", None) if brain else None) or "—"
    series = getattr(car, "series", None) or (getattr(brain, "series", None) if brain else None) or "—"
    year = getattr(car, "year", None) or (getattr(brain, "an", None) if brain else None) or "—"
    km = getattr(car, "km_actuali", None) or 0
    fuel = _fuel_map()

    soft = float(getattr(brain, "soft_score", 0) or 0) if brain else 0.0
    status = (getattr(brain, "status_health", None) or "—") if brain else "—"

    docs_ok = 0
    docs_tot = 0
    if brain and getattr(brain, "cloud_files", None):
        docs_tot = len(brain.cloud_files)
        docs_ok = sum(1 for d in brain.cloud_files if getattr(d, "verified", False))

    val_txt = _valuation_lines(car, brain) if car else "Fără profil mașină în DB."
    intel_fabia = _fabia_6y_market_intel_block(car, brain)
    intel_section = f"\n{intel_fabia}\n" if intel_fabia else ""
    multifactor_txt = ""
    if user_id is not None and vin:
        multifactor_txt = _multifactor_softscore_block(user_id, vin)
    multifactor_section = f"\n{multifactor_txt}\n" if multifactor_txt else ""

    return f"""Ești MulberryEXO — analist auto tehnic (RO). Mod strict analitic.

VEHICUL:
- {make} {model} {series}, an {year}, {km} km
- VIN: {vin}

BRAIN MULBERRY (sync / istoric):
- SoftScore (brain): {soft:.1f}%
- Status: {status}
- Documente verificate: {docs_ok}/{docs_tot}

EVALUARE & PIAȚĂ (încercare live — indicativ, nu ofertă):
{val_txt}
{intel_section}{multifactor_section}
INSIGHTS EXO (ultimele înregistrări):
{_insights_block(vin)}

PREȚURI CARBURANT (research local):
- Benzină: {fuel['benzina']} RON/L
- Motorină: {fuel['motorina']} RON/L

REGULI (obligatoriu):
- Română. Fără politețe inutilă: zero saluturi, zero „desigur/cu drag”, zero închideri floroase.
- Răspuns direct, structurat (secțiuni scurte, bullet-uri). Ton inginer, nu call center.
- Valori financiare: marchează „estimativ” și sursa din context dacă există.
- Urgențe ITP/RCA (<30 zile sau expirate dacă apar în context) — primele în răspuns.
- Nu inventa: date lipsă → „nu e în context Mulberry” + ce ar verifica utilizatorul la sursă.

Data: {datetime.now().strftime("%d.%m.%Y")}"""


def ask_exo(
    user_id: int,
    vin: str,
    message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Construiește system prompt complet + apelează LLM cu istoric (user/assistant).
    conversation_history: [{ "role": "user"|"assistant", "content": "..." }, ...]
    """
    vin_norm = (vin or "").strip().upper()
    if not vin_norm:
        return {
            "reply": "Adaugă VIN-ul vehiculului în profil pentru răspunsuri personalizate MulberryEXO.",
            "soft_score": None,
            "context": {},
        }

    car = database.get_car_by_vin(vin_norm)
    brain = database.get_vehicle_brain(vin_norm)

    if not car and not brain:
        return {
            "reply": "Nu găsesc vehiculul acestui VIN în Mulberry. Rulează sincronizarea din aplicație.",
            "soft_score": None,
            "context": {},
        }

    if not car and brain:
        # construim un obiect minimal din brain
        class _Mini:
            pass

        c = _Mini()
        c.make = getattr(brain, "marca", "")
        c.model = getattr(brain, "model", "")
        c.year = getattr(brain, "an", None)
        c.km_actuali = 0
        c.vin = vin_norm
        c.rca_expiry = None
        c.itp_expiry = None
        c.series = getattr(brain, "series", "")
        car = c

    msg_c = (message or "").strip()

    system = build_exo_system_prompt(vin_norm, car, brain, user_id=user_id)
    rag_prefix = ""
    try:
        rag_prefix = rag_qdata.build_memory_injection_block(vin_norm, msg_c)
    except Exception as rag_err:
        # ChromaDB lipsă / colecție goală / filtru invalid — nu blocăm Groq
        print(f"[exo_assistant] RAG memory injection skip: {rag_err!r}")
    if rag_prefix:
        system = rag_prefix + "\n\n---\n\n" + system

    history = conversation_history or []
    # normalize keys
    norm_hist: List[Dict[str, str]] = []
    for h in history[-12:]:
        role = (h.get("role") or "user").lower()
        if role not in ("user", "assistant"):
            role = "user"
        content = (h.get("content") or h.get("text") or "").strip()
        if content:
            norm_hist.append({"role": role, "content": content})

    messages: List[Dict[str, str]] = []
    for h in norm_hist:
        messages.append({"role": h["role"], "content": h["content"]})
    # Evită duplicat dacă frontend include deja ultimul user turn
    if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != msg_c:
        messages.append({"role": "user", "content": msg_c})

    reply = ai_proxy.complete_with_history(
        system,
        messages,
        task="fast_chat",
        max_completion_tokens=1500,
        temperature=0.4,
    )

    soft_out = float(brain.soft_score) if brain else None
    llm_backend = ai_proxy.get_last_chat_backend()
    return {
        "reply": reply,
        "soft_score": soft_out,
        "llm_backend": llm_backend,
        "context": {
            "make": getattr(car, "make", None),
            "model": getattr(car, "model", None),
            "year": getattr(car, "year", None),
        },
    }
