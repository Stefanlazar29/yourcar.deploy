"""
Descriere profil MyMulberry — generată de FastAPI (AI) din istoric vehicul + brain + chat.
Fără enumerare de funcții din app; focus: model, istoric, tip de utilizare.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from backend import database, rag_qdata
from backend.ai_proxy import complete_chat

MAX_CONTEXT = 12000
MAX_OUT_CHARS = 1800

PROFILE_NARRATIVE_SYSTEM = """Ești redactor tehnic auto pentru profilul Mulberry (limba română).

Primești DOAR fapte din CONTEXT (date vehicul, documente Cloud, remindere, SoftScore, fragmente chat, insight).

Scrie o descriere pentru proprietar (2–3 paragrafe), folosind exclusiv tag-uri HTML:
<p class="profile-model-p profile-literary-p">...</p>

Conținut obligatoriu:
- Prezintă vehiculul pe scurt (marcă, generație dacă e în context, motorizare/tip combustibil, vârstă, km dacă există).
- Evidențiază ce reiese din ISTORICUL din context (documente la zi sau întârzieri, nivel întreținere din remindere, scor Mulberry dacă e menționat).
- Spune clar la ce TIP DE UTILIZARE se potrivește cel mai bine (ex.: navetă urbană, familie și drum lung ocazional, flotă ușoară, șofer pe distanțe mari) — rezonabil, fără exagerări.

Interdicții stricte:
- NU lista funcții ale aplicației Mulberry (fără „Cloud”, „QR”, „reminder în app”, „asistent chat”, „MyMulberry”, „ecosistem”).
- NU inventa defecțiuni, accidente sau service dacă nu apar în context.
- NU folosi bullet-uri sau liste HTML; doar paragrafe <p>.
- Ton pragmatic, fără marketing gol și fără metafore literare exagerate."""


def _brain_lines(brain: Any) -> List[str]:
    lines: List[str] = []
    if not brain:
        return ["Brain Mulberry: indisponibil în context."]
    try:
        ss = float(getattr(brain, "soft_score", 0) or 0)
        st = getattr(brain, "status_health", None) or "—"
        lines.append(f"SoftScore (brain): {ss:.1f}%. Stare: {st}.")
        cfs = getattr(brain, "cloud_files", None) or []
        if cfs:
            bits = []
            for d in cfs[:14]:
                if isinstance(d, dict):
                    t = (d.get("type") or "?").strip()
                    v = bool(d.get("verified"))
                else:
                    t = (getattr(d, "type", None) or "?").strip()
                    v = bool(getattr(d, "verified", False))
                bits.append(f"{t}{' (verif.)' if v else ''}")
            lines.append("Documente în dosar: " + ", ".join(bits))
        rem = getattr(brain, "reminders", None) or []
        if rem:

            def _done(r: Any) -> bool:
                st = r.get("status") if isinstance(r, dict) else getattr(r, "status", None)
                return st in ("done", "completed")

            done_n = sum(1 for r in rem if _done(r))
            lines.append(f"Remindere întreținere: {done_n}/{len(rem)} marcate finalizate.")
    except Exception:
        lines.append("Brain: detalii parțiale.")
    return lines


def _chat_block(user_id: int, limit: int = 16) -> str:
    rows = database.list_recent_chat_messages_for_user(user_id, limit=limit)
    if not rows:
        return "Istoric chat salvat: lipsă."
    lines = []
    for m in rows:
        role = (m.get("role") or "user").strip()
        body = (m.get("text") or "").strip().replace("\n", " ")
        if len(body) > 220:
            body = body[:220] + "…"
        lines.append(f"{role}: {body}")
    return "Fragmente conversație (cronologic):\n" + "\n".join(lines)


def build_profile_context(user_id: int, car: database.CarRow, brain: Optional[Any]) -> str:
    blocks: List[str] = []
    blocks.append(rag_qdata.build_qdata_text_from_car(car, brain))
    blocks.append("\n".join(_brain_lines(brain)))
    blocks.append(_chat_block(user_id, 18))
    vin = (car.vin or "").strip().upper()
    if vin:
        ins = database.vehicle_insight_latest_for_vehicle(user_id, vin)
        if ins and (ins.get("reply") or "").strip():
            blocks.append("Ultim rezumat insight: " + (ins.get("reply") or "")[:650])
    return "\n\n---\n\n".join(blocks)[:MAX_CONTEXT]


def sanitize_narrative_html(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    s = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", s, flags=re.I)
    s = re.sub(r"on\w+\s*=", "", s, flags=re.I)
    s = s[:MAX_OUT_CHARS]
    if not re.search(r"<p\b", s, re.I):
        parts = [p.strip() for p in re.split(r"\n\s*\n", re.sub(r"<[^>]+>", "", s)) if p.strip()]
        return "".join(
            f'<p class="profile-model-p profile-literary-p">{re.sub(r"<[^>]+>", "", p)}</p>'
            for p in parts[:5]
        )
    return s


def generate_profile_narrative(user_id: int) -> str:
    car = database.get_car_for_user(user_id)
    if not car or not (car.vin or "").strip():
        raise ValueError("Lipsește vehiculul sau VIN pentru profil.")
    vin = (car.vin or "").strip().upper()
    brain = database.get_vehicle_brain(vin)
    ctx = build_profile_context(user_id, car, brain)
    user_turn = (
        "Generează descrierea pentru profil folosind STRICT informațiile din CONTEXT. "
        "Respectă clasele CSS indicate în instrucțiuni pentru fiecare <p>."
    )
    raw = complete_chat(
        PROFILE_NARRATIVE_SYSTEM,
        [{"role": "user", "content": user_turn + "\n\n--- CONTEXT ---\n" + ctx}],
        task="fast_chat",
        max_completion_tokens=900,
    )
    out = sanitize_narrative_html(raw)
    if not out:
        raise RuntimeError("Modelul nu a returnat text valid.")
    return out


def generate_and_persist_profile_narrative(user_id: int) -> tuple[str, str]:
    text = generate_profile_narrative(user_id)
    now = database._now_iso()
    database.set_car_profile_narrative(user_id, text, now)
    return text, now
