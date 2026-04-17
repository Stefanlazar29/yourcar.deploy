from datetime import datetime, timedelta
import asyncio
import json
import mimetypes
import os
import sqlite3
import time
import re
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

try:
  from dotenv import load_dotenv
  _backend_dir = Path(__file__).resolve().parent
  load_dotenv(_backend_dir / ".env")
  load_dotenv(_backend_dir.parent / ".env")
except ImportError:
  pass

from fastapi import BackgroundTasks, Body, Depends, FastAPI, File, Form, Header, HTTPException, Request, status, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import bcrypt
from pydantic import BaseModel, Field

from backend import database
from backend.models import SyncRequest, SyncResponse, MulberryBrain, CloudFile
from backend.engine import sync_vehicle_brain, process_mulberry_logic
from backend.knowledge import AutoExpertBrain
from backend.brain_engine import (
  check_for_alerts,
  generate_conversation_starter,
  get_conversation_starter_for_user,
  update_market_value,
)
from backend.events import pop_pending_proactive, get_proactive_for_event
from backend.reports import get_latest_report
from backend import vector_store
from backend import debug_logger
from backend import minimax_client
from backend import manual_skoda
from backend import conversation_store
from backend import chat_rag_narrative
from backend import exo_assistant
from backend import daily_insights_service
from backend import valuation_engine
from backend import cloud_manager
from backend import softscore_insight
from backend import profile_narrative as profile_narrative_service
from backend import mlbr_file
from backend import archive_service
from backend import auth_audit
from backend import business_analyze
from backend.vehicle_dto import (
  market_intel_synthesis_row_for_dto,
  vehicle_dto_from_car_row,
  vehicle_dto_from_payload,
)

# Director pentru documente încărcate (Mulberry Cloud)
ROOT_DIR = Path(__file__).resolve().parent.parent
# Upload-uri Mulberry Cloud — în Docker: MULBERRY_UPLOAD_DIR=/data/uploads
UPLOAD_DIR = os.getenv(
  "MULBERRY_UPLOAD_DIR",
  os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads"),
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Instanță globală pentru Lookup Table
expert_brain = AutoExpertBrain()

class ChatAttachmentIn(BaseModel):
  """Metadata + base64 opțional; mesajul efectiv către LLM folosește doar descrieri scurte (fără imagine în model text-only)."""
  name: str = ""
  mime: str = ""
  data_base64: str = ""


class ChatRequest(BaseModel):
  user_id: str
  message: str
  vin: Optional[str] = None
  context: Optional[dict] = None
  thread_id: Optional[str] = None  # sincron cu localStorage conversație (arhivă SQLite)
  attachments: Optional[List[ChatAttachmentIn]] = None

class ManualExcerpt(BaseModel):
  line_from: int
  line_to: int
  text: str


class DigitalTwinAlert(BaseModel):
  kind: str
  title: str
  detail: str


class ChatResponse(BaseModel):
  reply: str
  manual_excerpts: Optional[List[ManualExcerpt]] = None
  digital_twin_alert: Optional[DigitalTwinAlert] = None


class BusinessAnalyzeIn(BaseModel):
  """Analiză flotă / business — LLM cu context vehicul canonic."""

  question: str = Field(..., min_length=3, max_length=8000)
  vehicle: Optional[Dict[str, Any]] = None


class BusinessAnalyzeOut(BaseModel):
  reply: str
  vehicle: Dict[str, Any]
  cached: bool = False
  insight_id: Optional[int] = None


class VehicleInsightLatestOut(BaseModel):
  """Ultimul insight salvat pentru mașina reală din DB (filtrat user + VIN)."""

  latest_id: Optional[int] = None
  within_24h: bool = False
  question: Optional[str] = None
  reply: Optional[str] = None
  preview: Optional[str] = None
  created_at: Optional[str] = None
  score: Optional[float] = None


class SoftScoreLatestOut(BaseModel):
  """SoftScore multi-factor v1 — ultima intrare salvată sau goală."""

  insight_id: Optional[int] = None
  within_24h: bool = False
  softscore: Optional[float] = None
  market_value: Optional[float] = None
  currency: str = "EUR"
  market_base_eur: Optional[float] = None
  base_source: Optional[str] = None
  health_band: Optional[str] = None
  breakdown: Optional[Dict[str, Any]] = None
  reply: Optional[str] = None
  created_at: Optional[str] = None


class SoftScoreRefreshOut(SoftScoreLatestOut):
  """După refresh, insight_id este întotdeauna setat."""

  pass


class ProfileNarrativeOut(BaseModel):
  """Text profil MyMulberry (AI + istoric) — fără listă de funcții app."""

  narrative: str = ""
  updated_at: Optional[str] = None


class DailyInsightCardOut(BaseModel):
  """Card carousel Daily Insights (titlu, link, imagine — articole MulberryEXO în SQLite)."""

  id: Optional[int] = None
  tag: str = "AI INSIGHT"
  title: str
  url: str
  image_url: Optional[str] = None
  kind: str = "article"
  essence: Optional[str] = None
  reading_text: Optional[str] = None
  frame_images: Optional[List[str]] = None


class DailyInsightsOut(BaseModel):
  banner: Optional[str] = None
  cards: List[DailyInsightCardOut] = Field(default_factory=list)
  new_count_hint: int = 0


class DailyInsightsRefreshOut(BaseModel):
  ok: bool = True
  banner: Optional[str] = None
  count: int = 0


class DailyInsightOpinionIn(BaseModel):
  body: str
  card_id: Optional[int] = None
  sort_order: Optional[int] = None


class DailyInsightOpinionItemOut(BaseModel):
  id: int
  body: str
  author_display: str
  created_at: str


class DailyInsightOpinionsOut(BaseModel):
  opinions: List[DailyInsightOpinionItemOut] = Field(default_factory=list)


class DailyInsightPolishIn(BaseModel):
  text: str


class DailyInsightPolishOut(BaseModel):
  polished: str


class MulberryTechnicalReportPayload(BaseModel):
  """Date raport PDF tehnic (structură factură). Fără soft_score — rămâne în app."""

  report_id: str = "MLRB-001"
  report_date: Optional[str] = None
  subject_line: str = "Raport tehnic vehicul"
  vin: str = ""
  plate: str = ""
  mlbr_id: str = ""
  vehicle_label: str = ""
  owner_label: str = ""
  last_insurance: str = ""
  active_insurance: str = ""
  changes_made: str = ""
  last_issues: str = ""
  qr_url: str = ""


# ────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "schimba-ma")
JWT_ALG = "HS256"
JWT_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "43200"))  # 30 zile

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ────────────────────────────────────────────────────────────────
# Schemas
# ────────────────────────────────────────────────────────────────

class LoginIn(BaseModel):
  identifier: str  # email (Parola 1 = parola clasica)
  password: str
  phone_number: Optional[str] = None  # Parola 2 = cod acces secundar (nr. telefon)


class RegisterIn(BaseModel):
  identifier: str  # telefon sau email
  password: str
  phone_number: Optional[str] = None


class TokenOut(BaseModel):
  access_token: str
  token_type: str = "bearer"
  role: str = "user"
  needs_phone: Optional[bool] = None
  last_login_at: Optional[str] = None
  security_alerts: Optional[List[str]] = None


class DeviceApproveIn(BaseModel):
  identifier: str
  password: str
  new_device_id: str


class MeOut(BaseModel):
  id: int
  identifier: str
  role: str = "user"


class CarIn(BaseModel):
  payload: dict


class UserPrefsIn(BaseModel):
  """Preferințe EXO — folosite la următorul ciclu EXO Intelligence (Groq / Ollama)."""
  usage: Optional[str] = "mixed"  # city / highway / mixed
  budget: Optional[str] = "medium"  # low / medium / high
  concerns: Optional[List[str]] = None
  location: Optional[str] = "Romania"


class ExoChatIn(BaseModel):
  message: str
  include_error_log: bool = True


class ExoChatOut(BaseModel):
  reply: str


# ────────────────────────────────────────────────────────────────
# Form submit (fără pop-up / fără Supabase)
# ────────────────────────────────────────────────────────────────

class FormSubmitIn(BaseModel):
  provider: Optional[str] = None
  email: Optional[str] = None
  password: Optional[str] = None
  payload: Optional[dict] = None


class FormSubmitOut(BaseModel):
  ok: bool = True


# ────────────────────────────────────────────────────────────────
# Auth helpers
# ────────────────────────────────────────────────────────────────

def _password_bytes(pw: str) -> bytes:
  """bcrypt acceptă max 72 octeți UTF-8."""
  return (pw or "").encode("utf-8")[:72]


def hash_password(pw: str) -> str:
  if not pw:
    return ""
  # bcrypt direct — evită passlib + bcrypt 4.x (Python 3.12+) care crapă la __about__
  digest = bcrypt.hashpw(_password_bytes(pw), bcrypt.gensalt())
  return digest.decode("ascii")


def verify_password(pw: str, pw_hash: str) -> bool:
  if not pw_hash:
    return not pw
  try:
    return bcrypt.checkpw(_password_bytes(pw), pw_hash.encode("ascii"))
  except Exception:
    return False


def make_token(user_id: int, identifier: str, role: str = "user") -> str:
  exp = datetime.utcnow() + timedelta(minutes=JWT_TTL_MIN)
  payload = {"sub": str(user_id), "identifier": identifier, "role": role, "exp": exp}
  return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _user_from_jwt_token(token: str) -> database.UserRow:
  try:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    uid = int(payload.get("sub", "0"))
  except (JWTError, ValueError):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid.")
  ident = payload.get("identifier") or payload.get("email") or ""
  user = database.get_user_by_identifier(ident)
  if not user or user.id != uid:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizator inexistent.")
  return user


def get_current_user(token: str = Depends(oauth2_scheme)) -> database.UserRow:
  return _user_from_jwt_token(token)


def require_founder(current: database.UserRow = Depends(get_current_user)) -> database.UserRow:
  if (current.role or "").lower() != "founder":
    raise HTTPException(status_code=403, detail="Acces doar pentru Fondator.")
  return current


def _request_ip_and_ua(request: Request) -> tuple[str, str]:
  forwarded = request.headers.get("x-forwarded-for", "") or ""
  ip = forwarded.split(",")[0].strip() if forwarded else ""
  if not ip and request.client and request.client.host:
    ip = str(request.client.host)
  user_agent = request.headers.get("user-agent", "") or ""
  return ip, user_agent


def _mulberry_device_header(request: Request) -> Optional[str]:
  v = request.headers.get("X-Mulberry-Device-Id") or request.headers.get("x-mulberry-device-id")
  s = (v or "").strip()
  return s or None


def _single_device_enabled() -> bool:
  return (os.getenv("MULBERRY_SINGLE_DEVICE") or "").strip().lower() in ("1", "true", "yes")


def _check_device_binding_for_session(user: database.UserRow, request: Request) -> None:
  """Verifică amprenta pentru utilizator autentificat (rute protejate)."""
  if not _single_device_enabled():
    return
  u = database.get_user_by_id(user.id)
  if not u or not u.device_hwid_hash:
    return
  raw = _mulberry_device_header(request)
  if not raw:
    raise HTTPException(
      status_code=403,
      detail="Header X-Mulberry-Device-Id necesar pentru sesiunea acestui cont.",
    )
  if database.hash_device_fingerprint(raw) != u.device_hwid_hash:
    raise HTTPException(
      status_code=403,
      detail="Sesiune suspendată: amprentă dispozitiv nepotrivită. Confirmă prin /auth/device/approve.",
    )


def _enforce_single_device_binding(user: database.UserRow, request: Request) -> None:
  """
  Politică un singur dispozitiv: prima amprentă se salvează; următoarele trebuie să coincidă
  sau utilizatorul folosește POST /auth/device/approve cu parola.
  """
  if not _single_device_enabled():
    return
  u = database.get_user_by_id(user.id)
  if not u:
    return
  raw = _mulberry_device_header(request)
  h = database.hash_device_fingerprint(raw) if raw else None
  if u.device_hwid_hash:
    if not raw:
      raise HTTPException(
        status_code=403,
        detail="Pentru acest cont este activată politica un singur dispozitiv. Trimite header-ul X-Mulberry-Device-Id.",
      )
    if h != u.device_hwid_hash:
      raise HTTPException(
        status_code=403,
        detail="Amprentă dispozitiv diferită de cea înregistrată. Confirmă noul dispozitiv prin POST /auth/device/approve cu parola contului.",
      )
  elif raw and h:
    database.set_user_device_hwid(user.id, h)


