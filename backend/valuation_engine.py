"""
Evaluare piață + SoftScore „real” — agregare prețuri publice (Autovit) + formulă ponderată.

Notă: Autovit poate schimba HTML-ul; folosiți rezultatele ca indicii, nu ca ofertă fermă.
Respectați Termenii Autovit și limitați frecvența request-urilor (cache recomandat în producție).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from backend.vehicle_dto import MulberryVehicleDTO

import requests
from bs4 import BeautifulSoup

# Surse documentate (URL-uri de referință — nu toate sunt scrape-uite automat)
VALUATION_SOURCES = {
    "autovit": "https://www.autovit.ro/",
    "bnr_fx": "https://www.bnr.ro/nbrfxrates.xml",
}

DEFAULT_UA = "Mozilla/5.0 (compatible; MulberryEXO/2.6; +https://mulberry.local)"

# Întrebare stabilă pentru cache DB (vehicle_insights) — SoftScore depreciere multi-factor v1
SOFTSCORE_INSIGHT_QUESTION_V1 = "MulberryEXO · SoftScore multi-factor v1"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower().strip()).strip("-")


def _parse_price_text(text: str) -> Optional[int]:
    if not text:
        return None
    t = text.replace("\xa0", " ").replace(" ", "").replace(".", "").replace(",", ".")
    digits = "".join(ch for ch in t if ch.isdigit())
    if not digits:
        return None
    try:
        v = int(digits)
    except ValueError:
        return None
    # Autovit RO: prețuri adesea în EUR sau RON — euristică
    if 500 < v < 200000:
        return v
    return None


def get_market_prices_autovit(
    make: str,
    model: str,
    year: int,
    km: int,
    timeout: float = 18.0,
) -> Dict[str, Any]:
    """
    Încearcă să extragă prețuri din listări Autovit pentru marcă/model aproximativ.

    Returnează dict cu min/max/avg/median în unitatea detectată pe pagină (de obicei EUR sau RON).
    """
    make_slug = _slug(make) or "autoturisme"
    model_slug = _slug(model) or make_slug
    # URL tip listă Autovit
    url = f"https://www.autovit.ro/autoturisme/{make_slug}/{model_slug}"
    params = {
        "search[filter_float_year:from]": max(1990, year - 1),
        "search[filter_float_year:to]": min(datetime.now().year + 1, year + 1),
        "search[filter_float_mileage:to]": max(0, km + 30000),
    }
    headers = {"User-Agent": DEFAULT_UA, "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        return {"error": str(e), "prices": [], "source": "autovit.ro"}

    soup = BeautifulSoup(r.text, "html.parser")
    prices: List[int] = []

    # Selectori comuni (evoluează în timp)
    for sel in (
        '[data-testid="ad-price-container"]',
        '[data-testid="price-value"]',
        "span.offer-price__number",
        "h3.offer-price",
        ".offer-item-price",
        '[data-testid="ad-price"]',
    ):
        for el in soup.select(sel):
            p = _parse_price_text(el.get_text(" ", strip=True))
            if p:
                prices.append(p)

    # Fallback: orice număr care arată a preț în EUR/RON în main
    if not prices:
        for m in re.finditer(r"(\d{1,3}(?:[.\s]\d{3})+|\d{4,6})\s*(?:EUR|€|RON|lei)?", r.text, re.I):
            p = _parse_price_text(m.group(1))
            if p:
                prices.append(p)

    if not prices:
        return {
            "error": "Nu s-au putut extrage prețuri (structură pagină sau zero rezultate).",
            "prices": [],
            "source": "autovit.ro",
        }

    prices = sorted(set(prices))
    mid = len(prices) // 2
    median = prices[mid] if prices else 0
    return {
        "count": len(prices),
        "min": min(prices),
        "max": max(prices),
        "avg": int(sum(prices) / len(prices)),
        "median": median,
        "source": "autovit.ro",
        "currency_hint": "mixed_or_page_default",
    }


def calculate_real_softscore(
    vin: str,
    make: str,
    model: str,
    year: int,
    km: int,
    docs_verified: int,
    docs_total: int,
    rca_days: Optional[int],
    itp_days: Optional[int],
    market_data: Optional[Dict[str, Any]],
    owners_penalty: float = 0.0,
    recall_active: bool = False,
) -> Dict[str, Any]:
    """
    SoftScore 0–100 — componente care se adună la maxim 100:
    - documente: max 15
    - stare_mecanica (km + vârstă + urgență RCA/ITP în cadrul plafonului): max 25
    - valoare piață (date Autovit disponibile): max 30
    - istoric proprietari: max 15 (penalizare incrementală)
    - recall: max 15 puncte dacă nu există recall activ; 0 dacă există (penalizare)
    """
    breakdown: Dict[str, float] = {}

    dt = max(docs_total, 1)
    doc_part = min(15.0, (docs_verified / dt) * 15.0)
    breakdown["documente"] = round(doc_part, 1)

    # RCA / ITP: contribuție la „stare mecanică” (max 5 din 25)
    def _urgency_days(d: Optional[int]) -> float:
        if d is None:
            return 2.5
        if d < 0:
            return 0.0
        return max(0.0, min(2.5, d / 36.5))

    rca_s = _urgency_days(rca_days)
    itp_s = _urgency_days(itp_days)
    legal_sub = min(5.0, rca_s + itp_s)

    km = max(0, int(km))
    if km <= 100000:
        km_sub = 15.0
    elif km >= 200000:
        km_sub = 0.0
    else:
        km_sub = 15.0 * (1.0 - (km - 100000) / 100000.0)

    age = max(0, datetime.now().year - int(year or datetime.now().year))
    age_sub = max(0.0, 5.0 - (age * 0.25))

    mech_part = min(25.0, km_sub + age_sub + legal_sub)
    breakdown["stare_mecanica"] = round(mech_part, 1)

    if market_data and not market_data.get("error") and market_data.get("count", 0) > 0:
        market_part = 30.0
    else:
        market_part = 10.0
    breakdown["piata"] = round(market_part, 1)

    own_p = max(0.0, min(15.0, owners_penalty))
    owners_part = 15.0 - own_p
    breakdown["proprietari"] = round(owners_part, 1)

    recall_part = 0.0 if recall_active else 15.0
    breakdown["recall_siguranta"] = round(recall_part, 1)

    score = doc_part + mech_part + market_part + owners_part + recall_part
    total = max(0.0, min(100.0, round(score, 2)))
    status_health = (
        "Excelent — vehicul în stare foarte bună"
        if total >= 80
        else "Bun — câteva îmbunătățiri posibile"
        if total >= 60
        else "Atenție — verifică documentele și starea"
        if total >= 40
        else "Critic — necesită atenție urgentă"
    )

    return {
        "soft_score": total,
        "breakdown": breakdown,
        "market_data": market_data or {},
        "status_health": status_health,
        "vin": (vin or "").strip().upper(),
    }


def _days_until_iso(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    s = str(date_str).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            return (d - date.today()).days
        except ValueError:
            continue
    return None


def _year_from_vehicle_an(an: Optional[Any], *, fallback: int) -> int:
    if an is None or str(an).strip() == "":
        return fallback
    try:
        return int(str(an).strip()[:4])
    except (TypeError, ValueError):
        return fallback


def _market_base_from_intel_json(intel_row: Optional[Dict[str, Any]]) -> Optional[float]:
    """Extrage preț referință din `market_intel_synthesis` dacă JSON-ul conține câmpuri numerice."""
    if not intel_row:
        return None
    raw = intel_row.get("synthesis_json") or ""
    if not (raw and str(raw).strip()):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    for key in ("pret_mediu_eur", "estimated_median_eur", "pret_referinta_eur", "market_base_eur"):
        v = data.get(key)
        if v is None:
            continue
        try:
            x = float(v)
            if x > 0:
                return x
        except (TypeError, ValueError):
            continue
    return None


def resolve_market_base_eur(
    vehicle: MulberryVehicleDTO,
    intel_row: Optional[Dict[str, Any]] = None,
) -> Tuple[float, str]:
    """
    Preț_Bază pentru SoftScore: încearcă câmpuri numerice din sinteza market intel,
    apoi median Autovit, apoi estimare conservatoare.
    """
    b = _market_base_from_intel_json(intel_row)
    if b and b > 0:
        return round(b, 2), "market_intel_synthesis"

    y = _year_from_vehicle_an(getattr(vehicle, "an", None), fallback=datetime.now().year)
    km = int(getattr(vehicle, "km_actuali", None) or 0)
    make = getattr(vehicle, "marca", None) or ""
    model = getattr(vehicle, "model", None) or ""
    m = get_market_prices_autovit(str(make), str(model), y, km)
    if m and not m.get("error") and m.get("median"):
        med = float(m["median"])
        if med > 80000:
            med = med / 5.0
        return round(max(300.0, med), 2), "autovit_median"
    return 3200.0, "default_estimate"


def calculate_softscore(
    vehicle: MulberryVehicleDTO,
    market_avg_eur: float,
    *,
    current_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Depreciere multi-factor (0–100 puncte): 100 − (vârstă + km + documente).

    - Vârstă: 2 puncte pentru fiecare an peste 15 ani.
    - Km: 1 punct pentru fiecare 20.000 km peste 150.000.
    - Documente: +10 puncte penalizare (scăzute din 100) dacă ITP sau RCA expiră în ≤30 zile sau sunt expirate.
    """
    cy = int(current_year or datetime.now().year)
    year = _year_from_vehicle_an(getattr(vehicle, "an", None), fallback=cy)
    age_years = max(0, cy - year)
    pen_varsta = max(0.0, float(age_years - 15)) * 2.0

    km = int(getattr(vehicle, "km_actuali", None) or 0)
    pen_km = max(0.0, (float(km) - 150_000.0) / 20_000.0)

    rca_d = _days_until_iso(getattr(vehicle, "rca_expiry", None))
    itp_d = _days_until_iso(getattr(vehicle, "itp_expiry", None))
    pen_docs = 0.0
    for d in (rca_d, itp_d):
        if d is not None and d <= 30:
            pen_docs = 10.0
            break

    total_pen = pen_varsta + pen_km + pen_docs
    score = max(0.0, min(100.0, round(100.0 - total_pen, 2)))
    base = max(0.01, float(market_avg_eur))
    market_value = round(base * (score / 100.0), 2)

    if score > 80:
        band = "excellent"
        band_ro = "Mașină excelentă pe axa uzură — estimare peste pragul mediu al pieței pentru profilul dat."
    elif score >= 50:
        band = "normal"
        band_ro = "Stare normală de uzură — aliniere așteptată la piața SH."
    else:
        band = "poor"
        band_ro = "Scor scăzut — posibile investiții majore sau profil „cazan”; verificare histoire și buget reparații."

    label = f"{(vehicle.marca or '').strip()} {(vehicle.model or '').strip()}".strip() or "vehicul"

    breakdown = {
        "pen_varsta": round(pen_varsta, 2),
        "pen_km": round(pen_km, 2),
        "pen_documente": round(pen_docs, 2),
        "age_years": age_years,
        "km": km,
        "rca_days": rca_d,
        "itp_days": itp_d,
    }

    explain_parts: List[str] = []
    if pen_varsta > 0:
        explain_parts.append(f"vechimea de {age_years} ani aduce {pen_varsta:.1f} pt. penalizare")
    if pen_km > 0:
        explain_parts.append(f"rulajul {km} km aduce {pen_km:.1f} pt.")
    if pen_docs > 0:
        explain_parts.append("ITP/RCA în urgență (<30 zile sau expirate) −10 pt.")
    explain_tail = "; ".join(explain_parts) if explain_parts else "fără penalizări majore pe axele definite."

    reply = (
        f"SoftScore-ul pentru {label} este {score}/100. "
        f"{band_ro} "
        f"Valoare estimativă ajustată: ~{market_value} EUR (preț bază {base:.0f} EUR × scor/100). "
        f"Detalii: {explain_tail}"
    )

    return {
        "softscore": score,
        "market_value_eur": market_value,
        "market_base_eur": round(base, 2),
        "currency": "EUR",
        "health_band": band,
        "band_label_ro": band_ro,
        "breakdown": breakdown,
        "reply": reply,
    }


