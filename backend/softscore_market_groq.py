"""
SoftScore · verificare piață (Groq) peste statistici Autovit.

- Colectează mediană/min/max din listări (valuation_engine.get_market_prices_autovit).
- Trimite rezumatul la Groq (JSON structurat) pentru a verifica coerența mediei față de eșantion.
- Scrie fișiere interne cu timestamp; refresh complet cel mult o dată la 24h per model (cheie marcă+model+an).

Director: backend/data/softscore_market/{latest,history,refresh_state.json}
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend import database
from backend.ai_proxy import complete_chat
from backend.database import CarRow
from backend.valuation_engine import get_market_prices_autovit
from backend.vehicle_dto import MulberryVehicleDTO, vehicle_dto_from_car_row

DATA_ROOT = Path(__file__).resolve().parent / "data" / "softscore_market"
LATEST_DIR = DATA_ROOT / "latest"
HISTORY_DIR = DATA_ROOT / "history"
STATE_FILE = DATA_ROOT / "refresh_state.json"

REFRESH_INTERVAL = timedelta(hours=int(os.getenv("SOFTSCORE_MARKET_INTERVAL_HOURS", "24") or "24"))
ENABLED = os.getenv("SOFTSCORE_MARKET_GROQ", "1").strip().lower() not in ("0", "false", "no")


def _env_skip_groq() -> bool:
    return os.getenv("AI_SKIP_GROQ", "").strip().lower() in ("1", "true", "yes", "on")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "x"


def model_key_from_dto(v: MulberryVehicleDTO) -> str:
    y = str(v.an or "").strip()[:4] or "0000"
    return f"{_slug(v.marca or '')}-{_slug(v.model or '')}-{y}"


def _ensure_dirs() -> None:
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _load_state() -> Dict[str, Any]:
    _ensure_dirs()
    if not STATE_FILE.is_file():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    _ensure_dirs()
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _parse_json_from_llm(raw: str) -> Dict[str, Any]:
    t = (raw or "").strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.I)
        if m:
            t = m.group(1).strip()
    try:
        out = json.loads(t)
        if isinstance(out, dict):
            return out
    except json.JSONDecodeError:
        pass
    i0 = t.find("{")
    i1 = t.rfind("}")
    if i0 >= 0 and i1 > i0:
        try:
            out = json.loads(t[i0 : i1 + 1])
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError:
            pass
    return {
        "parse_error": True,
        "raw_excerpt": (t[:800] + "…") if len(t) > 800 else t,
    }


def _groq_verify_sample(autovit: Dict[str, Any], marca: str, model: str, an: int, km: int) -> Dict[str, Any]:
    if _env_skip_groq():
        return {
            "skipped": True,
            "reason": "AI_SKIP_GROQ",
            "median_plausible": None,
            "notes_ro": "Verificare LLM dezactivată (AI_SKIP_GROQ).",
        }
    system = (
        "Ești analist piață auto second-hand (România). Nu ai acces internet; lucrezi DOAR cu JSON-ul furnizat "
        "(statistici extrase din listări publice). Nu inventa cifre noi; evaluezi doar coerența eșantionului.\n"
        "Răspunde STRICT cu un singur obiect JSON (fără markdown, fără text în afara JSON), chei:\n"
        '  "median_plausible": boolean,\n'
        '  "avg_consistent": boolean,\n'
        '  "confidence_0_1": number,\n'
        '  "notes_ro": string (max 500 caractere, română),\n'
        '  "red_flags": array de string-uri (ex: moneda_mixed, esantion_mic).\n'
    )
    payload = {
        "marca": marca,
        "model": model,
        "an": an,
        "km_approx": km,
        "autovit_sample": autovit,
    }
    user = "Date eșantion:\n" + json.dumps(payload, ensure_ascii=False, indent=2)[:12000]
    try:
        raw = complete_chat(
            system,
            [{"role": "user", "content": user}],
            task="json_structured",
            max_completion_tokens=900,
        )
        return _parse_json_from_llm(raw)
    except Exception as e:
        return {"error": str(e), "median_plausible": None, "notes_ro": "Eroare apel Groq."}


def _should_refresh(mkey: str, force: bool) -> bool:
    if force:
        return True
    st = _load_state().get(mkey) or {}
    last = st.get("last_utc")
    if not last:
        return True
    try:
        t = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    return datetime.now(timezone.utc) - t >= REFRESH_INTERVAL


def build_snapshot_for_dto(v: MulberryVehicleDTO, *, force: bool = False) -> Dict[str, Any]:
    """
    Construiește snapshot piață + verificare Groq; scrie fișiere dacă e cazul (interval 24h sau force).
    Returnează dict-ul snapshot (din cache sau proaspăt).
    """
    if not ENABLED:
        return {"disabled": True, "reason": "SOFTSCORE_MARKET_GROQ=0"}

    mkey = model_key_from_dto(v)
    _ensure_dirs()

    latest_path = LATEST_DIR / f"{mkey}.json"
    if (
        not force
        and latest_path.is_file()
        and not _should_refresh(mkey, False)
    ):
        try:
            cached = json.loads(latest_path.read_text(encoding="utf-8"))
            cached["cached"] = True
            return cached
        except (json.JSONDecodeError, OSError):
            pass

    try:
        year = int(str(v.an or "").strip()[:4])
    except (TypeError, ValueError):
        year = datetime.now().year
    km = int(v.km_actuali or 0)
    marca = (v.marca or "").strip() or "necunoscut"
    model = (v.model or "").strip() or "necunoscut"

    autovit = get_market_prices_autovit(marca, model, year, km)
    groq_part = _groq_verify_sample(autovit, marca, model, year, km)

    now = datetime.now(timezone.utc)
    ts_file = now.strftime("%Y%m%dT%H%M%SZ")
    snapshot: Dict[str, Any] = {
        "schema": "softscore_market_snapshot_v1",
        "timestamp_utc": now.isoformat(),
        "model_key": mkey,
        "vin": v.vin,
        "marca": marca,
        "model": model,
        "an": year,
        "km": km,
        "autovit": autovit,
        "groq_verification": groq_part,
        "cached": False,
    }

    hist_name = f"{mkey}_{ts_file}.json"
    hist_path = HISTORY_DIR / hist_name
    try:
        hist_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        latest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        state = _load_state()
        state[mkey] = {
            "last_utc": now.isoformat(),
            "last_history_file": hist_name,
            "vin_last": v.vin,
        }
        _save_state(state)
    except OSError as e:
        snapshot["write_error"] = str(e)

    return snapshot


def ensure_snapshot_for_dto(v: MulberryVehicleDTO, *, force: bool = False) -> Dict[str, Any]:
    """API clar pentru integrare (SoftScore, job scheduler)."""
    return build_snapshot_for_dto(v, force=force)


def refresh_all_registered_cars(*, force: bool = False) -> Dict[str, Any]:
    """
    Iteră toate mașinile cu VIN din DB; pentru fiecare model (cheie unică marcă+model+an) actualizează snapshot-ul.
    """
    rows = database.get_all_cars_with_vin()
    seen: set[str] = set()
    ok = 0
    err = 0
    errors: list[str] = []
    for row in rows:
        mkey = None
        try:
            car = CarRow(**{k: row[k] for k in row.keys()})
            v = vehicle_dto_from_car_row(car)
            mkey = model_key_from_dto(v)
        except Exception as e:
            err += 1
            errors.append(f"row: {e!s}")
            continue
        if mkey in seen:
            continue
        seen.add(mkey)
        try:
            build_snapshot_for_dto(v, force=force)
            ok += 1
        except Exception as e:
            err += 1
            errors.append(f"{mkey}: {e!s}")
    return {"ok": ok, "errors": err, "error_messages": errors[:20], "unique_models": len(seen)}


def background_snapshot_for_vehicle(user_id: int, vin: str) -> None:
    """Rulează din thread daemon — nu blochează request-ul SoftScore."""
    vin_norm = (vin or "").strip().upper()
    if len(vin_norm) != 17:
        return
    car = database.get_car_by_user_and_vin(user_id, vin_norm)
    if not car:
        return
    try:
        v = vehicle_dto_from_car_row(car)
        build_snapshot_for_dto(v, force=False)
    except Exception:
        pass
