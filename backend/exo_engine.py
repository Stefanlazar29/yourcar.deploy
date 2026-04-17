"""
exo_engine.py — EXO Intelligence Engine (AIProxy: Groq / fallback Ollama)
Rulează la fiecare 10 minute prin APScheduler.
Analizează fiecare vehicul din portofoliu și inserează insights în exo_daily_insights.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend import database
from backend import ai_proxy

def _max_vehicles_per_cycle() -> int:
    try:
        n = int(os.getenv("EXO_MAX_VEHICLES_PER_CYCLE", "10"))
    except ValueError:
        n = 10
    return max(1, min(n, 500))

# ── Categorii de insights ──
INSIGHT_TYPES = {
    "recall": "⚠️ RECALL",
    "maintenance": "🔧 MENTENANȚĂ",
    "legal": "📋 LEGISLAȚIE",
    "market": "💰 PIAȚĂ",
    "weather": "🌡️ SEZON",
    "fuel": "⛽ COMBUSTIBIL",
    "technical": "⚙️ TEHNIC",
    "personal": "👤 PERSONALIZAT",
}

EXO_SYSTEM_PROMPT = """
Ești EXO-Observer, un sistem de intelligence auto specializat pe piața românească.
Analizezi vehicule și generezi insights utile, concrete și acționabile.

REGULI STRICTE:
- Răspunzi DOAR în format JSON valid, niciun alt text
- Maximum 5 insights per vehicul
- Fiecare insight: maxim 120 caractere în câmpul "text"
- Insights relevante pentru România (legislație RO, prețuri RON, service RO)
- Prioritizează: urgente > personalizate > generale

FORMAT RĂSPUNS:
{
  "insights": [
    {
      "type": "recall|maintenance|legal|market|weather|fuel|technical|personal",
      "priority": "urgent|high|normal|low",
      "title": "Titlu scurt",
      "text": "Text insight maxim 120 caractere",
      "action": "Ce trebuie să facă userul (opțional)",
      "source": "Sursa informației (opțional)"
    }
  ],
  "health_score_delta": 0,
  "summary": "Rezumat 1 frază"
}
"""


def _days_until(date_str: str) -> Optional[int]:
    if not date_str:
        return None
    try:
        s = str(date_str).replace("Z", "")
        if "T" not in s:
            s = s + "T00:00:00"
        target = datetime.fromisoformat(s)
        now = datetime.utcnow()
        delta = target - now
        return int(delta.total_seconds() / 86400)
    except Exception:
        return None


def _brain_to_context(brain) -> Dict[str, Any]:
    """Convertește MulberryBrain (sau dict) la dict pentru prompt."""
    if brain is None:
        return {}
    if hasattr(brain, "model_dump"):
        return brain.model_dump()
    if isinstance(brain, dict):
        return brain
    return {}


def _build_vehicle_prompt(car: dict, brain_data: dict, user_prefs: dict) -> str:
    make = car.get("make") or ""
    model = car.get("model") or ""
    year = car.get("year") or ""
    fuel = car.get("fuel") or ""
    series = car.get("series") or ""
    plate = car.get("plate") or ""
    try:
        km = int(car.get("km_actuali") or 0)
    except (TypeError, ValueError):
        km = 0

    rca_expiry = car.get("rca_expiry") or ""
    itp_expiry = car.get("itp_expiry") or ""

    soft_score = float(brain_data.get("soft_score") or 0)
    alerts = brain_data.get("alerts") or []
    if not isinstance(alerts, list):
        alerts = []
    cloud_files = brain_data.get("cloud_files") or []
    if not isinstance(cloud_files, list):
        cloud_files = []
    reminders = brain_data.get("reminders") or []
    if not isinstance(reminders, list):
        reminders = []

    usage = user_prefs.get("usage") or "mixed"
    budget = user_prefs.get("budget") or "medium"
    concerns = user_prefs.get("concerns") or []
    if not isinstance(concerns, list):
        concerns = []
    location = user_prefs.get("location") or "Romania"

    now = datetime.utcnow()
    rca_urgent = _days_until(rca_expiry) if rca_expiry else None
    itp_urgent = _days_until(itp_expiry) if itp_expiry else None

    docs_verified = len([f for f in cloud_files if isinstance(f, dict) and f.get("verified")])
    docs_total = len(cloud_files)
    pending_tasks = len([r for r in reminders if isinstance(r, dict) and r.get("status") == "pending"])

    concerns_txt = ", ".join(str(c) for c in concerns) if concerns else "generale"

    prompt = f"""
VEHICUL DE ANALIZAT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATE GENERALE:
  Marcă/Model : {make} {series} {model}
  An fabricație: {year}
  Combustibil : {fuel}
  Nr. înmatr. : {plate}

DATE PERSONALIZATE (introduse de user):
  Kilometraj  : {km:,} km
  Utilizare   : {usage}
  Buget service: {budget}
  Preocupări  : {concerns_txt}
  Locație     : {location}

STARE DOCUMENTE:
  RCA         : {f'expiră în {rca_urgent} zile' if rca_urgent is not None else 'nedefinit'}
  ITP         : {f'expiră în {itp_urgent} zile' if itp_urgent is not None else 'nedefinit'}
  Cloud docs  : {docs_verified}/{docs_total} verificate
  Task-uri    : {pending_tasks} în așteptare

MULBERRY INDEX:
  SoftScore   : {soft_score:.1f}%
  Alerte active: {len(alerts)}

