# backend/scheduler.py — Task-uri automate (APScheduler)
# Motor de Extindere Continuu: ingestion zilnic în ChromaDB + EXO Intelligence (Groq / Ollama)

import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

def _run_ingestion():
    """Rulează ingestion din resources/ în ChromaDB."""
    try:
        from backend.vector_store import ingest_from_resources
        result = ingest_from_resources()
        print(f"[Scheduler] Ingest complet: {result.get('added', 0)} chunk-uri din {result.get('files', [])}")
    except Exception as e:
        print(f"[Scheduler] Eroare ingestion: {e}")


def _run_exo_research():
    """EXO legacy (Ollama) — păstrat pentru teste manuale; nu e în cron implicit."""
    try:
        from backend.exo_research import run_exo_research
        result = run_exo_research()
        print(f"[Scheduler] EXO Research (Ollama): {result.get('insights', 0)} insights, {result.get('cars', 0)} mașini")
    except Exception as e:
        print(f"[Scheduler] Eroare EXO Research: {e}")


def _run_exo_intelligence():
    """EXO Intelligence Engine — Groq/Ollama, insights în SQLite + health checks."""
    try:
        from backend.exo_engine import run_exo_cycle
        result = run_exo_cycle()
        print(
            f"[Scheduler] EXO Intelligence: vehicles={result.get('vehicles_processed', 0)}, "
            f"insights={result.get('insights_added', 0)}, err={result.get('errors', 0)}"
        )
    except Exception as e:
        print(f"[Scheduler] EXO Intelligence: {e}")


def _run_research_engine_safe():
    """EXO Research Engine — RSS/scrape/BNR, clasificare LLM, fișiere + Chroma."""
    try:
        from backend.exo_research_engine import run_research_cycle
        run_research_cycle()
    except Exception as e:
        print(f"[Scheduler] EXO Research Engine: {e}")


def _run_monthly_report():
    """Generează raport lunar pentru toți userii cu vehicul."""
    try:
        from backend.reports import generate_monthly_reports
        generate_monthly_reports()
        print("[Scheduler] Raport lunar generat.")
    except Exception as e:
        print(f"[Scheduler] Eroare raport lunar: {e}")


def _run_daily_archive():
    """Arhivă zilnică JSON (EXO + research + auth_audit) în research_data/archives/."""
    try:
        from backend.archive_service import generate_daily_archive
        generate_daily_archive()
    except Exception as e:
        print(f"[Scheduler] Eroare daily archive: {e}")


def _run_market_intel_skoda_fabia():
    """Wikipedia + Groq → SQLite; intel folosit de MulberryEXO pentru Škoda Fabia 6Y."""
    try:
        from backend.market_intel_skoda import refresh_skoda_fabia_6y

        out = refresh_skoda_fabia_6y()
        if out.get("skipped"):
            print(f"[Scheduler] Market intel Fabia 6Y: oprit ({out.get('reason')})")
        elif out.get("ok"):
            print(f"[Scheduler] Market intel Fabia 6Y: OK — {out.get('sources')} surse")
        else:
            print(f"[Scheduler] Market intel Fabia 6Y: {out}")
    except Exception as e:
        print(f"[Scheduler] Market intel Fabia 6Y: {e}")


def _run_softscore_market_snapshots():
    """Autovit + verificare Groq → fișiere în backend/data/softscore_market/ (max 1×/24h per model)."""
    try:
        from backend.softscore_market_groq import refresh_all_registered_cars

        out = refresh_all_registered_cars(force=False)
        print(
            f"[Scheduler] SoftScore market files: models={out.get('unique_models')}, "
            f"ok={out.get('ok')}, err={out.get('errors')}"
        )
    except Exception as e:
        print(f"[Scheduler] SoftScore market files: {e}")


def _run_daily_insight_cards():
    """Daily Insights — MulberryEXO → SQLite `daily_insight_cards` (carousel dashboard)."""
    if os.getenv("DAILY_INSIGHTS_DISABLE", "").strip().lower() in ("1", "true", "yes", "on"):
        return
    try:
        from backend.daily_insights_service import run_nightly_daily_insights

        out = run_nightly_daily_insights()
        print(f"[Scheduler] Daily insight cards: {out}")
    except Exception as e:
        print(f"[Scheduler] Daily insight cards: {e}")


_scheduler = None


