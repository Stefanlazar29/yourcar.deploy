"""MulberryGO — sistem rezervări service auto.

Auth:
  Parteneri  → header X-Partner-Token: <uuid din partners.api_token>
  Clienți    → header Authorization: Bearer <JWT Mulberry> (același token din mulberry_app)
"""
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/go", tags=["mulberry-go"])


# ──────────────────────────────────────────────
# Supabase client (service key, bypass RLS)
# ──────────────────────────────────────────────

def _sb():
    try:
        from supabase import create_client
    except ImportError:
        raise HTTPException(status_code=500, detail="supabase-py not installed")
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=500, detail="SUPABASE_URL / SUPABASE_SERVICE_KEY lipsesc din .env")
    return create_client(url, key)


# ──────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────

def _require_partner(x_partner_token: Optional[str]) -> dict:
    if not x_partner_token or not x_partner_token.strip():
        raise HTTPException(status_code=401, detail="Header X-Partner-Token lipsă")
    token = x_partner_token.strip()
    sb = _sb()
    resp = sb.table("partners").select("*").eq("api_token", token).execute()
    if not resp.data:
        raise HTTPException(status_code=401, detail="Token partener invalid")
    return resp.data[0]


def _require_client_email(authorization: Optional[str]) -> str:
    """Extrage email din JWT Mulberry (Bearer token)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Autentificare necesară (Bearer JWT)")
    token = authorization[7:].strip()
    try:
        import os as _os
        from jose import jwt, JWTError
        secret = _os.getenv("JWT_SECRET", "schimba-ma")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        email = payload.get("identifier") or payload.get("email") or ""
        if not email:
            raise ValueError("Email absent din token")
        return email
    except (Exception,) as e:
        raise HTTPException(status_code=401, detail=f"Token invalid: {e}")


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class PartnerRegisterIn(BaseModel):
    email: str
    name: str
    cif: str
    city: Optional[str] = ""
    phone: Optional[str] = ""
    description: Optional[str] = ""


class ServiceIn(BaseModel):
    name: str
    description: Optional[str] = ""
    duration_min: int = 60
    price_ron: Optional[float] = None


class RezervareaIn(BaseModel):
    partner_id: str
    service_id: Optional[str] = None
    data_programata: str
    vehicle_plate: Optional[str] = ""
    notes: Optional[str] = ""


class StatusIn(BaseModel):
    status: str


# ──────────────────────────────────────────────
# Partner registration / profile
# ──────────────────────────────────────────────

@router.post("/partner/register")
def partner_register(inp: PartnerRegisterIn):
    """Înregistrare/login partener. Dacă email există returnează token-ul existent."""
    sb = _sb()
    existing = sb.table("partners").select("id,api_token,name,city,cif").eq("email", inp.email).execute()
    if existing.data:
        p = existing.data[0]
        return {"ok": True, "partner_token": str(p["api_token"]), "partner_id": str(p["id"]), "name": p["name"]}
    data = {
        "email": inp.email,
        "name": inp.name,
        "cif": inp.cif,
        "city": inp.city or "",
        "phone": inp.phone or "",
        "description": inp.description or "",
    }
    resp = sb.table("partners").insert(data).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Eroare la crearea profilului partener")
    p = resp.data[0]
    return {"ok": True, "partner_token": str(p["api_token"]), "partner_id": str(p["id"]), "name": p["name"]}


@router.get("/partner/profile")
def partner_profile(x_partner_token: Optional[str] = Header(None)):
    partner = _require_partner(x_partner_token)
    partner.pop("api_token", None)
    return {"partner": partner}


# ──────────────────────────────────────────────
# Partner services CRUD
# ──────────────────────────────────────────────

@router.get("/partner/services")
def partner_services_list(x_partner_token: Optional[str] = Header(None)):
    partner = _require_partner(x_partner_token)
    sb = _sb()
    resp = sb.table("partner_services").select("*").eq("partner_id", partner["id"]).order("created_at").execute()
    return {"services": resp.data}


@router.post("/partner/services")
def partner_services_add(inp: ServiceIn, x_partner_token: Optional[str] = Header(None)):
    partner = _require_partner(x_partner_token)
    sb = _sb()
    row = {
        "partner_id": partner["id"],
        "name": inp.name,
        "description": inp.description or "",
        "duration_min": inp.duration_min,
        "price_ron": inp.price_ron,
    }
    resp = sb.table("partner_services").insert(row).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Eroare la adăugarea serviciului")
    return {"ok": True, "service": resp.data[0]}


@router.patch("/partner/services/{svc_id}")
def partner_services_update(svc_id: str, inp: ServiceIn, x_partner_token: Optional[str] = Header(None)):
    partner = _require_partner(x_partner_token)
    sb = _sb()
    existing = sb.table("partner_services").select("partner_id").eq("id", svc_id).execute()
    if not existing.data or existing.data[0]["partner_id"] != partner["id"]:
        raise HTTPException(status_code=403, detail="Serviciu inexistent sau acces refuzat")
    resp = sb.table("partner_services").update({
        "name": inp.name,
        "description": inp.description or "",
        "duration_min": inp.duration_min,
        "price_ron": inp.price_ron,
    }).eq("id", svc_id).execute()
    return {"ok": True, "service": resp.data[0] if resp.data else {}}


@router.delete("/partner/services/{svc_id}")
def partner_services_deactivate(svc_id: str, x_partner_token: Optional[str] = Header(None)):
    partner = _require_partner(x_partner_token)
    sb = _sb()
    existing = sb.table("partner_services").select("partner_id").eq("id", svc_id).execute()
    if not existing.data or existing.data[0]["partner_id"] != partner["id"]:
        raise HTTPException(status_code=403, detail="Serviciu inexistent sau acces refuzat")
    sb.table("partner_services").update({"active": False}).eq("id", svc_id).execute()
    return {"ok": True}


# ──────────────────────────────────────────────
# Partner rezervări
# ──────────────────────────────────────────────

@router.get("/partner/requests")
def partner_requests(x_partner_token: Optional[str] = Header(None)):
    partner = _require_partner(x_partner_token)
    sb = _sb()
    resp = (
        sb.table("rezervari")
        .select("*, partner_services(name, duration_min, price_ron)")
        .eq("partner_id", partner["id"])
        .order("data_programata", desc=True)
        .execute()
    )
    return {"rezervari": resp.data}


@router.patch("/rezervare/{rez_id}/status")
def update_status(rez_id: str, inp: StatusIn, x_partner_token: Optional[str] = Header(None)):
    allowed = {"pending", "confirmed", "cancelled", "completed"}
    if inp.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status invalid. Permise: {sorted(allowed)}")
    partner = _require_partner(x_partner_token)
    sb = _sb()
    rez = sb.table("rezervari").select("id,partner_id").eq("id", rez_id).execute()
    if not rez.data:
        raise HTTPException(status_code=404, detail="Rezervare inexistentă")
    if rez.data[0]["partner_id"] != partner["id"]:
        raise HTTPException(status_code=403, detail="Nu ai acces la această rezervare")
    resp = sb.table("rezervari").update({"status": inp.status}).eq("id", rez_id).execute()
    return {"ok": True, "rezervare": resp.data[0] if resp.data else {}}


# ──────────────────────────────────────────────
# Public endpoints (clienți)
# ──────────────────────────────────────────────

@router.get("/services")
def public_services(city: Optional[str] = None):
    """Listă publică de servicii active + info partener."""
    sb = _sb()
    q = (
        sb.table("partner_services")
        .select("id,name,description,duration_min,price_ron,partner_id,partners(id,name,city,address,phone)")
        .eq("active", True)
    )
    resp = q.execute()
    data = resp.data or []
    if city:
        city_lower = city.lower()
        data = [s for s in data if (s.get("partners") or {}).get("city", "").lower() == city_lower]
    return {"services": data}


@router.get("/partners")
def public_partners(city: Optional[str] = None):
    """Listă parteneri activi."""
    sb = _sb()
    q = sb.table("partners").select("id,name,city,address,phone,description").eq("active", True)
    resp = q.execute()
    data = resp.data or []
    if city:
        city_lower = city.lower()
        data = [p for p in data if p.get("city", "").lower() == city_lower]
    return {"partners": data}


@router.post("/rezervare")
def create_rezervare(inp: RezervareaIn, authorization: Optional[str] = Header(None)):
    client_email = _require_client_email(authorization)
    sb = _sb()
    row = {
        "client_email": client_email,
        "client_vehicle_plate": inp.vehicle_plate or "",
        "partner_id": inp.partner_id,
        "service_id": inp.service_id or None,
        "data_programata": inp.data_programata,
        "notes": inp.notes or "",
        "status": "pending",
    }
    resp = sb.table("rezervari").insert(row).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Rezervare eșuată")
    return {"ok": True, "rezervare": resp.data[0]}


@router.get("/rezervari/me")
def my_rezervari(authorization: Optional[str] = Header(None)):
    client_email = _require_client_email(authorization)
    sb = _sb()
    resp = (
        sb.table("rezervari")
        .select("*, partners(name,city), partner_services(name,duration_min,price_ron)")
        .eq("client_email", client_email)
        .order("data_programata", desc=True)
        .execute()
    )
    return {"rezervari": resp.data}