def require_device_fingerprint(
  request: Request,
  current: database.UserRow = Depends(get_current_user),
) -> database.UserRow:
  _check_device_binding_for_session(current, request)
  return current


def get_current_user_optional(
  authorization: Optional[str] = Header(None),
) -> Optional[database.UserRow]:
  """Returnează user-ul dacă token valid; altfel None (nu ridică eroare)."""
  if not authorization or not authorization.startswith("Bearer "):
    return None
  token = authorization[7:].strip()
  if not token:
    return None
  try:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    uid = int(payload.get("sub", "0"))
  except (JWTError, ValueError):
    return None
  ident = payload.get("identifier") or payload.get("email") or ""
  user = database.get_user_by_identifier(ident)
  if not user or user.id != uid:
    return None
  return user


def optional_device_fingerprint(
  request: Request,
  current: Optional[database.UserRow] = Depends(get_current_user_optional),
) -> Optional[database.UserRow]:
  if current is None:
    return None
  _check_device_binding_for_session(current, request)
  return current


# ────────────────────────────────────────────────────────────────
# App — mai întâi FastAPI, apoi middleware (CORS)
# ────────────────────────────────────────────────────────────────

app = FastAPI(title="Mulberry API", version="1.2")

# CORS: dev local + producție Mulberry/Vercel + supliment din MULBERRY_CORS_ORIGINS
def _resolve_cors_origins() -> List[str]:
  base = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:9000",
    "http://localhost:9000",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "https://127.0.0.1:9000",
    "https://localhost:9000",
    "https://mulberry.autos",
    "https://www.mulberry.autos",
    # Preview Vercel (înlocuiește cu URL-ul din tab-ul tău Deployments dacă e altul)
    "https://project-4gy67.vercel.app",
    "null",  # file:// (unele browsere trimit Origin: null)
  ]
  # Alte origini (ex. alt preview *.vercel.app): MULBERRY_CORS_ORIGINS=https://foo.vercel.app,https://bar.vercel.app
  extra = (os.getenv("MULBERRY_CORS_ORIGINS") or "").strip()
  if extra:
    for part in extra.split(","):
      o = part.strip().rstrip("/")
      if o and o not in base:
        base.append(o)
  return base


_CORS_ORIGINS = _resolve_cors_origins()

app.add_middleware(
  CORSMiddleware,
  allow_origins=_CORS_ORIGINS,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
  # SQLite: tabele + migrații în database.init_db() — echivalent practic cu
  # SQLAlchemy Base.metadata.create_all(bind=engine), fără ORM duplicat în proiect.
  database.init_db()
  auth_audit.init_auth_audit_db()
  try:
    if (os.getenv("SKIP_AP_SCHEDULER") or "").strip().lower() in ("1", "true", "yes", "on"):
      print("[Startup] SKIP_AP_SCHEDULER=1 — fără APScheduler (ex. Vercel serverless).")
    else:
      from backend.scheduler import start_scheduler
      start_scheduler()
  except Exception as e:
    print(f"[Startup] Scheduler eșuat: {e}")


@app.get("/health")
def health():
  return {"ok": True}


@app.get("/api/health")
def api_health():
  """Deep health: verifică șițeava către Postgres (Supabase) sau SQLite local."""
  try:
    con = database.connect()
    try:
      cur = con.execute("SELECT 1 AS health_check")
      row = cur.fetchone()
      if row is None:
        raise RuntimeError("SELECT 1 returned no row")
    finally:
      con.close()
  except Exception as e:
    return JSONResponse(
      status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
      content={
        "status": "degraded",
        "database": "error",
        "details": str(e)[:800],
      },
    )
  db_kind = "postgresql" if (os.getenv("DATABASE_URL") or "").strip() else "sqlite"
  return {
    "status": "healthy",
    "database": "connected",
    "backend": db_kind,
  }


@app.get("/labels/kanban-pervasive-sample.pdf")
def kanban_pervasive_sample_pdf():
  """PDF etichetă Kanban/e-ink (template PERVASIVE DISPLAY) — structură fixă, date exemplu."""
  from backend import kanban_label_pdf

  body = kanban_label_pdf.build_kanban_label_pdf()
  return Response(
    content=body,
    media_type="application/pdf",
    headers={"Content-Disposition": 'inline; filename="kanban-pervasive-sample.pdf"'},
  )


@app.get("/reports/mulberry-technical-sample.pdf")
def mulberry_technical_sample_pdf():
  """PDF tehnic A4 (factură) — exemplu cu date implicite; fără soft_score."""
  from backend import mulberry_report_pdf

  body = mulberry_report_pdf.build_mulberry_technical_invoice_pdf()
  return Response(
    content=body,
    media_type="application/pdf",
    headers={"Content-Disposition": 'inline; filename="mulberry-technical-sample.pdf"'},
  )


@app.post("/reports/mulberry-technical.pdf")
def mulberry_technical_pdf(body: MulberryTechnicalReportPayload):
  """Generează raportul tehnic Mulberry (JSON → PDF)."""
  from backend.mulberry_report_pdf import MulberryTechnicalReportData, build_mulberry_technical_invoice_pdf

  d = MulberryTechnicalReportData(**body.model_dump())
  out = build_mulberry_technical_invoice_pdf(d)
  return Response(
    content=out,
    media_type="application/pdf",
    headers={"Content-Disposition": 'attachment; filename="mulberry-technical-report.pdf"'},
  )


@app.get("/fleet/stats")
def fleet_stats():
  """Statistici flotă (număr vehicule în `cars`) — fără date personale."""
  return {
    "total_vehicles": database.count_cars(),
    "last_update": datetime.utcnow().isoformat(timespec="seconds") + "Z",
  }


@app.get("/system/archives")
def system_archives_list(_: database.UserRow = Depends(require_founder)):
  """Listă fișiere JSON din research_data/archives/ (Fondator)."""
  root = archive_service.ARCHIVES_ROOT.resolve()
  files: List[Dict[str, Any]] = []
  if root.is_dir():
    for p in sorted(root.rglob("*.json")):
      try:
        st = p.stat()
        rel = p.relative_to(root)
        files.append(
          {
            "name": p.name,
            "rel_path": str(rel).replace("\\", "/"),
            "size_bytes": st.st_size,
            "mtime": st.st_mtime,
          }
        )
      except OSError:
        continue
  return {"files": files, "notice": archive_service.read_last_notice()}


@app.get("/system/archives/status")
def system_archives_status(_: database.UserRow = Depends(require_founder)):
  return archive_service.read_last_notice() or {}


@app.post("/system/archives/generate")
def system_archives_generate(_: database.UserRow = Depends(require_founder)):
  """Generează arhiva zilnică la cerere (altfel rulează din scheduler)."""
  return archive_service.generate_daily_archive()


@app.get("/system/archives/download/{rel_path:path}")
def system_archives_download(rel_path: str, _: database.UserRow = Depends(require_founder)):
  root = archive_service.ARCHIVES_ROOT.resolve()
  target = (root / rel_path).resolve()
  if not str(target).startswith(str(root)) or not target.is_file():
    raise HTTPException(status_code=404, detail="Fișier inexistent.")
  return FileResponse(target, media_type="application/json", filename=target.name)


class LogErrorIn(BaseModel):
  message: str = ""
  status: Optional[int] = None
  url: Optional[str] = None
  detail: Optional[str] = None


@app.post("/log-error")
def log_error_endpoint(inp: LogErrorIn):
  debug_logger.log_error(
    message=inp.message or "",
    status=inp.status,
    url=inp.url,
    detail=inp.detail,
  )
  return {"ok": True}


@app.post("/chat", response_model=ExoChatOut)
def exo_chat(inp: ExoChatIn, current: database.UserRow = Depends(require_device_fingerprint)):
  """
  Chat MulberryExoTerra prin AIProxy (Groq + fallback Ollama). Necesită JWT (Bearer).
  """
  if not (inp.message or "").strip():
    raise HTTPException(status_code=400, detail="Mesaj gol.")
  extra_parts = []
  agent_id = os.getenv("AGENT_ID", "MulberryEXO")
  extra_parts.append(f"Agent ID configurat: {agent_id}")
  try:
    car = database.get_car_for_user(current.id)
    if car:
      extra_parts.append(
        f"Vehicul înregistrat: {car.make or '—'} {car.model or '—'} an {car.year or '—'}, "
        f"VIN {car.vin or '—'}, nr. {car.plate or '—'}"
      )
    else:
      extra_parts.append("Nu există încă vehicul salvat în baza de date pentru acest cont.")
  except Exception as e:
    extra_parts.append(f"Eroare citire vehicul: {e}")
  if inp.include_error_log:
    try:
      lines = debug_logger.read_recent_errors(40)
      if lines:
        extra_parts.append("Ultimele erori (errors.log):\n" + "".join(lines)[-6000:])
    except Exception:
      pass
  try:
    man = manual_skoda.analyze_user_message(inp.message)
    if man.excerpts:
      extra_parts.append(
        "Extras din manual Skoda Fabia 6Y (fișier local):\n"
        + "\n".join(f"[L{e['line_from']}-{e['line_to']}] {e['text']}" for e in man.excerpts)
      )
  except Exception:
    pass
  context = "\n".join(extra_parts)
  try:
    reply = minimax_client.call_minimax(inp.message.strip(), context)
    return ExoChatOut(reply=reply)
  except RuntimeError as e:
    raise HTTPException(status_code=503, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Chat EXO: {e}")


@app.get("/debug/status")
def debug_status():
  """Diagnostic: utilizatori și mașini din DB (pentru debugging)."""
  try:
    con = database.connect()
    users = con.execute("SELECT id, identifier, email, role FROM users").fetchall()
    cars = con.execute("SELECT id, user_id, make, model, vin, plate FROM cars").fetchall()
    con.close()
    return {
      "users": [dict(r) for r in users],
      "cars": [dict(r) for r in cars],
      "summary": {"users_count": len(users), "cars_count": len(cars)},
    }
  except Exception as e:
    return {"error": str(e), "users": [], "cars": []}


# ────────────────────────────────────────────────────────────────
# EXO-Observer: Insights + Health (pentru meniul Hub)
# ────────────────────────────────────────────────────────────────

@app.get("/exo/insights")
def exo_insights(vin: str, limit: int = 5):
  """Ultimele descoperiri EXO pentru vehicul (Research Feed)."""
  if not vin or not vin.strip():
    return {"insights": []}
  vin_norm = vin.strip().upper()
  items = database.get_exo_insights(vin_norm, limit=max(1, min(limit, 20)))
  return {"insights": items}


@app.get("/exo/status")
def exo_status():
  """Stare ultim ciclu EXO Intelligence (scheduler + interval)."""
  st = database.get_exo_scheduler_state()
  interval_min = 10
  next_eta_sec = None
  last = st.get("last_cycle_at") if st else None
  if last:
    try:
      t = datetime.fromisoformat(str(last).replace("Z", ""))
      elapsed = (datetime.utcnow() - t).total_seconds()
      next_eta_sec = max(0.0, interval_min * 60 - elapsed)
    except Exception:
      next_eta_sec = None
  return {
    "scheduler": st or {},
    "interval_minutes": interval_min,
    "next_cycle_in_sec_approx": next_eta_sec,
  }


@app.post("/exo/run")
def exo_run_intelligence(current: database.UserRow = Depends(get_current_user)):
  """Declanșează manual ciclul EXO Intelligence (Groq / Ollama → SQLite)."""
  try:
    from backend.exo_engine import run_exo_cycle
    return run_exo_cycle()
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


@app.post("/exo/run-now")
def exo_run_now_alias(current: database.UserRow = Depends(get_current_user)):
  """Alias pentru clienti care așteaptă /exo/run-now."""
  from backend.exo_engine import run_exo_cycle
  return run_exo_cycle()


@app.post("/exo/run-legacy")
def exo_run_legacy_ollama(current: database.UserRow = Depends(get_current_user)):
  """
  DEPRECATED — fluxul Ollama nu mai e suportat ca rută activă.
  Folosește POST /exo/run sau POST /exo/run-now (EXO Intelligence) și POST /research/run-now (crawler).
  """
  return {
    "deprecated": True,
    "use": ["/exo/run", "/exo/run-now", "/research/run-now"],
    "message": "Endpoint păstrat pentru compatibilitate; nu rulează Ollama.",
  }


@app.get("/exo/stream")
async def exo_event_stream(
  vin: str,
  authorization: Optional[str] = Header(None),
):
  """
  SSE: insight-uri + stare scheduler la ~20s.
  Autentificare doar prin header Authorization: Bearer <JWT> (fără token în URL).
  Frontend: fetch() + ReadableStream (vezi mulberry_exo_menu.js).
  """
  raw = ""
  if authorization and authorization.startswith("Bearer "):
    raw = authorization[7:].strip()
  if not raw:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Lipsește Authorization: Bearer <token>.",
    )
  user = _user_from_jwt_token(raw)
  vin_norm = (vin or "").strip().upper()
  car = database.get_car_for_user(user.id)
  if not car or (car.vin or "").strip().upper() != vin_norm:
    raise HTTPException(status_code=403, detail="VIN inexistent sau nu aparține contului.")

  async def gen():
    while True:
      st = database.get_exo_scheduler_state()
      items = database.get_exo_insights(vin_norm, limit=25)
      payload = {"scheduler": st or {}, "insights": items}
      yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
      await asyncio.sleep(20)

  return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/exo/health")
def exo_health(vin: str):
  """
  Verifică dacă Ochiul a validat integritatea datelor în ultimele 24h.
  Mulberry ID Health: bifă verde dacă within_24h și ok.
  """
  if not vin or not vin.strip():
    return {"ok": False, "within_24h": False, "checked_at": None}
  vin_norm = vin.strip().upper()
  h = database.get_exo_health(vin_norm)
  if not h:
    return {"ok": False, "within_24h": False, "checked_at": None}
  try:
    checked = datetime.fromisoformat(h["checked_at"].replace("Z", ""))
    now = datetime.utcnow()
    delta = now - checked
    within_24h = delta.total_seconds() < 86400
  except Exception:
    within_24h = False
  return {
    "ok": h["ok"] and within_24h,
    "within_24h": within_24h,
    "checked_at": h["checked_at"],
  }


# ────────────────────────────────────────────────────────────────
# EXO Research Engine — surse externe, SQLite research_data + snapshot JSON
# ────────────────────────────────────────────────────────────────


@app.get("/research/insights")
def research_insights(
  make: str = "",
  model: str = "",
  year: Optional[int] = None,
  limit: int = 10,
):
  """Insights din research extern (RSS/scrape) pentru un model."""
  from backend.exo_research_engine import get_insights_for_vehicle

  return {"insights": get_insights_for_vehicle(make, model, year, limit)}


@app.get("/research/fuel")
def research_fuel():
  """Ultimele prețuri combustibil salvate (RON)."""
  from backend.exo_research_engine import get_latest_fuel_prices

  return {"prices": get_latest_fuel_prices()}


@app.post("/research/run-now")
def research_run_now(current: database.UserRow = Depends(get_current_user)):
  """Declanșează manual un ciclu EXO Research (crawler + clasificare LLM)."""
  from backend.exo_research_engine import run_research_cycle

  return run_research_cycle()


@app.get("/research/status")
def research_status():
  """Contoare DB research + ultim research."""
  from backend.exo_research_engine import get_research_status_counts

  return get_research_status_counts()


# ────────────────────────────────────────────────────────────────
# WebSocket — Notificări proactive (Mulberry Brain)
# ────────────────────────────────────────────────────────────────

CHECK_INTERVAL_SEC = 60

@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: str):
  """
  Conexiune persistentă pentru notificări proactive.
  Verifică alertele (ITP, RCA, SoftScore) periodic și trimite mesaj când există.
  """
  await websocket.accept()
  last_sent = {}  # evităm spam: { code: timestamp }
  try:
    while True:
      # 1. Verifică notificări proactive din evenimente (raport lunar, drum lung, etc.)
      notification = pop_pending_proactive(user_id)
      # 2. Dacă nu, verifică alerte (ITP, RCA, SoftScore)
      if not notification:
        notification = check_for_alerts(user_id)
      if notification:
        code = notification.get("code", "")
        now = time.time()
        last = last_sent.get(code, 0)
        if now - last > 300:  # max 1 notificare per cod la 5 min
          try:
            await websocket.send_json(notification)
            last_sent[code] = now
          except Exception:
            break
      await asyncio.sleep(CHECK_INTERVAL_SEC)
  except Exception:
    pass
  try:
    await websocket.close()
  except Exception:
    pass


