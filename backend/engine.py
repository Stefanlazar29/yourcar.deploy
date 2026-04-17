# backend/engine.py — Logic Engine (Creierul Analitic)

from datetime import datetime, timedelta
from typing import List
from backend.models import MulberryBrain, CloudFile, Reminder

def check_overdue_reminders(reminders: List[Reminder]) -> int:
    """Returnează numărul de remindere expirate"""
    count = 0
    now = datetime.utcnow()
    
    for r in reminders:
        if r.status == "completed":
            continue
        if r.due_date:
            try:
                due = datetime.fromisoformat(r.due_date.replace('Z', '+00:00'))
                if due < now:
                    count += 1
            except Exception:
                pass
    
    return count

def calculate_document_bonus(cloud_files: List[CloudFile]) -> int:
    """
    Bonus pentru documente verificate:
    - ITP verificat: +15
    - RCA verificat: +15
    - Talon verificat: +10
    - Altele verificate: +5
    """
    bonus = 0
    doc_types = {"ITP": 15, "RCA": 15, "Talon": 10}
    
    for f in cloud_files:
        if f.verified:
            bonus += doc_types.get(f.type, 5)
    
    return min(bonus, 50)  # cap la +50

def process_mulberry_logic(brain: MulberryBrain) -> dict:
    """
    Gândirea centrală — calculează SoftScore + Status Health + Alerts
    
    Formula:
    SoftScore = BASE(50) + DOC_BONUS - OVERDUE_PENALTY
    
    Unde:
    - BASE: 50 (pornire neutră)
    - DOC_BONUS: +15 ITP, +15 RCA, +10 Talon, +5 altele (max +50)
    - OVERDUE_PENALTY: -10 per reminder expirat
    """
    
    # 1. Analizează Cloud-ul: documente verificate
    verified_docs = [d for d in brain.cloud_files if d.verified]
    doc_bonus = calculate_document_bonus(brain.cloud_files)
    
    # 2. Analizează Reminder-ele: task-uri expirate
    overdue_count = check_overdue_reminders(brain.reminders)
    overdue_penalty = overdue_count * 10
    
    # 3. Calculează SoftScore final
    base_score = 50
    raw_score = base_score + doc_bonus - overdue_penalty
    final_score = max(0, min(100, raw_score))
    
    # 4. Determină Status Health
    if final_score >= 80:
        status = "Excelent — Toate documentele în regulă"
    elif final_score >= 60:
        status = "Bun — Lipsesc unele documente"
    elif final_score >= 40:
        status = "Atenție — Verifică documentele"
    else:
        status = "Critic — Acțiune imediată necesară"
    
    # 5. Generează Alerts (acțiuni recomandate)
    alerts = []
    
    # Alert pentru documente lipsă
    has_itp = any(d.type == "ITP" and d.verified for d in brain.cloud_files)
    has_rca = any(d.type == "RCA" and d.verified for d in brain.cloud_files)
    has_talon = any(d.type == "Talon" and d.verified for d in brain.cloud_files)
    
    if not has_itp:
        alerts.append("📄 Încarcă ITP verificat (+15 puncte)")
    if not has_rca:
        alerts.append("🛡️ Încarcă RCA verificat (+15 puncte)")
    if not has_talon:
        alerts.append("📋 Încarcă Talon verificat (+10 puncte)")
    
    # Alert pentru remindere expirate
    if overdue_count > 0:
        alerts.append(f"⏰ {overdue_count} reminder{'e' if overdue_count > 1 else ''} expirat{'e' if overdue_count > 1 else ''} (-{overdue_penalty} puncte)")
    
    # Alert pentru calibrare
    if final_score < 40:
        alerts.append("⚠️ Urgent: Calibrează datele vehiculului")
    
    return {
        "score": round(final_score, 2),
        "status": status,
        "alerts": alerts,
        "stats": {
            "verified_docs": len(verified_docs),
            "overdue_tasks": overdue_count,
            "doc_bonus": doc_bonus,
            "overdue_penalty": overdue_penalty
        }
    }

def sync_vehicle_brain(brain: MulberryBrain) -> MulberryBrain:
    """
    Actualizează creierul vehiculului cu noua analiză
    Returnează obiectul MulberryBrain actualizat
    """
    analysis = process_mulberry_logic(brain)
    
    brain.soft_score = analysis["score"]
    brain.status_health = analysis["status"]
    brain.last_sync = datetime.utcnow().isoformat()
    
    return brain
