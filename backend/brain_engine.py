# backend/brain_engine.py — Creierul contextual pentru subiecte de conversație și notificări proactive

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# Lunile în română (index 1–12)
MONTH_NAMES = ["", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
               "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie"]


def generate_conversation_starter(
    vehicle_data: Dict[str, Any],
    external_data: Dict[str, Any],
) -> str:
    """
    Pattern Matching + context pentru subiecte de conversație auto.
    Dacă există un pattern clar (ex: iarnă, anvelope vara) → subiect fix.
    Altfel → euristică bazată pe context (fără LLM extern).
    """
    temp = external_data.get("temperature")
    month = external_data.get("month") or datetime.utcnow().month
    location = (external_data.get("location") or "").lower()
    tyres_type = (vehicle_data.get("tyres_type") or "").lower()
    model = vehicle_data.get("model") or "mașina ta"
    marca = vehicle_data.get("marca") or ""

    # ——— Pattern 1: Pregătire iarnă (temp < 7°C și/sau luni nov–feb)
    if (temp is not None and temp < 7) or month in (11, 12, 1, 2):
        if "summer" in tyres_type or tyres_type == "vara":
            return f"Pregătire de iarnă: Verifică anvelopele și antigelul pentru {model}."
        return f"Pregătire de iarnă: Anvelope de iarnă și lichid parbriz pentru {model}."

    # ——— Pattern 2: Pregătire vară (apr–iun, temp > 20)
    if (temp is not None and temp > 20) or month in (4, 5, 6, 7, 8):
        if "winter" in tyres_type or tyres_type == "iarna":
            return f"Tranziție la vară: Schimbul anvelopelor de vară pentru {model}."
        return f"Verificare de vară: Aer condiționat și lichid răcitor pentru {model}."

    # ——— Pattern 3: Octombrie (exemplul din spec)
    if month == 10:
        return f"Pregătirea de iarnă: Verificarea anvelopelor și antigelului pentru {model}."

    # ——— Pattern 4: Locație specifică (ex: Buzău — clima rece)
    if "buzau" in location or "buzău" in location:
        return f"Clima rece în {location.capitalize()}: Verifică lichidul de parbriz și bateria pentru {model}."

    # ——— Pattern 5: Lună generică — subiect preventiv
    month_name = MONTH_NAMES[month] if 1 <= month <= 12 else "acest"
    return f"Sfat pentru {month_name}: Revizie preventivă și verificare generală la {model}."