class DriveEventIn(BaseModel):
  user_id: str
  vin: Optional[str] = None
  avg_speed_kmh: float = 0
  duration_min: float = 0
  hour_of_day: Optional[int] = None

class BrakingEventIn(BaseModel):
  user_id: str
  vin: Optional[str] = None
  count: int = 0

@app.post("/events/drive")
def event_drive(inp: DriveEventIn):
  """
  Înregistrează un drum (OBD/GPS).
  Regulă: viteză > 80 km/h ȘI durată > 2h ȘI ora >= 20 → notificare "Drum lung încheiat".
  """
  from backend.events import record_drive_event, push_proactive_for_user
  hour = inp.hour_of_day if inp.hour_of_day is not None else datetime.utcnow().hour
  notif = record_drive_event(inp.user_id, inp.vin, inp.avg_speed_kmh, inp.duration_min, hour)
  if notif:
    push_proactive_for_user(inp.user_id, notif)
    return {"triggered": True, "notification": notif}
  return {"triggered": False}


@app.post("/events/braking")
def event_braking(inp: BrakingEventIn):
  """Înregistrează frânări agresive. Dacă count >= 5, declanșează notificare."""
  from backend.events import record_aggressive_braking, push_proactive_for_user
  notif = record_aggressive_braking(inp.user_id, inp.vin, inp.count)
  if notif:
    push_proactive_for_user(inp.user_id, notif)
    return {"triggered": True, "notification": notif}
  return {"triggered": False}


@app.get("/reports/latest")
def reports_latest(current: database.UserRow = Depends(get_current_user)):
  """Returnează ultimul raport lunar pentru user."""
  r = get_latest_report(current.id)
  if not r:
    raise HTTPException(status_code=404, detail="Nu există raport generat.")
  return r


@app.post("/ingest")
def ingest_resources():
  """
  Declanșează manual ingestion din resources/ în ChromaDB.
  În producție rulează automat la 02:00 prin APScheduler.
  """
  result = vector_store.ingest_from_resources()
  return {"added": result["added"], "files": result["files"]}


@app.get("/vector/status")
def vector_status():
  """Status ChromaDB: număr documente în baza vectorială."""
  n = vector_store.count()
  return {"documents": n, "ready": n > 0}


@app.get("/brain/starter")
def brain_conversation_starter(user_id: str, temperature: Optional[float] = None, location: Optional[str] = None):
  """
  Generează un subiect de conversație auto contextual (pattern matching).
  Parametri: user_id, temperature (opțional), location (opțional).
  """
  ext = {"month": datetime.utcnow().month}
  if temperature is not None:
    ext["temperature"] = temperature
  if location:
    ext["location"] = location
  starter = get_conversation_starter_for_user(user_id, ext)
  return {"starter": starter or "Verificare generală a vehiculului."}


@app.post("/form/submit", response_model=FormSubmitOut)
def form_submit(inp: FormSubmitIn):
  # Endpoint simplu: primește date din formularul din HTML.
  # Tu decizi ulterior cum validezi și cum salvezi în PostgreSQL.
  print("[YourCar] /form/submit:", inp.model_dump())
  return FormSubmitOut(ok=True)


@app.post("/auth/login", response_model=TokenOut)
def login(inp: LoginIn, request: Request):
  """
  Login dublu: Parola 1 (email + parolă) + Parola 2 (nr. telefon).
  Dacă userul are phone în DB și nu a furnizat phone_number → needs_phone=True.
  Dacă phone_number e greșit → 401.
  """
  ident = database.normalize_identifier(inp.identifier)
  ip_addr, user_agent = _request_ip_and_ua(request)
  user = database.get_user_by_identifier(ident)
  if not user:
    auth_audit.log_auth_attempt(
      identifier=ident,
      status="FAILED_NO_USER",
      user_id=None,
      ip_address=ip_addr,
      user_agent=user_agent,
      path=str(request.url.path),
    )
    raise HTTPException(status_code=401, detail="Utilizator inexistent.")
  if not verify_password(inp.password, user.password_hash):
    auth_audit.log_auth_attempt(
      identifier=ident,
      status="FAILED_INVALID_PASS",
      user_id=user.id,
      ip_address=ip_addr,
      user_agent=user_agent,
      path=str(request.url.path),
    )
    raise HTTPException(status_code=401, detail="Email sau parolă incorectă.")

  # Parola 2: nr. telefon (cod acces secundar)
  user_phone_norm = database.normalize_phone(user.phone or "")
  if user_phone_norm:
    if not inp.phone_number or not inp.phone_number.strip():
      auth_audit.log_auth_attempt(
        identifier=ident,
        status="NEEDS_PHONE",
        user_id=user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        path=str(request.url.path),
      )
      return TokenOut(
        access_token="",
        needs_phone=True,
        role=user.role or "user",
        last_login_at=None,
        security_alerts=[],
      )
    input_phone_norm = database.normalize_phone(inp.phone_number)
    if input_phone_norm != user_phone_norm:
      auth_audit.log_auth_attempt(
        identifier=ident,
        status="FAILED_INVALID_PASS",
        user_id=user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        path=str(request.url.path),
      )
      raise HTTPException(status_code=401, detail="Cod acces secundar incorect. Verifică numărul de telefon.")

  _enforce_single_device_binding(user, request)

  snapshot = auth_audit.get_security_snapshot(user.id, ip_addr)
  session_hash = auth_audit.make_session_hash(ident, ip_addr, user_agent)
  auth_audit.log_auth_attempt(
    identifier=ident,
    status="SUCCESS",
    user_id=user.id,
    ip_address=ip_addr,
    user_agent=user_agent,
    path=str(request.url.path),
    session_hash=session_hash,
  )
  token = make_token(user.id, user.identifier, user.role or "user")
  return TokenOut(
    access_token=token,
    role=user.role or "user",
    last_login_at=snapshot.last_login_at,
    security_alerts=snapshot.security_alerts,
  )


@app.post("/auth/register", response_model=TokenOut)
def register(inp: RegisterIn, request: Request):
  ident = database.normalize_identifier(inp.identifier)
  if not ident:
    raise HTTPException(status_code=400, detail="Telefon/Email invalid.")
  if not inp.password or len(inp.password) < 8:
    raise HTTPException(status_code=400, detail="Parola trebuie să aibă minim 8 caractere.")
  existing = database.get_user_by_identifier(ident)
  if existing:
    raise HTTPException(status_code=409, detail="Utilizatorul există deja.")
  try:
    pw_hash = hash_password(inp.password)
    phone_val = (inp.phone_number or "").strip() or None
    user = database.create_user(ident, pw_hash, phone=phone_val)
  except Exception as e:
    print(f"[Register] Eroare 500: {e}\n{traceback.format_exc()}")
    raise HTTPException(
      status_code=500,
      detail="Eroare server la înregistrare. Vezi traceback în terminal. Dacă e DB: rulează .\\reset_db.ps1 și repornește uvicorn.",
    ) from e
  raw_dev = _mulberry_device_header(request)
  if raw_dev:
    database.set_user_device_hwid(user.id, database.hash_device_fingerprint(raw_dev))
  token = make_token(user.id, user.identifier, user.role or "user")
  return TokenOut(access_token=token, role=user.role or "user")