DATA ANALIZĂ: {now.strftime('%d.%m.%Y %H:%M')} UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Generează maximum 5 insights relevante și acționabile pentru
acest vehicul specific, ținând cont de:
1. Problemele cunoscute ale modelului {make} {model} {series} din {year}
2. Urgențele documentelor (RCA/ITP)
3. Preocupările specifice ale userului: {concerns_txt}
4. Sezonul curent și condițiile din România
5. Kilometrajul și uzura estimată la {km:,} km

Răspunde DOAR JSON valid.
"""
    return prompt.strip()


def _parse_minimax_response(raw: str) -> Optional[dict]:
    if not raw:
        return None
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        inner: List[str] = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            inner.append(line)
        clean = "\n".join(inner).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    if m:
        clean = m.group(0)
    try:
        return json.loads(clean)
    except Exception:
        return None


def run_exo_cycle() -> dict:
    """
    Ciclul principal EXO — rulat la fiecare 10 minute (sau manual).
    """
    started_at = datetime.utcnow()
    results: Dict[str, Any] = {
        "vehicles_processed": 0,
        "insights_added": 0,
        "errors": 0,
        "duration_sec": 0.0,
        "ok": True,
    }

    print(f"[EXO] Ciclu pornit la {started_at.strftime('%H:%M:%S')}")

    try:
        cars = database.get_all_cars_with_vin()
    except Exception as e:
        print(f"[EXO] Eroare citire mașini: {e}")
        results["ok"] = False
        results["errors"] += 1
        from datetime import datetime as _dt

        database.update_exo_scheduler_state(
            _dt.utcnow().isoformat(timespec="seconds"),
            0,
            0.0,
            0,
            1,
        )
        return results

    if not cars:
        print("[EXO] Niciun vehicul cu VIN în portofoliu.")
        results["duration_sec"] = (datetime.utcnow() - started_at).total_seconds()
        database.update_exo_scheduler_state(
            datetime.utcnow().isoformat(timespec="seconds"),
            0,
            float(results["duration_sec"]),
            0,
            0,
        )
        return results

    def _sort_key(c: dict) -> str:
        v = (c.get("vin") or "").strip().upper()
        ts = database.get_last_exo_intelligence_insight_at(v) if v else None
        return ts or "1970-01-01T00:00:00"

    cars_sorted = sorted(cars, key=_sort_key)
    cap = _max_vehicles_per_cycle()
    cars_to_process = cars_sorted[:cap]
    if len(cars) > len(cars_to_process):
        print(f"[EXO] Rotiție cost: {len(cars_to_process)}/{len(cars)} vehicule (cap={cap})")

    for car in cars_to_process:
        vin = (car.get("vin") or "").strip().upper()
        user_id = car.get("user_id")
        if not vin:
            continue

        try:
            brain = database.get_vehicle_brain(vin)
            brain_data = _brain_to_context(brain)

            user_prefs = database.get_user_preferences(int(user_id)) if user_id else {}

            prompt = _build_vehicle_prompt(car, brain_data, user_prefs)
            ctx = f"Vehicul: {car.get('make','')} {car.get('model','')} {car.get('year','')}"

            raw_response = ai_proxy.complete_simple(
                prompt,
                ctx,
                system_override=EXO_SYSTEM_PROMPT,
                task="json_structured",
                max_completion_tokens=1200,
            )

            parsed = _parse_minimax_response(raw_response)

            if not parsed or "insights" not in parsed:
                print(f"[EXO] Răspuns invalid pentru {vin}: {(raw_response or '')[:120]}")
                results["errors"] += 1
                database.upsert_exo_health(vin, ok=False)
                continue

            for insight in parsed.get("insights", [])[:5]:
                if not isinstance(insight, dict):
                    continue
                text = (insight.get("text") or "").strip()
                if not text:
                    continue

                insight_type = (insight.get("type") or "general").strip()
                prefix = INSIGHT_TYPES.get(insight_type, "")
                full_text = f"{prefix} {text}".strip() if prefix else text
                action = insight.get("action") or ""
                if action:
                    full_text += f" → {action}"

                database.insert_exo_insight(
                    vin=vin,
                    insight_text=full_text[:2000],
                    insight_type=insight_type[:64],
                    raw_context=json.dumps(
                        {
                            "priority": insight.get("priority", "normal"),
                            "title": insight.get("title", ""),
                            "source": insight.get("source", "EXO-Observer"),
                            "summary": parsed.get("summary"),
                            "cycle_at": started_at.isoformat(),
                        },
                        ensure_ascii=False,
                    ),
                    engine="exo_intelligence",
                )
                results["insights_added"] += 1

            database.upsert_exo_health(vin, ok=True)
            results["vehicles_processed"] += 1
            print(
                f"[EXO] ✓ {car.get('make','')} {car.get('model','')} ({vin[-6:]}) → "
                f"{len(parsed.get('insights', []))} insights"
            )

        except Exception as e:
            print(f"[EXO] ✗ Eroare pentru {vin}: {e}")
            try:
                database.upsert_exo_health(vin, ok=False)
            except Exception:
                pass
            results["errors"] += 1

    results["duration_sec"] = (datetime.utcnow() - started_at).total_seconds()
    print(f"[EXO] Ciclu încheiat: {results}")

    database.update_exo_scheduler_state(
        datetime.utcnow().isoformat(timespec="seconds"),
        int(results["insights_added"]),
        float(results["duration_sec"]),
        int(results["vehicles_processed"]),
        int(results["errors"]),
    )
    return results
