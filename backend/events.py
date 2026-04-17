# backend/events.py — Event Triggers pentru notificări proactive
# Detectează evenimente (OBD/telemetrie) și declanșează conversații

from datetime import datetime
from typing import Optional, Dict, Any

# Queue notificări proactive per user (WebSocket le preia)
_pending_proactive: Dict[str, list] = {}


def push_proactive_for_user(user_id: str, notification: Dict[str, Any]) -> None:
    """Adaugă notificare în coada user-ului pentru WebSocket."""
    key = str(user_id)
    if key not in _pending_proactive:
        _pending_proactive[key] = []
    _pending_proactive[key].append(notification)


def pop_pending_proactive(user_id: str) -> Optional[Dict[str, Any]]:
    """Preia ultima notificare proactivă din coadă (FIFO)."""
    key = str(user_id)
    lst = _pending_proactive.get(key, [])
    if not lst:
        return None
    return lst.pop(0)


def record_drive_event(
    user_id: str,
    vin: Optional[str],
    avg_speed_kmh: float,
    duration_min: float,
    hour_of_day: int,
) -> Optional[Dict[str, Any]]:
    """
    Înregistrează un drum (ex. din OBD/GPS).
    Dacă se potrivește cu regulile proactive, returnează notificare.
    """
    # Regulă: viteză medie > 80 km/h ȘI durată > 2h ȘI ora > 20:00
    if avg_speed_kmh > 80 and duration_min > 120 and hour_of_day >= 20:
        return {
            "code": "long_drive_check",
            "title": "Drum lung încheiat",
            "message": "A fost un drum lung azi! Vrei să analizăm cum a fost la condus și cum influențează SoftScore-ul? Deschide Mulberry Assistant.",
            "type": "info",
            "timestamp": datetime.utcnow().isoformat(),
        }
    return None


def record_aggressive_braking(user_id: str, vin: Optional[str], count: int) -> Optional[Dict[str, Any]]:
    """Dacă frânări agresive detectate (OBD) — trigger conversație."""
    if count >= 5:
        return {
            "code": "aggressive_braking",
            "title": "Stil de condus dinamic",
            "message": f"Am observat {count} frânări puternice. Stilul tău uzează plăcuțele și discurile mai repede. Vrei un reminder pentru verificare la service?",
            "type": "warning",
            "timestamp": datetime.utcnow().isoformat(),
        }
    return None


def get_proactive_for_event(
    user_id: str,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Generează notificare proactivă pentru un tip de eveniment.
    event_type: "long_drive", "aggressive_braking", "monthly_report_ready"
    """
    if event_type == "long_drive":
        p = payload or {}
        return record_drive_event(
            user_id=user_id,
            vin=p.get("vin"),
            avg_speed_kmh=float(p.get("avg_speed_kmh", 0)),
            duration_min=float(p.get("duration_min", 0)),
            hour_of_day=int(p.get("hour_of_day", datetime.utcnow().hour)),
        )
    if event_type == "aggressive_braking":
        p = payload or {}
        return record_aggressive_braking(
            user_id=user_id,
            vin=p.get("vin"),
            count=int(p.get("count", 0)),
        )
    if event_type == "monthly_report_ready":
        return {
            "code": "monthly_report",
            "title": "Raportul tău lunar este gata",
            "message": "Mulberry Report a fost generat. Vrei să-l parcurgem împreună în Assistant?",
            "type": "info",
            "timestamp": datetime.utcnow().isoformat(),
        }
    return None
