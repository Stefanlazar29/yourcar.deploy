# backend/reports.py — Agent de Analiză — Rapoarte automate
# Raport lunar/săptămânal cu profilare (tag-uri: șofer agresiv, etc.)

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

def _get_all_users_with_cars():
    """Returnează lista (user_id, vin, car) pentru raport."""
    try:
        from backend import database
        con = database.connect()
        rows = con.execute("""
            SELECT u.id as user_id, c.vin, c.make, c.model
            FROM users u
            JOIN cars c ON c.user_id = u.id
            WHERE c.vin IS NOT NULL AND c.vin != ''
        """).fetchall()
        con.close()
        return [{"user_id": r["user_id"], "vin": r["vin"], "make": r["make"], "model": r["model"]} for r in rows]
    except Exception:
        return []


def _generate_report_for_user(user_id: int, vin: str, make: str, model: str) -> Optional[Dict[str, Any]]:
    """Generează conținut raport pentru un user."""
    try:
        from backend import database
        from backend.engine import process_mulberry_logic
        brain = database.get_vehicle_brain(vin)
        if not brain:
            return None
        analysis = process_mulberry_logic(brain)
        score = analysis.get("score", brain.soft_score)
        alerts = analysis.get("alerts", [])
        pending = [r for r in brain.reminders if r.status != "completed"]

        # Tag-uri simple (psihologic)
        tags = []
        if alerts and score < 50:
            tags.append("documente în urmă")
        if len(pending) > 3:
            tags.append("multe task-uri în așteptare")
        # În viitor: tag "șofer agresiv" din telemetrie

        month_name = datetime.utcnow().strftime("%B %Y")
        vehicle = f"{make or ''} {model or ''}".strip() or "vehicul"

        return {
            "user_id": user_id,
            "vin": vin,
            "vehicle": vehicle,
            "month": month_name,
            "score": score,
            "score_delta": None,  # Poate fi calculat vs luna trecută
            "status": brain.status_health,
            "alerts": alerts,
            "reminders_pending": [r.task for r in pending[:5]],
            "tags": tags,
            "suggestion": "Verifică documentele și reminderele în Mulberry. Adaugă ITP, Raport lunar sau Verifică Index.",
        }
    except Exception:
        return None


def generate_monthly_reports() -> List[Dict[str, Any]]:
    """
    Generează rapoarte lunare pentru toți userii.
    Salvează în storage și declanșează notificare proactivă.
    """
    from backend.events import push_proactive_for_user
    reports = []
    for rec in _get_all_users_with_cars():
        r = _generate_report_for_user(
            rec["user_id"],
            rec["vin"],
            rec.get("make", ""),
            rec.get("model", ""),
        )
        if r:
            reports.append(r)
            _store_report_for_user(rec["user_id"], r)
            notif = {
                "code": "monthly_report",
                "title": "Raportul tău lunar este gata",
                "message": "Mulberry Report a fost generat. Vrei să-l parcurgem împreună în Assistant?",
                "type": "info",
                "timestamp": datetime.utcnow().isoformat(),
            }
            push_proactive_for_user(str(rec["user_id"]), notif)
    return reports


_REPORTS_CACHE: Dict[int, Dict] = {}


def _store_report_for_user(user_id: int, report: Dict):
    """Stochează raportul pentru user (în producție: DB sau Redis)."""
    _REPORTS_CACHE[user_id] = report


def get_latest_report(user_id: int) -> Optional[Dict]:
    """Returnează ultimul raport pentru user."""
    return _REPORTS_CACHE.get(user_id)