@app.post("/auth/device/approve", response_model=TokenOut)
def device_approve(inp: DeviceApproveIn, request: Request):
  """
  Confirmare manuală: înregistrează un nou X-Mulberry-Device-Id după verificarea parolei.
  """
  ident = database.normalize_identifier(inp.identifier)
  user = database.get_user_by_identifier(ident)
  if not user:
    raise HTTPException(status_code=404, detail="Utilizator inexistent.")
  if not verify_password(inp.password, user.password_hash):
    raise HTTPException(status_code=401, detail="Parolă incorectă.")
  new_id = (inp.new_device_id or "").strip()
  if len(new_id) < 8:
    raise HTTPException(status_code=400, detail="new_device_id invalid (minim 8 caractere).")
  database.set_user_device_hwid(user.id, database.hash_device_fingerprint(new_id))
  ip_addr, user_agent = _request_ip_and_ua(request)
  auth_audit.log_auth_attempt(
    identifier=ident,
    status="DEVICE_APPROVED",
    user_id=user.id,
    ip_address=ip_addr,
    user_agent=user_agent,
    path=str(request.url.path),
  )
  token = make_token(user.id, user.identifier, user.role or "user")
  return TokenOut(access_token=token, role=user.role or "user")


@app.get("/auth/session-probe")
def auth_session_probe(request: Request, current: database.UserRow = Depends(get_current_user)):
  """
  Verificare silențioasă HWID pentru client (ex. deschidere chat).
  403 dacă MULBERRY_SINGLE_DEVICE=1 și X-Mulberry-Device-Id nu corespunde.
  """
  _check_device_binding_for_session(current, request)
  return {"ok": True}


@app.post("/auth/client-tab-close")
def auth_client_tab_close(
  request: Request,
  current: Optional[database.UserRow] = Depends(get_current_user_optional),
):
  """
  Semnal best-effort la închiderea tab-ului (navigator.sendBeacon / fetch keepalive).
  Nu cere corp cu token — folosește Authorization: Bearer. Fără verificare HWID (doar audit).
  """
  if current is None:
    return {"ok": True, "logged": False}
  ip_addr, user_agent = _request_ip_and_ua(request)
  auth_audit.log_auth_attempt(
    identifier=current.identifier,
    status="TAB_CLOSE",
    user_id=current.id,
    ip_address=ip_addr,
    user_agent=user_agent,
    path=str(request.url.path),
  )
  return {"ok": True, "logged": True}


@app.get("/me", response_model=MeOut)
def me(current: database.UserRow = Depends(get_current_user)):
  return MeOut(id=current.id, identifier=current.identifier, role=current.role or "user")


@app.get("/me/vehicle", response_model=Dict[str, Any])
def me_vehicle_canonical(current: database.UserRow = Depends(get_current_user)):
  """
  Vehiculul utilizatorului în format canonic MulberryVehicleDTO (contract unic API).
  Orice câmp care nu trece validarea (ex. VIN) → 422.
  """
  car = database.get_car_for_user(current.id)
  if not car:
    raise HTTPException(status_code=404, detail="Niciun vehicul înregistrat.")
  try:
    dto = vehicle_dto_from_car_row(car)
  except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e)) from e
  return dto.model_dump(mode="json")


@app.post("/analyze/business", response_model=BusinessAnalyzeOut)
def analyze_business(inp: BusinessAnalyzeIn, current: database.UserRow = Depends(get_current_user)):
  """
  Consultant flotă (Groq/Ollama prin AIProxy): contextul analizei este ÎNTOTDEAUNA vehiculul
  înregistrat în SQLite pentru user. Dacă trimiți `vehicle` în body, VIN-ul trebuie să coincidă
  cu mașina reală (altfel 403). Cache 24h per (user, VIN, întrebare normalizată) — fără apel Groq.
  """
  car = database.get_car_for_user(current.id)
  if not car:
    raise HTTPException(
      status_code=404,
      detail="Niciun vehicul în DB. Înregistrează vehiculul înainte de analiză business.",
    )
  try:
    v = vehicle_dto_from_car_row(car)
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e

  if inp.vehicle is not None and len(inp.vehicle) > 0:
    try:
      v_body = vehicle_dto_from_payload(inp.vehicle)
    except ValueError as e:
      raise HTTPException(status_code=400, detail=str(e)) from e
    if v_body.vin != v.vin:
      raise HTTPException(
        status_code=403,
        detail="VIN-ul din body nu coincide cu vehiculul înregistrat pentru acest cont.",
      )

  cached = database.vehicle_insight_get_cached(current.id, v.vin, inp.question, hours=24)
  if cached:
    return BusinessAnalyzeOut(
      reply=cached["reply"],
      vehicle=v.model_dump(mode="json"),
      cached=True,
      insight_id=cached["id"],
    )

  try:
    reply = business_analyze.run_business_analysis(v, inp.question)
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e
  except RuntimeError as e:
    raise HTTPException(status_code=503, detail=str(e)) from e

  aid = database.vehicle_insight_insert(
    current.id,
    v.vin,
    inp.question,
    {"reply": reply, "vehicle": v.model_dump(mode="json")},
    score=v.ycs_score,
  )
  return BusinessAnalyzeOut(
    reply=reply,
    vehicle=v.model_dump(mode="json"),
    cached=False,
    insight_id=aid,
  )


@app.get("/me/vehicle/insights/latest", response_model=VehicleInsightLatestOut)
def me_vehicle_insight_latest(current: database.UserRow = Depends(get_current_user)):
  """Hub: ultimul insight pentru mașina curentă (siguranță: doar rânduri user + VIN din get_car_for_user)."""
  car = database.get_car_for_user(current.id)
  if not car:
    return VehicleInsightLatestOut()
  try:
    dto_vin = vehicle_dto_from_car_row(car).vin
  except ValueError:
    return VehicleInsightLatestOut()
  row = database.vehicle_insight_latest_for_vehicle(current.id, dto_vin)
  if not row:
    return VehicleInsightLatestOut()
  return VehicleInsightLatestOut(
    latest_id=row["id"],
    within_24h=row["within_24h"],
    question=row["question"],
    reply=row["reply"],
    preview=row.get("preview"),
    created_at=row["created_at"],
    score=row["score"],
  )


@app.get("/me/daily-insights", response_model=DailyInsightsOut)
def me_daily_insights(current: database.UserRow = Depends(get_current_user)):
  """Carduri Daily Insights (SQLite, articole MulberryEXO); prima încărcare poate popula dacă lipsește."""
  data = daily_insights_service.build_insights_response_for_user(current.id)
  return DailyInsightsOut(**data)


@app.post("/me/daily-insights/refresh", response_model=DailyInsightsRefreshOut)
def me_daily_insights_refresh(current: database.UserRow = Depends(get_current_user)):
  """Regenerează cardurile pentru VIN-ul curent (test / forțare)."""
  car = database.get_car_for_user(current.id)
  if not car or not (car.vin or "").strip():
    raise HTTPException(status_code=400, detail="Nicio mașină cu VIN înregistrată.")
  banner, n = daily_insights_service.refresh_daily_insights_for_vin(car.vin.strip().upper(), current.id)
  return DailyInsightsRefreshOut(ok=True, banner=banner or None, count=n)


def _me_display_name(user: database.UserRow) -> str:
  em = (user.email or "").strip()
  if em and "@" in em:
    return em.split("@")[0][:32]
  return (user.identifier or "utilizator")[:32]


@app.post("/me/daily-insights/polish-text", response_model=DailyInsightPolishOut)
def me_daily_insights_polish_text(inp: DailyInsightPolishIn, current: database.UserRow = Depends(get_current_user)):
  """Corectare / optimizare limbaj pentru texte (opinii) — MulberryEXO."""
  _ = current
  return DailyInsightPolishOut(polished=daily_insights_service.polish_opinion_text(inp.text))


@app.get("/me/daily-insights/opinions", response_model=DailyInsightOpinionsOut)
def me_daily_insights_opinions_list(
  card_id: Optional[int] = None,
  sort_order: Optional[int] = None,
  current: database.UserRow = Depends(get_current_user),
):
  car = database.get_car_for_user(current.id)
  if not car or not (car.vin or "").strip():
    raise HTTPException(status_code=400, detail="Necesită vehicul cu VIN în profil.")
  vin = car.vin.strip().upper()
  cid = card_id
  if cid is None and sort_order is not None:
    resolved = database.get_daily_insight_card_id_by_vin_sort(vin, int(sort_order))
    if not resolved:
      raise HTTPException(status_code=404, detail="Nu există card Daily Insight pentru acest index.")
    cid = resolved
  if cid is None:
    raise HTTPException(status_code=400, detail="Trimite card_id sau sort_order.")
  if not database.daily_insight_card_belongs_to_vin(int(cid), vin):
    raise HTTPException(status_code=404, detail="Card inexistent pentru vehiculul tău.")
  rows = database.list_daily_insight_opinions_for_card(int(cid))
  return DailyInsightOpinionsOut(opinions=[DailyInsightOpinionItemOut(**r) for r in rows])


@app.post("/me/daily-insights/opinions", response_model=DailyInsightOpinionItemOut)
def me_daily_insights_opinions_post(
  inp: DailyInsightOpinionIn,
  current: database.UserRow = Depends(get_current_user),
):
  car = database.get_car_for_user(current.id)
  if not car or not (car.vin or "").strip():
    raise HTTPException(status_code=400, detail="Necesită vehicul cu VIN în profil.")
  vin = car.vin.strip().upper()
  body = (inp.body or "").strip()
  if len(body) < 2:
    raise HTTPException(status_code=400, detail="Scrie cel puțin câteva caractere.")
  if len(body) > 8000:
    raise HTTPException(status_code=400, detail="Text prea lung.")

  cid = inp.card_id
  if cid is None and inp.sort_order is not None:
    cid = database.get_daily_insight_card_id_by_vin_sort(vin, int(inp.sort_order))
  if cid is None:
    raise HTTPException(status_code=400, detail="Lipsește card_id sau sort_order valid.")
  if not database.daily_insight_card_belongs_to_vin(int(cid), vin):
    raise HTTPException(status_code=404, detail="Card inexistent pentru vehiculul tău.")

  oid, created_at = database.insert_daily_insight_opinion(current.id, int(cid), body)
  return DailyInsightOpinionItemOut(
    id=oid,
    body=body,
    author_display=_me_display_name(current),
    created_at=created_at,
  )


def _softscore_row_to_out(row: dict) -> SoftScoreLatestOut:
  try:
    payload = json.loads(row.get("analysis_json") or "{}")
  except json.JSONDecodeError:
    payload = {}
  return SoftScoreLatestOut(
    insight_id=int(row["id"]),
    within_24h=bool(row.get("within_24h", False)),
    softscore=payload.get("softscore"),
    market_value=payload.get("market_value"),
    currency=str(payload.get("currency") or "EUR"),
    market_base_eur=payload.get("market_base_eur"),
    base_source=payload.get("base_source"),
    health_band=payload.get("health_band"),
    breakdown=payload.get("breakdown"),
    reply=(payload.get("reply") or row.get("reply") or "").strip() or None,
    created_at=row.get("created_at"),
  )


@app.get("/me/vehicle/softscore/latest", response_model=SoftScoreLatestOut)
def me_vehicle_softscore_latest(current: database.UserRow = Depends(get_current_user)):
  car = database.get_car_for_user(current.id)
  if not car:
    return SoftScoreLatestOut()
  try:
    dto_vin = vehicle_dto_from_car_row(car).vin
  except ValueError:
    return SoftScoreLatestOut()
  row = database.vehicle_insight_latest_for_question(
    current.id,
    dto_vin,
    valuation_engine.SOFTSCORE_INSIGHT_QUESTION_V1,
  )
  if not row:
    return SoftScoreLatestOut()
  return _softscore_row_to_out(row)