def check_for_alerts(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Verifică alertele pentru user (mașina asociată).
    Returnează notificare proactivă dacă există ceva urgent
    (ITP/RCA expirat sau în curând, SoftScore scăzut, remindere expirate).
    """
    from backend import database

    try:
        uid = int(user_id) if str(user_id).isdigit() else None
        if uid is None:
            return None
        car = database.get_car_for_user(uid)
        if not car or not car.vin:
            return None

        brain = database.get_vehicle_brain(car.vin)
        if not brain:
            return None

        from backend.engine import process_mulberry_logic
        analysis = process_mulberry_logic(brain)
        alerts = analysis.get("alerts", [])
        score = analysis.get("score", brain.soft_score)
        model = brain.model or brain.marca or "mașina ta"

        # ITP în curând sau expirat
        if car.itp_expiry:
            try:
                exp_str = car.itp_expiry.replace("Z", "").split("T")[0]
                exp = datetime.fromisoformat(exp_str).date()
                today = datetime.utcnow().date()
                days = (exp - today).days
                if days < 0:
                    return _make_notification(
                        "itp_expired",
                        "Nu uita de ITP!",
                        f"ITP-ul la {model} a expirat. Programează-te acum pentru a evita amenzile.",
                        "warning",
                    )
                if 0 <= days <= 14:
                    return _make_notification(
                        "itp_soon",
                        "ITP în curând",
                        f"ITP la {model} expiră în {days} zile. Programează-te în timp util.",
                        "info",
                    )
            except Exception:
                pass

        # RCA în curând
        if car.rca_expiry:
            try:
                exp_str = car.rca_expiry.replace("Z", "").split("T")[0]
                exp = datetime.fromisoformat(exp_str).date()
                today = datetime.utcnow().date()
                days = (exp - today).days
                if days < 0:
                    return _make_notification(
                        "rca_expired",
                        "RCA expirat",
                        f"Asigurarea la {model} a expirat. Reînnoiește urgent.",
                        "warning",
                    )
                if 0 <= days <= 21:
                    return _make_notification(
                        "rca_soon",
                        "RCA în curând",
                        f"Asigurarea la {model} expiră în {days} zile. Reînnoiește în timp.",
                        "info",
                    )
            except Exception:
                pass

        # Alerte din engine (documente lipsă, remindere)
        if alerts:
            first = alerts[0] if alerts else ""
            return _make_notification(
                "engine_alert",
                "Mulberry te avertizează",
                first if len(first) <= 120 else first[:117] + "...",
                "warning" if score < 50 else "info",
            )

        # SoftScore critic
        if score < 40:
            return _make_notification(
                "score_critical",
                "SoftScore scăzut",
                f"Indexul {model} e sub 40%. Verifică documentele și reminderele.",
                "warning",
            )

        return None
    except Exception:
        return None


def _make_notification(
    code: str,
    title: str,
    message: str,
    ntype: str = "info",
) -> Dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "message": message,
        "type": ntype,
        "timestamp": datetime.utcnow().isoformat(),
    }


def get_conversation_starter_for_user(
    user_id: str,
    external_data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generează un subiect de conversație pentru user, cu datele vehiculului.
    Folosit atât pentru notificări, cât și pentru prompt-uri inițiale.
    """
    from backend import database

    try:
        uid = int(user_id) if str(user_id).isdigit() else None
        if uid is None:
            return None
        car = database.get_car_for_user(uid)
        if not car:
            return None

        vehicle_data = {
            "marca": car.make or "",
            "model": car.model or "",
            "tyres_type": "",  # Poate fi extins din profil
        }
        ext = external_data or {}
        ext.setdefault("month", datetime.utcnow().month)
        return generate_conversation_starter(vehicle_data, ext)
    except Exception:
        return None


def update_market_value(
    v_base_lei: float,
    vehicle_year: Optional[int],
    current_soft_score: float,
    *,
    annual_depreciation: float = 0.12,
    current_year: Optional[int] = None,
) -> dict:
    """
    Depreciere inteligentă:
    - Valoare de bază (V_base) = preț piață model (aprox.)
    - Depreciere temporală: V_base * (1 - D_t) ** age (D_t ~ 10-15%)
    - Factor Mulberry (SoftScore): aplică bonus/amendă în jurul pivotului 70%
      score_modifier = (SoftScore - 70) / 150
      clamp: [-20%, +10%]
    """
    if v_base_lei is None:
        v_base_lei = 0.0

    if current_year is None:
        current_year = datetime.utcnow().year

    age = 0
    if vehicle_year:
        try:
            age = int(current_year) - int(vehicle_year)
            age = max(0, age)
        except Exception:
            age = 0

    depreciation_factor = 1.0 - float(annual_depreciation)
    market_value_temporal = float(v_base_lei) * (depreciation_factor ** age)

    score_modifier = (float(current_soft_score) - 70.0) / 150.0
    # Ajustăm drastic când SoftScore e foarte mic / foarte mare (clamp comentariu)
    score_modifier = max(-0.2, min(0.1, score_modifier))

    final_estimate = market_value_temporal * (1.0 + score_modifier)

    # Rotunjire la sute lei ca să fie UX-friendly
    final_rounded = round(final_estimate, -2)
    temporal_rounded = round(market_value_temporal, -2)
    delta_rounded = round(final_rounded - temporal_rounded, -2)

    # Valoare pierdută estimativ pe 1 an (din depreciere temporală)
    annual_loss_lei = final_rounded * float(annual_depreciation)
    annual_loss_rounded = round(annual_loss_lei, -2)

    return {
        "age_years": age,
        "annual_depreciation": float(annual_depreciation),
        "score_modifier": float(score_modifier),
        "market_value_temporal_lei": float(temporal_rounded),
        "estimated_value_lei": float(final_rounded),
        "delta_vs_market_lei": float(delta_rounded),
        "annual_value_loss_lei": float(annual_loss_rounded),
    }
