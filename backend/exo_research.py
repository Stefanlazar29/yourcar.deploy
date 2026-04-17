# backend/exo_research.py — EXO-Observer: "Ochiul" care scanează piața și analizează cu Ollama
# Rulează la 04:00 AM (cron) sau manual. Salvează Daily Insights în LocalBase.

import os
import sys
import json
import requests
from datetime import datetime
from typing import Optional

# Adaugă rădăcina proiectului la path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")


# Date simulate pentru "Research Engine" (știri, prețuri, legislație)
# În producție: scraping sau API-uri auto reale
MARKET_CONTEXT = [
    "Preț mediu plăcuțe frână Dacia Logan 2018–2022: 180–320 lei/set. Creștere ~8% YoY.",
    "Taxă nouă mediu 2025: vehicule >1600cc plătesc +15% la impozit. Verifică seria ta.",
    "Scădere preț revizie la parteneri autorizați: promoții lunare -15% la schimb ulei.",
    "Piață second-hand România: modele 2018–2020 încă cerute, depreciere ~12%/an.",
    "ITP online: programare anticipată recomandată. Perioade aglomerate octombrie–noiembrie.",
]


def _get_vehicle_context(car: dict) -> str:
    """Construiește context vehicul pentru prompt Ollama."""
    parts = []
    if car.get("make"):
        parts.append(f"Marcă: {car['make']}")
    if car.get("model"):
        parts.append(f"Model: {car['model']}")
    if car.get("year"):
        parts.append(f"An: {car['year']}")
    if car.get("fuel"):
        parts.append(f"Combustibil: {car['fuel']}")
    if car.get("km_actuali"):
        parts.append(f"Km actuali: {car['km_actuali']}")
    if car.get("rca_expiry"):
        parts.append(f"RCA expiră: {car['rca_expiry']}")
    if car.get("itp_expiry"):
        parts.append(f"ITP expiră: {car['itp_expiry']}")
    if car.get("ycs_score") is not None:
        parts.append(f"SoftScore: {car['ycs_score']}")
    return "\n".join(parts) if parts else "Date vehicul incomplete"


def _call_ollama(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """Trimite la Ollama /api/generate și returnează răspunsul."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("response", "").strip()
    except requests.RequestException as e:
        print(f"[EXO] Ollama error: {e}")
        return None
    except Exception as e:
        print(f"[EXO] Unexpected: {e}")
        return None


def _run_health_check(vin: str, car: dict) -> bool:
    """Verifică integritatea datelor: VIN valid, câmpuri esențiale."""
    vin_ok = vin and len(vin.strip()) == 17 and vin.isalnum()
    make_ok = bool(car.get("make") or car.get("model"))
    return vin_ok and make_ok


def run_exo_research() -> dict:
    """
    Logica principală EXO-Observer:
    1. Citește mașinile din LocalBase
    2. Simulează date piață (sau API/scraping real)
    3. Trimite context către Ollama
    4. Salvează concluzia în exo_daily_insights
    5. Salvează health check în exo_health_checks
    """
    try:
        from backend import database
    except ImportError:
        print("[EXO] Eroare: backend.database nu a fost găsit. Rulează din rădăcina proiectului.")
        return {"ok": False, "error": "import", "insights": 0}

    database.init_db()
    cars = database.get_all_cars_with_vin()

    if not cars:
        print("[EXO] Niciun vehicul cu VIN în LocalBase. Skip.")
        return {"ok": True, "insights": 0, "cars": 0}

    system_prompt = (
        "Ești EXO, asistentul Mulberry pentru vehicule. "
        "Analizezi date brute (prețuri, știri, legislație) pentru un utilizator cu mașina dată. "
        "Răspunde DOAR cu 1–2 propoziții scurte, în română, concrete: ce îi influențează SoftScore-ul sau portofelul. "
        "Nu adăuga preambule. Nu repeta datele vehiculului."
    )

    insights_saved = 0
    for car in cars:
        vin_raw = (car.get("vin") or "").strip()
        if not vin_raw:
            continue
        vin = vin_raw.upper()

        vehicle_ctx = _get_vehicle_context(car)
        market_sample = "\n".join(MARKET_CONTEXT[:3])  # primele 3 contexturi

        prompt = f"""Date vehicul:
{vehicle_ctx}

Date piață / știri (extrase):
{market_sample}

---

Extrage doar ce îi influențează utilizatorului SoftScore-ul sau portofelul. Răspunde concis."""

        response = _call_ollama(prompt, system=system_prompt)
        if response:
            insight_type = "general"
            if "tax" in response.lower() or "impozit" in response.lower() or "mediu" in response.lower():
                insight_type = "legislation"
            elif "preț" in response.lower() or "lei" in response.lower() or "revizie" in response.lower():
                insight_type = "price"

            database.insert_exo_insight(
                vin=vin,
                insight_text=response,
                insight_type=insight_type,
                raw_context=market_sample[:500],
                engine="exo_research_ollama",
            )
            insights_saved += 1
            print(f"[EXO] Insight salvat pentru {vin[:8]}...: {response[:80]}...")

        # Health check
        ok = _run_health_check(vin, car)
        database.upsert_exo_health(vin, ok)
        print(f"[EXO] Health check {vin[:8]}: {'OK' if ok else 'necomplet'}")

    return {
        "ok": True,
        "insights": insights_saved,
        "cars": len(cars),
    }


def main():
    print(f"[EXO] Pornire research la {datetime.utcnow().isoformat()}")
    result = run_exo_research()
    print(f"[EXO] Final: {result}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