@app.post("/me/vehicle/softscore/refresh", response_model=SoftScoreRefreshOut)
def me_vehicle_softscore_refresh(current: database.UserRow = Depends(get_current_user)):
  car = database.get_car_for_user(current.id)
  if not car:
    raise HTTPException(status_code=400, detail="Nicio mașină înregistrată.")
  try:
    dto_vin = vehicle_dto_from_car_row(car).vin
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e

  aid = softscore_insight.persist_multifactor_insight_for_vehicle(current.id, dto_vin)
  if aid is None:
    raise HTTPException(status_code=400, detail="Nu s-a putut salva SoftScore pentru acest profil.")
  fresh = database.vehicle_insight_latest_for_question(
    current.id,
    dto_vin,
    valuation_engine.SOFTSCORE_INSIGHT_QUESTION_V1,
  )
  if not fresh:
    got = database.vehicle_insight_get_by_id(current.id, aid, dto_vin)
    if not got:
      raise HTTPException(status_code=500, detail="Insight salvat dar nu a putut fi citit.")
    pl = got.get("analysis") or {}
    return SoftScoreRefreshOut(
      insight_id=aid,
      within_24h=True,
      softscore=pl.get("softscore"),
      market_value=pl.get("market_value"),
      currency=str(pl.get("currency") or "EUR"),
      market_base_eur=pl.get("market_base_eur"),
      base_source=pl.get("base_source"),
      health_band=pl.get("health_band"),
      breakdown=pl.get("breakdown"),
      reply=pl.get("reply") or got.get("reply"),
      created_at=got.get("created_at"),
    )
  out = _softscore_row_to_out(fresh)
  out.insight_id = aid
  return SoftScoreRefreshOut(**out.model_dump())


@app.get("/me/vehicles")
def me_vehicles(current: database.UserRow = Depends(get_current_user)):
  """Returnează vehiculele userului (pentru redirect: founder → dash, user fără mașină → onboarding)."""
  car = database.get_car_for_user(current.id)
  if not car or not car.vin:
    return {"vehicles": []}
  mlbr = getattr(car, "mlbr_code", None) or None
  if not mlbr and car.vin:
    mlbr = database.mlbr_code_from_vin(car.vin)
  return {
    "vehicles": [
      {
        "make": car.make,
        "model": car.model,
        "vin": car.vin,
        "plate": car.plate,
        "year": car.year,
        "fuel": car.fuel,
        "series": car.series,
        "mlbr_code": mlbr,
      }
    ]
  }


@app.get("/me/vehicle/profile-narrative", response_model=ProfileNarrativeOut)
def me_vehicle_profile_narrative_get(current: database.UserRow = Depends(get_current_user)):
  """Descriere profil vehicul (salvată în `cars.profile_narrative`); generare la POST refresh."""
  car = database.get_car_for_user(current.id)
  if not car:
    return ProfileNarrativeOut()
  text = getattr(car, "profile_narrative", None) or ""
  at = getattr(car, "profile_narrative_at", None)
  return ProfileNarrativeOut(narrative=text or "", updated_at=at)


@app.post("/me/vehicle/profile-narrative/refresh", response_model=ProfileNarrativeOut)
def me_vehicle_profile_narrative_refresh(current: database.UserRow = Depends(get_current_user)):
  """Regenerează descrierea din istoric (brain, Cloud, chat, insight) și o salvează."""
  try:
    text, at = profile_narrative_service.generate_and_persist_profile_narrative(current.id)
    return ProfileNarrativeOut(narrative=text, updated_at=at)
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e
  except RuntimeError as e:
    raise HTTPException(status_code=503, detail=str(e)) from e
  except Exception as e:
    raise HTTPException(status_code=503, detail=f"Generare profil indisponibilă: {e}") from e


@app.get("/me/preferences")
def get_me_preferences(current: database.UserRow = Depends(get_current_user)):
  """Preferințe EXO (utilizare, buget, preocupări) — folosite în ciclul EXO Intelligence."""
  return database.get_user_preferences(current.id)


@app.put("/me/preferences")
def put_me_preferences(inp: UserPrefsIn, current: database.UserRow = Depends(get_current_user)):
  data = inp.model_dump()
  if data.get("concerns") is None:
    data["concerns"] = []
  database.upsert_user_preferences(current.id, data)
  return {"ok": True, "message": "EXO va folosi preferințele la următorul ciclu."}


@app.put("/cars")
def upsert_car(inp: CarIn, current: database.UserRow = Depends(get_current_user)):
  database.upsert_car_for_user(current.id, inp.payload or {})
  return {"ok": True}


@app.post("/cars/sync")
def sync_car(payload: Dict[str, Any] = Body(...), current: database.UserRow = Depends(get_current_user)):
  """
  Sincronizează vehiculul din obiectul din browser (localStorage) în dev.db.
  Cod MLBR derivat din VIN (stabil); insert dacă lipsește, altfel update pe VIN / rând fără VIN.
  """
  try:
    return database.sync_vehicle_from_client(current.id, payload or {})
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/sync", response_model=SyncResponse)
def sync_brain(inp: SyncRequest):
  """
  Orchestrator Central — Endpoint /sync
  
  Primește:
  - VIN + owner_email + cloud_files + reminders
  
  Returnează:
  - SoftScore actualizat + Status Health + Alerts
  
  Flow:
  1. Încarcă creierul existent din DB (sau creează unul nou)
  2. Merge cu datele noi primite (cloud_files, reminders)
  3. Rulează Logic Engine pentru recalculare
  4. Salvează în DB
  5. Returnează analiza
  """
  
  # 1. Încarcă creierul existent (sau inițializează)
  brain = database.get_vehicle_brain(inp.vin)
  
  if not brain:
    # Prima sincronizare: creează un creier nou
    brain = MulberryBrain(
      vin=inp.vin,
      owner_email=inp.owner_email or "unknown@mulberry.local",
      mlbr_code=database.mlbr_code_from_vin(inp.vin),
    )
  
  # 2. Merge cu datele noi (dacă sunt furnizate)
  if inp.cloud_files is not None:
    brain.cloud_files = inp.cloud_files
  
  if inp.reminders is not None:
    brain.reminders = inp.reminders
  
  if inp.owner_email:
    brain.owner_email = inp.owner_email
  
  # 3. Rulează Logic Engine (recalculează tot)
  brain = sync_vehicle_brain(brain)
  analysis = process_mulberry_logic(brain)
  
  # 4. Salvează în DB
  database.update_vehicle_brain(inp.vin, brain)
  
  # 5. Returnează analiza
  return SyncResponse(
    vin=brain.vin,
    soft_score=brain.soft_score,
    status_health=brain.status_health,
    alerts=analysis["alerts"],
    last_sync=brain.last_sync
  )


# ────────────────────────────────────────────────────────────────
# Mulberry Cloud — upload, listă, verificare documente
# ────────────────────────────────────────────────────────────────

ALLOWED_TYPES = ("ITP", "RCA", "Talon", "Service", "RaportAI", "Fotografie", "Altele")
ALLOWED_EXT = (".jpg", ".jpeg", ".png", ".webp", ".pdf")

def _safe_filename(name: str) -> str:
  s = re.sub(r"[^\w\-.]", "_", name)[:80]
  return s or "doc"

@app.post("/cloud/upload")
def cloud_upload(
  vin: str = Form(...),
  doc_type: str = Form(...),
  file: UploadFile = File(...),
):
  """Încarcă un document (imagine/PDF) pentru VIN. Returnează doc cu url."""
  if doc_type not in ALLOWED_TYPES:
    doc_type = "Altele"
  ext = os.path.splitext(file.filename or "")[1].lower()
  if ext not in ALLOWED_EXT:
    raise HTTPException(status_code=400, detail="Tip fișier invalid. Folosește imagine sau PDF.")
  vin_clean = re.sub(r"[^\w]", "", vin)[:20] or "default"
  dir_vin = os.path.join(UPLOAD_DIR, vin_clean)
  os.makedirs(dir_vin, exist_ok=True)
  unique = uuid.uuid4().hex[:8]
  safe = _safe_filename(file.filename or "doc")
  stored_name = f"{unique}_{safe}"
  path = os.path.join(dir_vin, stored_name)
  with open(path, "wb") as f:
    f.write(file.file.read())
  brain = database.get_vehicle_brain(vin)
  if not brain:
    brain = MulberryBrain(
      vin=vin,
      owner_email="unknown@mulberry.local",
      mlbr_code=f"MLBR-{vin[-4:]}-{vin[:4]}"
    )
  next_id = max([d.id for d in brain.cloud_files], default=0) + 1
  brain.cloud_files.append(CloudFile(
    id=next_id,
    type=doc_type,
    filename=stored_name,
    verified=False,
    uploaded_at=datetime.utcnow().isoformat(),
  ))
  brain = sync_vehicle_brain(brain)
  database.update_vehicle_brain(vin, brain)
  # Forțează recalcul SoftScore la următorul GET /valuation/estimate (nu lasă scor vechi în brain).
  try:
    car_for_score = database.get_car_by_vin(vin)
    if car_for_score:
      brain.soft_score = 0.0
      database.update_vehicle_brain(vin, brain)
  except Exception:
    pass
  return {
    "id": next_id,
    "type": doc_type,
    "filename": stored_name,
    "verified": False,
    "url": f"/cloud/file/{vin_clean}/{stored_name}",
  }


@app.post("/cloud/upload/v2/{doc_type}")
async def cloud_upload_v2(
  doc_type: str,
  background_tasks: BackgroundTasks,
  current: database.UserRow = Depends(get_current_user),
  vin: str = Form(...),
  file: UploadFile = File(...),
):
  """
  Upload Cloud „no-wait”: fișierul e salvat și răspunsul e imediat;
  BackgroundTasks rulează extragerea datelor (PDF/AI) și reîmprospătarea SoftScore multi-factor.
  """
  body = await file.read()
  if not body:
    raise HTTPException(status_code=400, detail="Fișier gol.")
  try:
    out, abs_path = cloud_manager.persist_cloud_upload_v2(
      upload_root=UPLOAD_DIR,
      user_id=current.id,
      vin=vin,
      doc_type=doc_type,
      file_body=body,
      original_filename=file.filename or "doc",
    )
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e
  except PermissionError as e:
    raise HTTPException(status_code=403, detail=str(e)) from e

  background_tasks.add_task(
    cloud_manager.run_post_upload_pipeline,
    current.id,
    vin.strip().upper(),
    out["type"],
    abs_path,
    original_name=file.filename or "",
  )
  return out


@app.get("/cloud/list")
def cloud_list(vin: str):
  """Listează documentele pentru un VIN."""
  brain = database.get_vehicle_brain(vin)
  docs = []
  car = database.get_car_by_vin((vin or "").strip().upper())
  owner_id = car.user_id if car else None
  if brain:
    vin_clean = re.sub(r"[^\w]", "", vin)[:20] or "default"
    for d in brain.cloud_files:
      fn = d.filename or ""
      if owner_id and "/" in fn:
        url = f"/cloud/file/u{owner_id}/{vin_clean}/{fn}"
      else:
        url = f"/cloud/file/{vin_clean}/{fn}"
      docs.append({
        "id": d.id,
        "type": d.type,
        "filename": fn,
        "verified": d.verified,
        "uploaded_at": getattr(d, "uploaded_at", None),
        "url": url,
        "category": cloud_manager.category_for_type(d.type),
      })
  return {"documents": docs}


@app.get("/cloud/file/{vin_path:path}", response_class=FileResponse)
def cloud_file(vin_path: str):
  """Servește fișierul din Cloud (imagine/PDF). Suportă legacy `VIN/fisier` și `u{user_id}/VIN/categorie/fisier`."""
  raw = vin_path.strip("/").replace("\\", "/")
  if ".." in raw:
    raise HTTPException(status_code=400, detail="Invalid path")
  parts = raw.split("/")
  if len(parts) < 2:
    raise HTTPException(status_code=404, detail="Not found")
  if parts[0].startswith("u") and parts[0][1:].isdigit() and len(parts) >= 4:
    path = os.path.join(UPLOAD_DIR, parts[0], parts[1], *parts[2:])
    filename = parts[-1]
  else:
    vin_clean = parts[0]
    filename = parts[-1]
    path = os.path.join(UPLOAD_DIR, vin_clean, filename)
  if not os.path.isfile(path):
    raise HTTPException(status_code=404, detail="File not found")
  media_type, _ = mimetypes.guess_type(filename)
  if not media_type:
    media_type = "application/octet-stream"
  # inline: previzualizare corectă în Mulberry Cloud (<img>, fără forțare download ca la attachment)
  return FileResponse(
    path,
    filename=filename,
    media_type=media_type,
    content_disposition_type="inline",
  )


