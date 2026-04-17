"""
Arhive zilnice Mulberry — JSON în research_data/archives/REPORTS_YYYY_MM/
Prefix fișier: REPORT_<MLBR>_<data>.json + sumar global.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import database
from backend import auth_audit
from backend import debug_logger

ROOT = Path(__file__).resolve().parent / "research_data"
ARCHIVES_DIR = ROOT / "archives"
ARCHIVES_ROOT = ARCHIVES_DIR
NOTICE_PATH = ROOT / "archive_last_notice.json"


def _month_folder_name(utc: Optional[datetime] = None) -> str:
    d = utc or datetime.utcnow()
    return f"REPORTS_{d.year}_{d.month:02d}"


def archive_dir_for_now() -> Path:
    d = ARCHIVES_DIR / _month_folder_name()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_mlbr_filename(mlbr: str) -> str:
    s = (mlbr or "UNKNOWN").strip().upper()
    s = re.sub(r"[^A-Z0-9\-]", "_", s)
    return s[:48] or "UNKNOWN"


def _collect_exo_intelligence_snapshot(limit: int = 80) -> Dict[str, Any]:
    con = database.connect()
    try:
        rows = con.execute(
            """
            SELECT vin, insight_text, insight_type, engine, created_at
            FROM exo_daily_insights
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        err_like = []
        all_rows = []
        for r in rows:
            d = dict(r)
            all_rows.append(d)
            txt = (d.get("insight_text") or "").lower()
            eng = (d.get("engine") or "").lower()
            if "error" in txt or "error" in eng or "fail" in txt:
                err_like.append(d)
        return {"recent_insights": all_rows, "suspected_errors": err_like}
    finally:
        con.close()