def start_scheduler():
    """Pornește scheduler-ul cu job-uri periodice."""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    # Zilnic la 02:00 — ingestion din resources/
    _scheduler.add_job(
        _run_ingestion,
        CronTrigger(hour=2, minute=0),
        id="nightly_ingestion",
        replace_existing=True,
    )
    # Lunar pe 1, la 03:00 — raport Mulberry
    _scheduler.add_job(
        _run_monthly_report,
        CronTrigger(day=1, hour=3, minute=0),
        id="monthly_report",
        replace_existing=True,
    )
    # Zilnic la 00:30 UTC — arhivă sistem (JSON în research_data/archives/REPORTS_YYYY_MM/)
    _scheduler.add_job(
        _run_daily_archive,
        CronTrigger(hour=0, minute=30),
        id="daily_archive",
        replace_existing=True,
        max_instances=1,
    )
    # EXO Intelligence (Groq / Ollama) — la fiecare 10 minute
    _scheduler.add_job(
        _run_exo_intelligence,
        IntervalTrigger(minutes=10),
        id="exo_intelligence",
        name="EXO Intelligence Cycle",
        replace_existing=True,
        max_instances=1,
    )
    # EXO Research Engine (surse externe) — la fiecare 4 ore
    _scheduler.add_job(
        _run_research_engine_safe,
        IntervalTrigger(hours=4),
        id="exo_research_engine",
        name="EXO Research Engine",
        replace_existing=True,
        max_instances=1,
    )
    # Primul ciclu research la ~30s după boot (best-effort)
    _scheduler.add_job(
        _run_research_engine_safe,
        DateTrigger(run_date=datetime.now() + timedelta(seconds=30)),
        id="exo_research_engine_boot",
        replace_existing=True,
    )
    # Intel piață Fabia 6Y — la 24h (sau MARKET_INTEL_INTERVAL_HOURS), + primul ciclu după boot
    _intel_hours = int(os.getenv("MARKET_INTEL_INTERVAL_HOURS", "24") or "24")
    _intel_hours = max(6, min(_intel_hours, 168))
    _scheduler.add_job(
        _run_market_intel_skoda_fabia,
        IntervalTrigger(hours=_intel_hours),
        id="market_intel_skoda_fabia",
        name="Market intel Škoda Fabia 6Y",
        replace_existing=True,
        max_instances=1,
    )
    _intel_boot = int(os.getenv("MARKET_INTEL_BOOT_SEC", "120") or "120")
    _intel_boot = max(30, min(_intel_boot, 3600))
    _scheduler.add_job(
        _run_market_intel_skoda_fabia,
        DateTrigger(run_date=datetime.now() + timedelta(seconds=_intel_boot)),
        id="market_intel_skoda_fabia_boot",
        replace_existing=True,
    )
    _ss_hours = int(os.getenv("SOFTSCORE_MARKET_INTERVAL_HOURS", "24") or "24")
    _ss_hours = max(6, min(_ss_hours, 168))
    _scheduler.add_job(
        _run_softscore_market_snapshots,
        IntervalTrigger(hours=_ss_hours),
        id="softscore_market_groq_files",
        name="SoftScore market Autovit+Groq files",
        replace_existing=True,
        max_instances=1,
    )
    _ss_boot = int(os.getenv("SOFTSCORE_MARKET_BOOT_SEC", "180") or "180")
    _ss_boot = max(45, min(_ss_boot, 7200))
    _scheduler.add_job(
        _run_softscore_market_snapshots,
        DateTrigger(run_date=datetime.now() + timedelta(seconds=_ss_boot)),
        id="softscore_market_groq_boot",
        replace_existing=True,
    )
    # Daily Insights — înainte de 06:00 (articole zilnice + digest MulberryEXO)
    _scheduler.add_job(
        _run_daily_insight_cards,
        CronTrigger(hour=5, minute=50),
        id="daily_insight_cards",
        name="Daily Insights triple (MulberryEXO)",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    print(
        "[Scheduler] Pornit: ingestion 02:00, EXO Intelligence 10 min, "
        "EXO Research 4h (+ boot 30s), raport lunar 1st 03:00, arhivă zilnică 00:30, "
        f"market intel Fabia 6Y la {_intel_hours}h (+ boot {_intel_boot}s), "
        f"SoftScore market files la {_ss_hours}h (+ boot {_ss_boot}s), "
        "Daily Insights cards 05:50 (înainte de 06:00)"
    )


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
