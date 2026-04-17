"""
Public unit snapshot for QR /v/{UNIT_ID} — fără PII, fără token.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any, Dict, Optional
from urllib.parse import unquote

from backend import database as db
from backend import mlbr_file


def resolve_mlbr_row(mlbr_path: str) -> Optional[Dict[str, Any]]:
    raw = unquote(mlbr_path or "").strip()
    if not raw:
        return None
    candidates = [raw, mlbr_file.normalize_mlbr_id(raw)]
    seen: set = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        row = db.mlbr_get_by_mlbr_id(c)
        if row:
            return row
    return None


def _mask_vin(vin: str) -> str:
    v = re.sub(r"[^A-HJ-NPR-Z0-9]", "", (vin or "").upper())
    if len(v) < 4:
        return "—"
    return f"{v[:3]}…{v[-4:]}"


def _short_label(make: str, model: str, plate: str) -> str:
    parts = [p for p in [(make or "").strip(), (model or "").strip(), (plate or "").strip()] if p]
    return " ".join(parts) if parts else "Vehicul"


def _components_ok_from_row(row: Dict[str, Any], signature_valid: bool) -> bool:
    if not signature_valid:
        return False
    if not row:
        return True
    for key in ("blocked", "revoked", "suspended"):
        if row.get(key):
            return False
    return True


def build_public_unit_snapshot(unit_id: str) -> Optional[Dict[str, Any]]:
    """
    Returnează JSON serializabil pentru /api/public/unit/{unit_id}.
    None dacă unitatea nu există.
    """
    row = resolve_mlbr_row(unit_id)
    if not row:
        return None

    try:
        fd = json.loads(row["file_data"])
    except Exception:
        return None

    mid = mlbr_file.normalize_mlbr_id(fd.get("mlbr_id") or row.get("mlbr_id") or unit_id)
    vin = (row.get("vin") or fd.get("vin") or "").strip().upper()
    make = (fd.get("make") or "").strip()
    model = (fd.get("model") or "").strip()
    plate = (fd.get("plate") or "").strip()
    public_row = mlbr_file.public_safe_payload(dict(fd))
    signature_valid = mlbr_file.verify_mlbr_file(dict(fd))

    counts = db.public_timeline_counts_for_vin(vin) if vin else {"exo_n": 0, "card_n": 0}
    total_records = int(counts.get("exo_n", 0)) + int(counts.get("card_n", 0))

    last_service_summary: Optional[str] = None
    last_service_at: Optional[str] = None
    if vin:
        exo = db.get_exo_insights(vin, limit=1)
        if exo:
            t = (exo[0].get("insight_text") or "").strip()
            last_service_summary = (t[:280] + "…") if len(t) > 280 else t or None
            last_service_at = exo[0].get("created_at")

    components_ok = _components_ok_from_row(public_row, signature_valid)
    status_label = "Istoric Valid" if components_ok else "Verificare necesară"

    return {
        "unit_id": mid,
        "make": make,
        "model": model,
        "plate_display": plate,
        "vin_masked": _mask_vin(vin),
        "label_short": _short_label(make, model, plate),
        "last_service_summary": last_service_summary,
        "last_service_at": last_service_at,
        "components_ok": components_ok,
        "signature_valid": signature_valid,
        "status_label": status_label,
        "recent_records_total": total_records,
        "recent_breakdown": {
            "exo_insights": int(counts.get("exo_n", 0)),
            "insight_cards": int(counts.get("card_n", 0)),
        },
        "public": public_row,
    }


def og_title_for_snapshot(s: Dict[str, Any]) -> str:
    lbl = s.get("label_short") or "Vehicul"
    st = s.get("status_label") or "Verificare"
    return f"Verificare Mulberry ID: {lbl} - {st}"


def render_verify_html_page(s: Dict[str, Any], api_base: str) -> str:
    """HTML minimal cu meta OG server-side (WhatsApp / preview)."""
    title = html.escape(og_title_for_snapshot(s))
    desc = html.escape(
        f"{s.get('recent_records_total', 0)} înregistrări recente în istoricul public Mulberry. "
        f"Ultimul eveniment: {(s.get('last_service_summary') or '—')[:120]}"
    )
    unit = html.escape(s.get("unit_id") or "")
    make = html.escape(s.get("make") or "—")
    model = html.escape(s.get("model") or "—")
    plate = html.escape(s.get("plate_display") or "—")
    vin_m = html.escape(s.get("vin_masked") or "—")
    last = html.escape(s.get("last_service_summary") or "—")
    status = html.escape(s.get("status_label") or "—")
    nrec = int(s.get("recent_records_total") or 0)
    ok = bool(s.get("components_ok"))
    badge = "OK" if ok else "!"

    logo = html.escape(f"{api_base.rstrip('/')}/assets/mulberry-logo.png")

    return f"""<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <meta name="description" content="{desc}"/>
  <meta property="og:type" content="website"/>
  <meta property="og:title" content="{title}"/>
  <meta property="og:description" content="{desc}"/>
  <meta property="og:image" content="{logo}"/>
  <meta name="twitter:card" content="summary_large_image"/>
  <meta name="twitter:title" content="{title}"/>
  <meta name="twitter:description" content="{desc}"/>
  <meta name="twitter:image" content="{logo}"/>
  <style>
    :root {{ --bg:#0f1419; --card:#1a222c; --text:#e8eef4; --muted:#8b9aab; --accent:#c9a227; --ok:#22c55e; --warn:#f59e0b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }}
    .wrap {{ max-width:420px; margin:0 auto; padding:24px 20px 48px; }}
    .logo {{ width:120px; height:auto; display:block; margin:0 auto 20px; }}
    h1 {{ font-size:1.1rem; font-weight:600; text-align:center; margin:0 0 8px; line-height:1.35; }}
    .sub {{ text-align:center; color:var(--muted); font-size:0.85rem; margin-bottom:24px; }}
    .card {{ background:var(--card); border-radius:16px; padding:20px; margin-bottom:16px; border:1px solid rgba(255,255,255,.06); }}
    .row {{ display:flex; justify-content:space-between; gap:12px; padding:8px 0; border-bottom:1px solid rgba(255,255,255,.06); font-size:0.9rem; }}
    .row:last-child {{ border-bottom:none; }}
    .k {{ color:var(--muted); }}
    .badge {{ display:inline-flex; align-items:center; justify-content:center; min-width:36px; height:36px; border-radius:10px; font-weight:700; font-size:0.85rem;
      background:{('#14532d' if ok else '#713f12')}; color:{('var(--ok)' if ok else 'var(--warn)')}; }}
    .records {{ text-align:center; font-size:2rem; font-weight:700; color:var(--accent); margin:8px 0 4px; }}
    .records-cap {{ text-align:center; color:var(--muted); font-size:0.8rem; margin-bottom:16px; }}
    .last {{ font-size:0.88rem; line-height:1.45; color:var(--text); background:rgba(0,0,0,.2); padding:12px; border-radius:10px; margin-top:12px; }}
    .cta {{ display:block; width:100%; text-align:center; text-decoration:none; background:linear-gradient(180deg, #d4af37, #a67c00); color:#0f1419; font-weight:700;
      font-size:1rem; padding:16px 20px; border-radius:14px; margin-top:24px; box-shadow:0 4px 20px rgba(201,162,39,.35); }}
    .cta:active {{ opacity:0.92; }}
    footer {{ text-align:center; color:var(--muted); font-size:0.75rem; margin-top:32px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <img class="logo" src="{logo}" alt="Mulberry"/>
    <h1>{title}</h1>
    <p class="sub">ID unitate: <strong>{unit}</strong></p>
    <div class="card">
      <div class="row"><span class="k">Marcă</span><span>{make}</span></div>
      <div class="row"><span class="k">Model</span><span>{model}</span></div>
      <div class="row"><span class="k">Număr</span><span>{plate}</span></div>
      <div class="row"><span class="k">VIN (parțial)</span><span>{vin_m}</span></div>
      <div class="row"><span class="k">Componente scanate</span><span class="badge">{badge}</span></div>
      <div class="row"><span class="k">Status</span><span>{status}</span></div>
      <p class="records">{nrec}</p>
      <p class="records-cap">înregistrări / articole în istoricul recent public</p>
      <div class="last"><strong>Ultimul eveniment</strong><br/>{last}</div>
    </div>
    <a class="cta" href="https://mulberry.autos/mulberry.html">Vrei raportul complet? Descarcă Mulberry App</a>
    <footer>Verificare publică Mulberry · fără date personale ale posesorului</footer>
  </div>
</body>
</html>"""