@app.get("/me/cloud/list")
def me_cloud_list(current: database.UserRow = Depends(get_current_user)):
  """Listă documente Cloud pentru mașina userului — URL-uri corecte pentru layout `u{id}/VIN/...`."""
  car = database.get_car_for_user(current.id)
  if not car or not car.vin:
    return {"documents": [], "vin": None}
  vin_u = (car.vin or "").strip().upper()
  brain = database.get_vehicle_brain(vin_u)
  vin_clean = re.sub(r"[^\w]", "", vin_u)[:20] or "default"
  docs = []
  if brain:
    for d in brain.cloud_files:
      fn = d.filename or ""
      if "/" in fn:
        url = f"/cloud/file/u{current.id}/{vin_clean}/{fn}"
      else:
        url = f"/cloud/file/{vin_clean}/{fn}"
      docs.append({
        "id": d.id,
        "type": d.type,
        "filename": fn,
        "verified": d.verified,
        "uploaded_at": getattr(d, "uploaded_at", None),
        "url": url,
        "category": cloud_manager.category_for_type(d.type),
      })
  return {"documents": docs, "vin": vin_u}


class VerifyDocIn(BaseModel):
  vin: str
  doc_id: int

@app.post("/cloud/verify")
def cloud_verify(inp: VerifyDocIn):
  """Marchează documentul ca verificat (bifa)."""
  brain = database.get_vehicle_brain(inp.vin)
  if not brain:
    raise HTTPException(status_code=404, detail="VIN negăsit")
  for d in brain.cloud_files:
    if d.id == inp.doc_id:
      d.verified = True
      brain = sync_vehicle_brain(brain)
      database.update_vehicle_brain(inp.vin, brain)
      return {"ok": True, "verified": True}
  raise HTTPException(status_code=404, detail="Document negăsit")


# ────────────────────────────────────────────────────────────────
# Mulberry SoftScore + Evaluare (preț estimat piață)
# ────────────────────────────────────────────────────────────────

# Preț mediu revânzare (lei) per model — pentru formulă evaluare
MARKET_BASE_PRICES = {
  "skoda_fabia": 8500,
  "skoda_fabia_6y": 9200,
  "vw_golf_7": 12500,
  "dacia_logan": 6500,
  "dacia_sandero": 7200,
}

def _market_key(marca: str, model: str, series: str) -> str:
  m = (marca or "").lower().replace(" ", "")
  mdl = (model or "").lower().replace(" ", "")
  s = (series or "").lower().replace(" ", "").replace("/", "")
  if "skoda" in m and "fabia" in mdl:
    return f"skoda_fabia_{s}" if s else "skoda_fabia"
  if "vw" in m or "volkswagen" in m and "golf" in mdl:
    return "vw_golf_7"
  if "dacia" in m and "logan" in mdl:
    return "dacia_logan"
  if "dacia" in m and "sandero" in mdl:
    return "dacia_sandero"
  return f"{m}_{mdl}" if m and mdl else "skoda_fabia"

def _reminder_status_done(r: Any) -> bool:
  st = r.get("status") if isinstance(r, dict) else getattr(r, "status", None)
  return st in ("done", "completed")


@app.get("/valuation/estimate")
def valuation_estimate(vin: str, live_market: int = 0):
  """
  SoftScore recalculat din date reale (cloud, RCA/ITP, km, vârstă, remindere) + evaluare piață.
  `live_market=1`: snapshot Autovit + SoftScore extins (valuation_engine).
  """
  brain = database.get_vehicle_brain(vin)
  car = database.get_car_by_vin(vin)

  if not brain or not car:
    now = datetime.utcnow()
    week_start = (now - timedelta(days=now.weekday())).date().isoformat()
    return {
      "vin": vin,
      "soft_score": 0.0,
      "status_health": "VIN negăsit sau vehicul neînregistrat.",
      "market_price_base_lei": 0,
      "estimated_value_lei": 0,
      "market_value_temporal_lei": 0,
      "delta_vs_market_lei": 0,
      "age_years": 0,
      "annual_value_loss_lei": 0,
      "formula_note": "Înregistrează vehiculul complet.",
      "price_last_updated": week_start,
    }

  now = datetime.utcnow()
  score = 0.0
  breakdown: Dict[str, Any] = {}

  files = brain.cloud_files or []

  def _cf_type(d: Any) -> str:
    return (d.get("type") if isinstance(d, dict) else getattr(d, "type", "")) or ""

  def _cf_verified(d: Any) -> bool:
    v = d.get("verified") if isinstance(d, dict) else getattr(d, "verified", False)
    return bool(v)

  docs_total = len(files)
  docs_verified = len([d for d in files if _cf_verified(d)])
  has_itp = any(_cf_type(d) == "ITP" and _cf_verified(d) for d in files)
  has_rca = any(_cf_type(d) == "RCA" and _cf_verified(d) for d in files)
  has_tal = any(_cf_type(d) == "Talon" and _cf_verified(d) for d in files)
  doc_score = (12 if has_itp else 0) + (12 if has_rca else 0) + (6 if has_tal else 0)
  score += doc_score
  breakdown["documente"] = doc_score

  rca_days = None
  rca_score = 0
  if car.rca_expiry:
    try:
      rca_exp = datetime.fromisoformat(str(car.rca_expiry).replace("Z", "").split("T")[0])
      rca_days = (rca_exp.date() - now.date()).days
      rca_score = 15 if rca_days > 30 else (8 if rca_days > 0 else 0)
    except Exception:
      pass
  score += rca_score
  breakdown["rca"] = rca_score

  itp_days = None
  itp_score = 0
  if car.itp_expiry:
    try:
      itp_exp = datetime.fromisoformat(str(car.itp_expiry).replace("Z", "").split("T")[0])
      itp_days = (itp_exp.date() - now.date()).days
      itp_score = 15 if itp_days > 30 else (8 if itp_days > 0 else 0)
    except Exception:
      pass
  score += itp_score
  breakdown["itp"] = itp_score

  km = car.km_actuali or 0
  km_score = (
    (20 if km < 50000 else 17 if km < 100000 else 13 if km < 150000 else 8 if km < 200000 else 3)
    if km > 0
    else 10
  )
  score += km_score
  breakdown["km"] = km_score

  age_score = 5
  try:
    age_y = now.year - int(str(car.year).strip())
    age_score = 10 if age_y <= 3 else 8 if age_y <= 7 else 6 if age_y <= 12 else 4 if age_y <= 18 else 2
  except Exception:
    pass
  score += age_score
  breakdown["varsta"] = age_score

  rem_score = 0
  if brain.reminders:
    total_r = len(brain.reminders)
    completed = len([r for r in brain.reminders if _reminder_status_done(r)])
    rem_score = round((completed / total_r) * 10) if total_r > 0 else 0
  score += rem_score
  breakdown["remindere"] = rem_score

  total_score = min(100.0, round(score, 2))

  brain.soft_score = total_score
  brain.status_health = (
    "Excelent — vehicul în stare foarte bună"
    if total_score >= 80
    else "Bun — câteva îmbunătățiri posibile"
    if total_score >= 60
    else "Atenție — verifică documentele"
    if total_score >= 40
    else "Critic — documente lipsă sau expirate"
  )
  database.update_vehicle_brain(vin, brain)

  make = (car.make or "").strip()
  model = (car.model or "").strip()
  series = (car.series or "").strip()
  key = _market_key(make, model, series)
  base_lei = float(MARKET_BASE_PRICES.get(key, 8000))

  try:
    year_raw = int(str(car.year).strip()) if car.year else None
  except Exception:
    year_raw = None

  market_out = update_market_value(
    v_base_lei=base_lei,
    vehicle_year=year_raw,
    current_soft_score=total_score,
    annual_depreciation=0.12,
  )

  now2 = datetime.utcnow()
  week_start = (now2 - timedelta(days=now2.weekday())).date().isoformat()

  out = {
    "vin": car.vin,
    "soft_score": total_score,
    "soft_score_real": total_score,
    "status_health": brain.status_health,
    "breakdown": breakdown,
    "docs_total": docs_total,
    "docs_verified": docs_verified,
    "rca_days": rca_days,
    "itp_days": itp_days,
    "market_price_base_lei": base_lei,
    "age_years": int(market_out.get("age_years", 0)),
    "annual_depreciation": float(market_out.get("annual_depreciation", 0.12)),
    "market_value_temporal_lei": int(market_out.get("market_value_temporal_lei", 0)),
    "estimated_value_lei": int(market_out.get("estimated_value_lei", 0)),
    "delta_vs_market_lei": int(market_out.get("delta_vs_market_lei", 0)),
    "annual_value_loss_lei": int(market_out.get("annual_value_loss_lei", 0)),
    "score_modifier": float(market_out.get("score_modifier", 0.0)),
    "price_last_updated": week_start,
    "formula_note": (
      f"Documente({breakdown.get('documente', 0)}p) + "
      f"RCA({breakdown.get('rca', 0)}p) + ITP({breakdown.get('itp', 0)}p) + "
      f"Km({breakdown.get('km', 0)}p) + Vârstă({breakdown.get('varsta', 0)}p) + "
      f"Remindere({breakdown.get('remindere', 0)}p)"
    ),
  }

  if live_market and car:
    try:
      snap = valuation_engine.snapshot_for_vehicle(car, brain)
      out["market_live"] = snap.get("market")
      out["soft_score_real"] = snap.get("soft_score_real")
    except Exception as e:
      out["market_live_error"] = str(e)

  return out


@app.post("/assistant/exo", response_model=ChatResponse)
def assistant_exo(inp: ChatRequest, current: Optional[database.UserRow] = Depends(optional_device_fingerprint)):
  """
  MulberryEXO — AIProxy (Groq + fallback Ollama) cu context complet (vehicul, piață, insights, carburant).
  `context.history`: [{\"role\":\"user\"|\"assistant\",\"content\":\"...\"}, ...] mesaje anterioare (fără duplicat la mesajul curent).
  """
  atts = inp.attachments or []
  base_msg = (inp.message or "").strip()
  if not base_msg and not atts:
    raise HTTPException(status_code=400, detail="Mesaj gol.")
  _ATT_MAX_B64 = 700_000
  for a in atts[:6]:
    if len((a.data_base64 or "").strip()) > _ATT_MAX_B64:
      raise HTTPException(status_code=400, detail="Un atașament depășește limita permisă.")

  msg_for_model = base_msg
  if atts:
    lines = []
    has_image = False
    for a in atts[:4]:
      nm = (a.name or "fișier").strip() or "fișier"
      mt = (a.mime or "").strip() or "application/octet-stream"
      lines.append(f"- {nm} [{mt}]")
      if "image" in mt.lower():
        has_image = True
    extra = "\n\n[Atașamente utilizator]\n" + "\n".join(lines)
    if has_image:
      extra += (
        "\n(Cel puțin o imagine: tratează ca posibilă fotografie vehicul, document sau panou — "
        "răspunde practic în română, fără a pretinde analiză vizuală detaliată.)"
      )
    msg_for_model = (base_msg + extra).strip() if base_msg else (
      "Utilizatorul a trimis fișiere fără text. Ghidhează-l: ce să verifice, cum să le încarce în Mulberry Cloud, pași la service."
      + extra
    )

  vin = (inp.vin or "").strip().upper()
  if not vin:
    return ChatResponse(reply="Adaugă VIN-ul vehiculului în profil pentru răspunsuri MulberryEXO personalizate.")

  hist = []
  if inp.context:
    hist = inp.context.get("history") or []

  try:
    result = exo_assistant.ask_exo(
      user_id=current.id if current else 0,
      vin=vin,
      message=msg_for_model,
      conversation_history=hist,
    )
  except RuntimeError as e:
    raise HTTPException(status_code=503, detail=str(e))
  except Exception as e:
    import traceback
    print(f"[assistant/exo] EROARE RAG/GROQ/LLM: {e!r}")
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=f"MulberryEXO: {e}")

  reply = (result.get("reply") or "").strip() or "Nu am putut genera un răspuns."
  thread_id = (inp.thread_id or "default").strip()[:128] or "default"
  persist_user = base_msg if base_msg else "[Fișiere atașate]"
  if atts:
    persist_user += " · " + ", ".join((a.name or "fișier").strip() for a in atts[:4])
  _lb = (result.get("llm_backend") or "groq").strip().lower()
  _engine_tag = "exo_gemini" if _lb == "gemini" else ("exo_ollama" if _lb == "ollama" else "exo_groq")
  if current:
    try:
      database.append_chat_message(current.id, thread_id, "user", persist_user.strip(), None)
      database.append_chat_message(current.id, thread_id, "assistant", reply, {"engine": _engine_tag})
    except Exception as e:
      print(f"[assistant/exo] SQLite persist: {e}")

  return ChatResponse(reply=reply)