def snapshot_for_vehicle(car: Any, brain: Any) -> Dict[str, Any]:
    """
    Construiește snapshot evaluare pentru integrare în assistant / API.
    `car` = CarRow sau obiect cu make, model, year, km_actuali, rca_expiry, itp_expiry
    `brain` = MulberryBrain sau None
    """
    make = getattr(car, "make", None) or ""
    model = getattr(car, "model", None) or ""
    year = getattr(car, "year", None)
    try:
        y = int(str(year)) if year is not None else datetime.now().year
    except Exception:
        y = datetime.now().year
    km = int(getattr(car, "km_actuali", None) or 0)

    docs_verified = 0
    docs_total = 0
    if brain and getattr(brain, "cloud_files", None):
        docs_total = len(brain.cloud_files)
        docs_verified = sum(1 for d in brain.cloud_files if getattr(d, "verified", False))

    rca_days = _days_until_iso(getattr(car, "rca_expiry", None))
    itp_days = _days_until_iso(getattr(car, "itp_expiry", None))

    market = get_market_prices_autovit(make, model, y, km)
    soft = calculate_real_softscore(
        vin=getattr(car, "vin", "") or "",
        make=make,
        model=model,
        year=y,
        km=km,
        docs_verified=docs_verified,
        docs_total=docs_total,
        rca_days=rca_days,
        itp_days=itp_days,
        market_data=market,
        owners_penalty=0.0,
        recall_active=False,
    )
    return {"market": market, "soft_score_real": soft}
