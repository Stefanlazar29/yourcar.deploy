"""
Narațiune RAG „umană”: leagă manualul local, profilul vehiculului (serie, motor),
SoftScore / documente Cloud și remindere — fără ton sec de robot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from backend.manual_skoda import ManualAnalysis


def _has_verified_itp(cloud_files: List[dict]) -> bool:
    return any((f.get("type") == "ITP" and f.get("verified")) for f in cloud_files or [])


def build_narrative_prefix(
    context: Dict[str, Any],
    message_lower: str,
    vin: Optional[str],
    manual: "ManualAnalysis",
    brain_soft: Optional[float],
    brain_status: Optional[str],
) -> str:
    """
    Paragraf introductiv înainte de răspunsul detaliat.
    Reminderele = pastile laterale, nu blocaj central.
    """
    chunks: List[str] = []

    marca = (context.get("marca") or "").strip()
    model = (context.get("model") or "").strip()
    series = (context.get("series") or "").strip()
    fuel = (context.get("fuel") or "").strip().lower()
    cloud = context.get("cloud_files") or []

    label_parts = [p for p in [marca, series, model] if p]
    if label_parts:
        vlabel = " · ".join(label_parts)
        chunks.append(f"Îți vorbesc în contextul **{vlabel}**")
        if series:
            chunks[-1] += f" (cod serie **{series}** ca în Mulberry ID)"

    if vin and brain_soft is not None:
        if brain_soft < 60:
            chunks.append(
                f"**SoftScore** e la **{brain_soft:.1f}%** — destul de mic până pui documentele la zi."
                + (f" Stare tehnică reținută: *{brain_status}*." if brain_status else "")
            )
        else:
            chunks.append(f"**SoftScore** e la **{brain_soft:.1f}%** — poți îl menține cu Cloud și remindere la punct.")

    if cloud and not _has_verified_itp(cloud):
        chunks.append("Un motiv frecvent pentru scor mic e **ITP neconfirmat** în Mulberry Cloud; când îl încarci, bifează verificarea.")

    if "1.2" in fuel or "tsi" in fuel or "1.2" in message_lower or "tsi" in message_lower:
        chunks.append(
            "Pe **1.2 TSI**, manualul local (Fabia 6Y) spune să fim atenți și la **consumul de ulei** — merită verificat, nu doar ITP-ul."
        )

    if manual.excerpts:
        chunks.append("Am corelat întrebarea ta cu **manualul mașinii** (extras mai jos).")

    reminders = context.get("reminders") or []
    pending = [r for r in reminders if r.get("status") == "pending"]
    if pending:
        chunks.append(
            f"Ai **{len(pending)} reminder{'e' if len(pending) > 1 else ''}** — gândește-le ca **notițe laterale** (ITP, revizie), nu ca obstacol în fața chat-ului; le poți rezolva când vrei."
        )

    if not chunks:
        return ""

    return "💬 " + " ".join(chunks) + "\n\n"