@app.post("/assistant/ask", response_model=ChatResponse)
def assistant_ask(inp: ChatRequest, current: Optional[database.UserRow] = Depends(get_current_user_optional)):
  """
  Mulberry Assistant — Expert Auto AI
  
  Dacă utilizatorul e Fondator (role=founder), primește protocoale de nivel 1.
  
  Primește:
  - user_id
  - message (întrebare)
  - VIN (opțional)
  - context (marca, model, cloud_files, reminders, istoric întrebări)
  
  Returnează:
  - răspuns contextualizat (analizează brand + probleme specifice)
  
  Logică:
  - Identifică keywords (probleme/roți/mecanic/suspensie/frână)
  - Verifică brand-ul (Skoda → probleme comune specifice)
  - Caută în istoric intervenții (dacă există remindere legate)
  - Oferă recomandări + opțiune de reminder
  """
  
  message = inp.message.lower()
  context = inp.context or {}
  is_founder = current is not None and (current.role or "").lower() == "founder"
  founder_prefix = "**Bun venit, Fondator.** Protocoale de nivel 1 active. Acces la date brute și rapoarte de cercetare disponibil.\n\n" if is_founder else ""

  marca = (context.get("marca") or "").lower()
  model = (context.get("model") or "").lower()
  series = (context.get("series") or "").lower()
  cloud_files = context.get("cloud_files", [])
  reminders = context.get("reminders", [])
  
  # Construim "tonul expert" — Apple-style calm dar tehnic
  vehicle_name = f"{marca.capitalize()} {series} {model}".strip() if marca else "vehiculul tău"

  # Pas A–C: manual local Skoda Fabia 6Y + RAG narațiune + memorie conversație
  manual = manual_skoda.analyze_user_message(inp.message)
  user_conv_key = (current.identifier if current else None) or (inp.user_id or "guest")
  thread_id = (inp.thread_id or "default").strip()[:128] or "default"

  brain_soft: Optional[float] = None
  brain_status: Optional[str] = None
  if inp.vin:
    try:
      b = database.get_vehicle_brain(inp.vin.strip().upper())
      if b:
        brain_soft = float(b.soft_score)
        brain_status = (b.status_health or "").strip() or None
    except Exception:
      pass

  def out(reply_body: str) -> ChatResponse:
    narrative = chat_rag_narrative.build_narrative_prefix(
      context, message, inp.vin, manual, brain_soft, brain_status
    )
    if narrative:
      reply_body = narrative + reply_body
    merged = manual_skoda.merge_into_reply(reply_body, manual)
    meta_alert = manual.alert.get("kind") if manual.alert else None
    meta = {"manual_lines": manual.matched_line_numbers, "alert": meta_alert}
    if current:
      try:
        database.append_chat_message(current.id, thread_id, "user", (inp.message or "").strip(), None)
        database.append_chat_message(current.id, thread_id, "assistant", merged, meta)
      except Exception as e:
        print(f"[chat] SQLite persist: {e}")
    else:
      conversation_store.append_turn(
        user_conv_key,
        (inp.message or "").strip(),
        merged,
        meta,
      )
    excerpts_out = (
      [ManualExcerpt(line_from=e["line_from"], line_to=e["line_to"], text=e["text"]) for e in manual.excerpts]
      if manual.excerpts
      else None
    )
    alert_out = DigitalTwinAlert(**manual.alert) if manual.alert else None
    return ChatResponse(
      reply=merged,
      manual_excerpts=excerpts_out,
      digital_twin_alert=alert_out,
    )

  # ──── Analiză SoftScore ────
  if "scor" in message or "softscore" in message or "puncte" in message:
    if inp.vin:
      brain = database.get_vehicle_brain(inp.vin)
      if brain:
        return out(founder_prefix + f"SoftScore-ul pentru {vehicle_name} este **{brain.soft_score:.1f}%**.\n\n{brain.status_health}\n\nSfat: {'Excelent! Menține documentele la zi.' if brain.soft_score >= 70 else 'Încarcă documentele lipsă (ITP, RCA) pentru a îmbunătăți scorul.'}")
    return out(founder_prefix + "Nu am găsit date despre vehicul. Asigură-te că ai completat VIN-ul în timpul înregistrării.")
  
  # ──── Analiză Documente (ITP/RCA/Talon) ────
  elif "document" in message or "itp" in message or "rca" in message or "talon" in message:
    verified = len([f for f in cloud_files if f.get("verified")])
    total = len(cloud_files)
    if total == 0:
      return out(founder_prefix + """📄 Nu ai încărcat încă documente în Mulberry Cloud.

Documentele (ITP, RCA, Talon) îți deblochează până la +40 puncte la SoftScore și îți oferă liniște: știi că ești în regulă la control. Încarcă poze sau PDF-uri din **Mulberry Cloud**, confirmă fiecare cu bifa, și indexul tău crește automat. Dacă vrei să începi rapid, folosește cardul **Adaugă ITP** de mai jos.""")
    
    missing = []
    if not any(f.get("type") == "ITP" and f.get("verified") for f in cloud_files):
      missing.append("ITP (+15 puncte)")
    if not any(f.get("type") == "RCA" and f.get("verified") for f in cloud_files):
      missing.append("RCA (+15 puncte)")
    if not any(f.get("type") == "Talon" and f.get("verified") for f in cloud_files):
      missing.append("Talon (+10 puncte)")
    
    if missing:
      return out(founder_prefix + f"""Ai {verified}/{total} documente verificate.

**Lipsesc:** {', '.join(missing)}. Fiecare document confirmat îți crește SoftScore-ul și îți dă siguranța că ești în regulă. Deschide **Mulberry Cloud** (cardul Adaugă ITP sau Încarcă RCA de mai jos), încarcă fișierul și bifează-l. În câteva secunde indexul se actualizează.""")
    return out(founder_prefix + f"""✅ Toate documentele ({total}/{total}) sunt verificate.

SoftScore-ul tău beneficiază de bonus complet. Menține-le la zi: când se apropie reînnoirea ITP sau RCA, încarcă din nou în Cloud. Dacă vrei să vezi exact unde stai la valoare, folosește **Verifică Index**; pentru planificare, **Raport lunar** (reminder).""")
  
  # ──── Analiză Remindere ────
  elif "reminder" in message or "task" in message or "mentenanță" in message:
    pending = [r for r in reminders if r.get("status") == "pending"]
    if not pending:
      return out(founder_prefix + """✅ Nu ai remindere active. Totul e la zi!

Un reminder te ajută să nu uiți revizia, schimbul de ulei sau ITP: îl setezi o dată și primești un semn când se apropie termenul. Dacă vrei să îți planifici următorul pas (ex. schimb ulei sau raport lunar), deschide **Raport lunar** din cardurile de mai jos și adaugă un reminder. Așa rămâi mereu cu mașina în siguranță.""")
    
    tasks_list = "\n".join([f"• {r.get('task', 'Task necunoscut')}" for r in pending[:5]])
    return out(founder_prefix + f"""Ai **{len(pending)} reminder{'e' if len(pending) > 1 else ''}** în așteptare:

{tasks_list}

Marchează pe rând cele finalizate ca să ții lista curată. Dacă vrei să adaugi unul nou (ex. raport lunar sau revizie), folosește cardul **Raport lunar** de mai jos. Reminderele la zi îți mențin și SoftScore-ul în formă.""")
  
  # ──── Analiză Probleme Tehnice (ChromaDB + Lookup Table) ────
  elif any(kw in message for kw in ["problemă", "probleme", "rot", "roat", "suspens", "fran", "frin", "zgomot", "huruit", "mecanic", "vibrat", "rugin", "prag", "geam", "abs", "consum", "ulei", "ecran", "infotainment", "ambreja", "volant"]):
    # Mapare componentă pentru lookup
    if any(kw in message for kw in ["rot", "roat", "rulment", "suspens", "zgomot", "huruit", "vitez"]):
      component = "roți"
    elif any(kw in message for kw in ["fran", "frin", "frana"]):
      component = "frâne"
    elif any(kw in message for kw in ["prag", "rugin", "rugina"]):
      component = "prag"
    elif any(kw in message for kw in ["geam", "macara", "electric geam"]):
      component = "geam"
    elif any(kw in message for kw in ["abs", "senzor"]):
      component = "abs"
    elif any(kw in message for kw in ["motor", "consum", "ulei", "apa", "pompa"]):
      component = "motor"
    elif any(kw in message for kw in ["ecran", "infotainment", "lag"]):
      component = "infotainment"
    elif any(kw in message for kw in ["ambreja", "volant", "ambreiaj"]):
      component = "ambreja"
    else:
      component = "roți"  # fallback generic

    # 0. Căutare semantică în ChromaDB (Motor Extindere Continuu)
    vector_ctx = ""
    try:
      query_text = f"{vehicle_name} {component} {inp.message}"
      hits = vector_store.query(query_text, n_results=3)
      if hits:
        vector_ctx = "\n\n📚 *Din baza de cunoștințe extinse:*\n" + "\n".join([f"• {h['text'][:200]}..." if len(h.get("text", "")) > 200 else f"• {h.get('text', '')}" for h in hits])
    except Exception:
      pass

    # 1. Căutare în Knowledge Base (Lookup Table)
    advice = expert_brain.get_expert_advice(
      marca=(context.get("marca") or "").strip(),
      model=(context.get("model") or "").strip(),
      series=(context.get("series") or "").strip(),
      component=component,
      user_message=message,
      include_preventive=True,
    )

    if advice:
      if vector_ctx:
        advice = vector_ctx + "\n\n---\n\n" + advice
      # Adăugăm tendințe din raportări utilizatori (dacă există)
      trends = expert_brain.get_trending_risks(
        marca=(context.get("marca") or "").strip(),
        model=(context.get("model") or "").strip(),
      )
      if trends:
        extra = "\n\n⚠️ Alți posesori au raportat recent: " + ", ".join([f"{c} ({n}x)" for c, n in trends[:2]])
        advice += extra
      return out(founder_prefix + advice)
    elif vector_ctx:
      return out(founder_prefix + vector_ctx + "\n\nPentru detalii specifice, verifică la service sau adaugă un reminder.")

    # 2. Fallback: răspuns generic dacă nu e în lookup
    return out(founder_prefix + f"Am detectat o întrebare despre {component} la {vehicle_name}.\n\nNu am încă date specifice pentru acest model. Verifică la service și poți raporta problema (buton 'Raportează') pentru ca Mulberry să învețe.")
  
  # ──── Ce este Mulberry? ────
  elif "mulberry" in message and ("ce" in message or "cum" in message):
    return out(founder_prefix + """Mulberry este **co-pilotul tău auto inteligent**.

Te ajut să:
• **Monitorizezi** ITP, RCA și talonul — încarcă documentele în Cloud și confirmă cu bifa pentru a-ți crește indexul.
• **Calculez SoftScore** bazat pe documente verificate și remindere la zi.
• **Răspund** la întrebări tehnice despre mașina ta (roți, frâne, motor, probleme frecvente la modelul tău).
• **Sugerez acțiuni** pentru a îmbunătăți scorul: Adaugă ITP, Raport lunar, Verifică Index — toate sunt la un click în cardurile de mai jos.

Poți oricând să îmi scrii despre documente, remindere sau probleme tehnice.""")

  # ──── Răspuns generic (chatbot conversational) + RAG vectorial pe orice întrebare ────
  else:
    vec_snip = ""
    try:
      hits = vector_store.query(f"{vehicle_name} {inp.message}", n_results=3)
      if hits:
        vec_snip = (
          "*Din indexul Mulberry (RAG, resurse încărcate):*\n"
          + "\n".join(f"• {(h.get('text') or '')[:300].strip()}…" if len(h.get("text") or "") > 300 else f"• {(h.get('text') or '').strip()}" for h in hits)
          + "\n\n---\n\n"
        )
    except Exception:
      pass
    return out(
      founder_prefix
      + vec_snip
      + f"""Am înțeles întrebarea ta: **"{inp.message}"**

Poți să mă întrebi despre:
• **SoftScore și documentele tale** — cum stai la ITP, RCA, talon și cum îți crești indexul.
• **Remindere și mentenanță** — ce task-uri ai în așteptare și cum îți planifici revizia.
• **Probleme tehnice** — roți, frâne, motor, zgomote sau defecte frecvente la modelul tău.

Spune-mi ce te interesează despre {vehicle_name} și îți răspund punctual. Dacă vrei să acționezi rapid, folosește cardurile de sugestii de mai jos: Adaugă ITP, Raport lunar sau Verifică Index."""
    )