def _collect_research_snapshot() -> Dict[str, Any]:
    out: Dict[str, Any] = {"fuel_prices": {}, "last_cycle_summary": None}
    try:
        from backend.exo_research_engine import get_latest_fuel_prices

        out["fuel_prices"] = get_latest_fuel_prices()
    except Exception as e:
        out["fuel_error"] = str(e)
    summary_path = ROOT / "last_cycle_summary.json"
    if summary_path.is_file():
        try:
            out["last_cycle_summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as e:
            out["last_cycle_summary_error"] = str(e)
    art = ROOT / "articles_recent.jsonl"
    if art.is_file():
        try:
            lines = art.read_text(encoding="utf-8").splitlines()[-20:]
            out["articles_recent_tail"] = [json.loads(x) for x in lines if x.strip()]
        except Exception as e:
            out["articles_tail_error"] = str(e)
    return out


def _optional_exo_summary_line(payload_hint: str) -> str:
    """Rezumat executive (Groq prin AIProxy); dezactivat cu EXO_ARCHIVE_LLM=0."""
    if os.getenv("EXO_ARCHIVE_LLM", "1").strip() not in ("1", "true", "yes"):
        return ""
    if not (os.getenv("GROQ_API_KEY") or "").strip() and os.getenv("AI_USE_LOCAL_ONLY", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return ""
    try:
        from backend import ai_proxy

        payload = json.loads(payload_hint) if payload_hint.strip().startswith("{") else {"hint": payload_hint[:3500]}
        return ai_proxy.archive_executive_summary(payload)[:4000]
    except Exception:
        try:
            from backend.assistant_exo import ask_exo_fast

            msg = (
                "Sintetizează în max 2 propoziții (română) acest snapshot de sistem auto (JSON scurt):\n"
                + payload_hint[:3500]
            )
            return str(ask_exo_fast(msg))[:800]
        except Exception:
            return ""


def _load_fleet_inventory() -> Optional[Dict[str, Any]]:
    p = ROOT / "fleet_inventory.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _collect_soft_scores_by_vin() -> Dict[str, float]:
    con = database.connect()
    out: Dict[str, float] = {}
    try:
        rows = con.execute("SELECT vin, brain_data FROM vehicle_brains").fetchall()
        for r in rows:
            vin = (r["vin"] or "").strip().upper()
            if not vin:
                continue
            try:
                data = json.loads(r["brain_data"] or "{}")
                out[vin] = float(data.get("soft_score") or 0)
            except Exception:
                continue
    finally:
        con.close()
    return out


def _previous_daily_master_path(for_utc: datetime) -> Optional[Path]:
    prev = for_utc - timedelta(days=1)
    d = ARCHIVES_DIR / _month_folder_name(prev)
    name = f"REPORT_DAILY_SUMMARY_{prev.date().isoformat()}.json"
    p = d / name
    return p if p.is_file() else None


def _soft_score_delta_vs_previous(
    current: Dict[str, float], previous_master: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not previous_master:
        return {"note": "Nu există snapshot anterior (prima zi sau arhivă lipsă)."}
    prev = previous_master.get("fleet_soft_score_snapshot") or {}
    if isinstance(prev, dict) and "by_vin" in prev:
        prev_map = prev.get("by_vin") or {}
    else:
        prev_map = prev if isinstance(prev, dict) else {}
    deltas: Dict[str, Optional[float]] = {}
    for vin, cur_score in current.items():
        if vin in prev_map:
            try:
                deltas[vin] = round(float(cur_score) - float(prev_map[vin]), 3)
            except (TypeError, ValueError):
                deltas[vin] = None
        else:
            deltas[vin] = None
    return {"by_vin": deltas, "previous_date": previous_master.get("date")}


def _device_signature_for_archive() -> str:
    env_sig = (os.getenv("ARCHIVE_DEVICE_HWID") or "").strip()
    if env_sig:
        return env_sig
    p = ROOT / "archive_device_signature.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return str(data.get("hwid") or data.get("device_signature") or "").strip()
        except Exception:
            return ""
    return ""


def generate_daily_archive() -> Dict[str, Any]:
    """
    Colectează date din dev.db, auth_audit, EXO, research; scrie JSON-uri în archives/.
    Ingestie: fleet_inventory.json, ultimele 24h auth_audit, SoftScore din vehicle_brains.
    """
    utc = datetime.utcnow()
    date_str = utc.strftime("%Y-%m-%d")
    ts = utc.isoformat(timespec="seconds") + "Z"
    out_dir = archive_dir_for_now()

    auth_snap = auth_audit.audit_summary_for_archive()
    auth_24h = auth_audit.audit_events_last_hours(24)
    fleet_inv = _load_fleet_inventory()
    soft_by_vin = _collect_soft_scores_by_vin()
    prev_path = _previous_daily_master_path(utc)
    previous_master: Optional[Dict[str, Any]] = None
    if prev_path:
        try:
            previous_master = json.loads(prev_path.read_text(encoding="utf-8"))
        except Exception:
            previous_master = None

    soft_delta = _soft_score_delta_vs_previous(soft_by_vin, previous_master)
    device_sig = _device_signature_for_archive()

    tech = _collect_exo_intelligence_snapshot()
    market = _collect_research_snapshot()
    errors_log = debug_logger.read_recent_errors(80)

    cars: List[Dict[str, Any]] = []
    con = database.connect()
    try:
        rows = con.execute(
            """
            SELECT user_id, vin, make, model, year, fuel, plate, series, mlbr_code, ycr_code
            FROM cars
            WHERE vin IS NOT NULL AND trim(vin) != ''
            ORDER BY id ASC
            """
        ).fetchall()
        for r in rows:
            vin = (r["vin"] or "").strip().upper()
            mlbr = (r["mlbr_code"] or r["ycr_code"] or "").strip() or database.mlbr_code_from_vin(vin)
            cars.append(
                {
                    "user_id": r["user_id"],
                    "vin": vin,
                    "make": r["make"],
                    "model": r["model"],
                    "year": r["year"],
                    "fuel": r["fuel"],
                    "plate": r["plate"],
                    "series": r["series"],
                    "mlbr_code": mlbr,
                }
            )
    finally:
        con.close()

    master = {
        "schema": "mulberry_daily_archive_v2",
        "generated_at": ts,
        "date": date_str,
        "security_auth_audit": auth_snap,
        "security_auth_audit_24h": auth_24h,
        "fleet_inventory": fleet_inv,
        "fleet_soft_score_snapshot": {
            "by_vin": soft_by_vin,
            "avg": round(sum(soft_by_vin.values()) / len(soft_by_vin), 1) if soft_by_vin else None,
        },
        "soft_score_delta_vs_previous": soft_delta,
        "device_signature_authorized": device_sig,
        "technical_exo_intelligence": tech,
        "market_research": market,
        "frontend_errors_log_tail": errors_log,
        "vehicles_index": cars,
    }
    hint = json.dumps(
        {
            "cars": len(cars),
            "auth_counts": auth_snap.get("counts_by_status", {}),
            "auth_24h_events": len(auth_24h),
            "soft_avg": master["fleet_soft_score_snapshot"]["avg"],
            "delta": soft_delta,
        },
        ensure_ascii=False,
    )
    summary_line = _optional_exo_summary_line(hint)
    if summary_line:
        master["executive_summary_bios"] = summary_line

    written: List[str] = []

    master_name = f"REPORT_DAILY_SUMMARY_{date_str}.json"
    master_path = out_dir / master_name
    master_path.write_text(json.dumps(master, indent=2, ensure_ascii=False), encoding="utf-8")
    written.append(str(master_path.relative_to(ROOT)))

    for c in cars:
        mlbr = c.get("mlbr_code") or database.mlbr_code_from_vin(c["vin"])
        fn = f"REPORT_{_safe_mlbr_filename(mlbr)}_{date_str}.json"
        per = {
            "schema": "mulberry_vehicle_archive_v2",
            "generated_at": ts,
            "date": date_str,
            "mlbr_code": mlbr,
            "vehicle": c,
            "technical_exo_intelligence": tech,
            "market_research": market,
            "security_auth_audit": auth_snap,
            "fleet_soft_score_snapshot": master["fleet_soft_score_snapshot"],
            "soft_score_delta_vs_previous": soft_delta,
            "device_signature_authorized": device_sig,
        }
        p = out_dir / fn
        p.write_text(json.dumps(per, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(str(p.relative_to(ROOT)))

    notice = {
        "ARCHIVE_GENERATED": ts,
        "message": f"ARCHIVE_GENERATED: {ts}",
        "files": written,
    }
    NOTICE_PATH.write_text(json.dumps(notice, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[Archive] Daily archive OK: {len(written)} files -> {out_dir}")
    return {"ok": True, "written": written, "notice": notice}


def read_last_notice() -> Optional[Dict[str, Any]]:
    if not NOTICE_PATH.is_file():
        return None
    try:
        return json.loads(NOTICE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