@app.get("/assistant/chat/history")
def assistant_chat_history(
  thread_id: str = "default",
  limit: int = 200,
  current: database.UserRow = Depends(get_current_user),
):
  """Istoric mesaje din SQLite pentru thread-ul curent (UI chat continuu)."""
  rows = database.list_chat_messages(current.id, thread_id, limit=max(1, min(limit, 500)))
  return {
    "thread_id": thread_id,
    "messages": [{"role": r["role"], "text": r["text"], "created_at": r["created_at"]} for r in rows],
  }


@app.get("/assistant/chat/threads")
def assistant_chat_threads(
  current: database.UserRow = Depends(get_current_user),
  limit: int = 40,
):
  """Lista thread-uri salvate în DB pentru utilizatorul autentificat."""
  return {"threads": database.list_chat_threads(current.id, limit=max(1, min(limit, 80)))}


# ────────────────────────────────────────────────────────────────
# MLBR Digital File — identitate vehicul semnată HMAC (public GET)
# ────────────────────────────────────────────────────────────────

class MlbrGenerateIn(BaseModel):
  vin: str


def _resolve_mlbr_row(mlbr_path: str):
  raw = unquote(mlbr_path or "").strip()
  if not raw:
    return None
  candidates = [raw, mlbr_file.normalize_mlbr_id(raw)]
  seen = set()
  for c in candidates:
    if not c or c in seen:
      continue
    seen.add(c)
    row = database.mlbr_get_by_mlbr_id(c)
    if row:
      return row
  return None


@app.post("/mlbr/generate")
def mlbr_generate(inp: MlbrGenerateIn, current: database.UserRow = Depends(get_current_user)):
  """Generează o singură dată fișierul MLBR pentru VIN; dacă există — returnează existentul."""
  vin = (inp.vin or "").strip().upper()
  if not vin:
    raise HTTPException(status_code=400, detail="VIN lipsă.")
  existing = database.mlbr_get_by_vin(vin)
  if existing:
    try:
      fd = json.loads(existing["file_data"])
    except Exception:
      raise HTTPException(status_code=500, detail="Date MLBR corupte.")
    return {"created": False, "mlbr_file": fd}
  car = database.get_car_by_user_and_vin(current.id, vin)
  if not car:
    raise HTTPException(status_code=404, detail="Vehicul negăsit pentru acest cont.")
  mlbr_id_override = None
  if car.ycr_id and str(car.ycr_id).strip():
    cand = mlbr_file.normalize_mlbr_id(car.ycr_id)
    if cand.startswith("MLBR-"):
      mlbr_id_override = cand
  if not mlbr_id_override:
    mlbr_id_override = mlbr_file.new_mlbr_id()
  car_d = {
    "vin": car.vin,
    "plate": car.plate or "",
    "make": car.make or "",
    "model": car.model or "",
    "series": car.series or "",
    "year": car.year,
    "fuel": car.fuel or "",
    "ycr_id": car.ycr_id or "",
  }
  user_d = {"identifier": current.identifier, "email": current.email or "", "id": current.id}
  payload = mlbr_file.generate_mlbr_file(car_d, user_d, mlbr_id_override=mlbr_id_override)
  sig = payload["signature"]
  gen_at = payload["generated_at"]
  row = {
    "mlbr_id": payload["mlbr_id"],
    "vin": vin,
    "file_data": json.dumps(payload, ensure_ascii=False),
    "signature": sig,
    "generated_at": gen_at,
    "is_locked": 1,
    "views": 0,
    "last_viewed": None,
  }
  try:
    database.mlbr_insert(row)
  except sqlite3.IntegrityError:
    ex2 = database.mlbr_get_by_vin(vin)
    if ex2:
      fd = json.loads(ex2["file_data"])
      return {"created": False, "mlbr_file": fd}
    raise HTTPException(status_code=409, detail="MLBR există deja.")
  database.set_car_ycr_id_for_vin(current.id, vin, payload["mlbr_id"])
  return {"created": True, "mlbr_file": payload}


@app.get("/mlbr/{mlbr_id}")
def mlbr_public_get(mlbr_id: str):
  """Public: date vehicul + validare semnătură; incrementează views."""
  row = _resolve_mlbr_row(mlbr_id)
  if not row:
    raise HTTPException(status_code=404, detail="MLBR negăsit.")
  views = database.mlbr_increment_views(row["mlbr_id"])
  try:
    fd = json.loads(row["file_data"])
  except Exception:
    raise HTTPException(status_code=500, detail="Date MLBR corupte.")
  valid = mlbr_file.verify_mlbr_file(dict(fd))
  safe = mlbr_file.public_safe_payload(fd)
  sig = fd.get("signature") or ""
  prev = (sig[:12] + "…" + sig[-6:]) if len(sig) > 20 else sig
  return {
    "valid": valid,
    "mlbr_id": fd.get("mlbr_id"),
    "data": safe,
    "views": views,
    "signature_preview": prev,
    "authentic": valid,
  }


@app.get("/mlbr/{mlbr_id}/verify")
def mlbr_public_verify(mlbr_id: str):
  row = _resolve_mlbr_row(mlbr_id)
  if not row:
    raise HTTPException(status_code=404, detail="MLBR negăsit.")
  try:
    fd = json.loads(row["file_data"])
  except Exception:
    raise HTTPException(status_code=500, detail="Date MLBR corupte.")
  valid = mlbr_file.verify_mlbr_file(dict(fd))
  return {
    "valid": valid,
    "mlbr_id": fd.get("mlbr_id"),
    "generated_at": fd.get("generated_at"),
    "version": fd.get("version"),
  }


@app.get("/mlbr_file.html")
def serve_mlbr_file_html():
  """Pagină publică BIOS/terminal (scan QR)."""
  p = ROOT_DIR / "mlbr_file.html"
  if not p.is_file():
    raise HTTPException(status_code=404, detail="Pagină indisponibilă.")
  return FileResponse(str(p), media_type="text/html")


# ────────────────────────────────────────────────────────────────
# Feedback Loop — endpoint /train (dezvoltator)
# ────────────────────────────────────────────────────────────────

TRAIN_SECRET = os.getenv("TRAIN_SECRET", "mulberry-train-dev")

class TrainRequest(BaseModel):
  marca: str
  model: str
  series: Optional[str] = None
  component: str
  fault_description: str
  secret: Optional[str] = None  # pentru backdoor

class ReportRequest(BaseModel):
  component: str
  fault_description: str


@app.post("/assistant/report")
def assistant_report(inp: ReportRequest, current: database.UserRow = Depends(get_current_user)):
  """
  Raportare utilizator — salvează o problemă raportată (anonimizat) în Knowledge Base.
  Folosește mașina din profilul user-ului pentru model.
  """
  car = database.get_car_for_user(current.id)
  if not car or not car.make or not car.model:
    raise HTTPException(status_code=400, detail="Nu ai o mașină înregistrată. Completează profilul vehicul.")
  expert_brain.add_user_report(
    marca=(car.make or "").strip(),
    model=(car.model or "").strip(),
    component=inp.component.strip(),
    fault_description=inp.fault_description.strip(),
  )
  return {"ok": True, "message": "Mulberry a reținut raportul. Mulțumim!"}


@app.post("/assistant/train")
def assistant_train(inp: TrainRequest):
  """
  Backdoor dezvoltator — adaugă o raportare de problemă în Knowledge Base.
  Dacă mai mulți posesori raportează același lucru, crește scorul de risc.
  """
  if inp.secret != TRAIN_SECRET:
    raise HTTPException(status_code=403, detail="Acces refuzat")
  expert_brain.add_user_report(
    marca=inp.marca.strip(),
    model=inp.model.strip(),
    component=inp.component.strip(),
    fault_description=inp.fault_description.strip(),
  )
  return {"ok": True, "message": "Raportare salvată. Mulberry va include tendința la răspunsuri viitoare."}


# ────────────────────────────────────────────────────────────────
# Frontend static — același origin cu API (:9000), fără Live Server
#
# Deschide: http://127.0.0.1:9000/  → mulberry.html
#           http://127.0.0.1:9000/mulberry_chat.html, … (orice *.html din rădăcină)
# Resurse:  /js/*, /css/*, /assets/*, /style.css
# Opțional: folder static/ în rădăcină → http://127.0.0.1:9000/static/… (nu montăm tot ROOT_DIR: .env / dev.db)
# Pornește: uvicorn backend.main:app --host 127.0.0.1 --port 9000 --reload
# În config.js, API-ul folosește același origin pe :9000 → fără CORS față de :5500.
# ────────────────────────────────────────────────────────────────

def _mount_static_dir(url_path: str, relative_dir: str, mount_name: str) -> None:
  d = ROOT_DIR / relative_dir
  if d.is_dir():
    app.mount(url_path, StaticFiles(directory=str(d)), name=mount_name)


_mount_static_dir("/js", "js", "mulberry_js")
_mount_static_dir("/css", "css", "mulberry_css")
_mount_static_dir("/assets", "assets", "mulberry_assets")
_optional_public = ROOT_DIR / "static"
if _optional_public.is_dir():
  app.mount("/static", StaticFiles(directory=str(_optional_public)), name="mulberry_static_public")


@app.get("/style.css", include_in_schema=False)
def serve_root_style_css():
  p = ROOT_DIR / "style.css"
  if not p.is_file():
    raise HTTPException(status_code=404, detail="Not found")
  return FileResponse(str(p), media_type="text/css")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def serve_frontend_root():
  p = ROOT_DIR / "mulberry.html"
  if not p.is_file():
    raise HTTPException(status_code=404, detail="mulberry.html lipsă")
  return FileResponse(str(p), media_type="text/html")


_HTML_PAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


@app.get("/{page}.html", response_class=FileResponse, include_in_schema=False)
def serve_frontend_html(page: str):
  """HTML la rădăcina proiectului (ex. mulberry_menu.html). Rutele API fără .html nu sunt afectate."""
  if not _HTML_PAGE_RE.fullmatch(page):
    raise HTTPException(status_code=404, detail="Not found")
  target = ROOT_DIR / f"{page}.html"
  if not target.is_file():
    raise HTTPException(status_code=404, detail="Not found")
  return FileResponse(str(target), media_type="text/html")


# Local / container: pornește Uvicorn direct (Vercel folosește api/main.py ca serverless).
if __name__ == "__main__":
  import uvicorn
  port = int(os.environ.get("PORT", 8000))
  print(f"[Mulberry] Direct run on port {port}")
  uvicorn.run(app, host="0.0.0.0", port=port)

