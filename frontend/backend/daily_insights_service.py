"""
Daily Insights — 3 carduri zilnice redactate de MulberryEXO: tehnologii producător, știri model, probleme+soluții.
Context: vehicul + fragmente research (RSS) + sinteză market intel Fabia 6Y când e cazul.
Salvare în `daily_insight_cards`; digest în `exo_daily_insights`.
Job nocturn înainte de 06:00: `run_nightly_daily_insights()` din scheduler.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

from backend import ai_proxy
from backend import database
from backend import rag_qdata

# Catalog intern — URL-uri reale (legacy); selecția nu inventează domenii noi.
INSIGHT_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "rar_itp",
        "tag": "AI INSIGHT",
        "title_default": "ITP în România — ghid RAR",
        "url": "https://www.rarom.ro/faq/afla-tot-ce-trebuie-sa-stii-despre-itp/",
        "image_url": "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=900&q=80&auto=format&fit=crop",
        "kind": "article",
        "keywords": ["itp", "rar", "inspecție", "statie"],
    },
    {
        "id": "wiki_fabia",
        "tag": "AI INSIGHT",
        "title_default": "Istoric și generații Škoda Fabia",
        "url": "https://en.wikipedia.org/wiki/%C5%A0koda_Fabia",
        "image_url": "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=900&q=80&auto=format&fit=crop",
        "kind": "article",
        "keywords": ["skoda", "fabia", "6y", "hatch"],
    },
    {
        "id": "skoda_ro",
        "tag": "PROMO",
        "title_default": "Škoda România — noutăți și service",
        "url": "https://www.skoda-auto.ro/",
        "image_url": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=900&q=80&auto=format&fit=crop",
        "kind": "promo",
        "keywords": ["skoda", "service", "ofertă", "revizie"],
    },
    {
        "id": "softscore_edu",
        "tag": "AI INSIGHT",
        "title_default": "Cum îți menții valoarea vehiculului (SoftScore)",
        "url": "https://en.wikipedia.org/wiki/Preventive_maintenance",
        "image_url": "https://images.unsplash.com/photo-1449965408869-eaa3f722e40d?w=900&q=80&auto=format&fit=crop",
        "kind": "article",
        "keywords": ["valoare", "întreținere", "scor", "documente"],
    },
    {
        "id": "promo_service_partner",
        "tag": "PROMO",
        "title_default": "Revizie periodică — întreabă un service partener",
        "url": "https://www.rarom.ro/",
        "image_url": "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?w=900&q=80&auto=format&fit=crop",
        "kind": "promo",
        "keywords": ["revizie", "service", "mentenanță", "ulei"],
    },
    {
        "id": "drpciv_rca",
        "tag": "AI INSIGHT",
        "title_default": "Asigurare RCA — informații oficiale",
        "url": "https://www.drpciv.ro/",
        "image_url": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=900&q=80&auto=format&fit=crop",
        "kind": "article",
        "keywords": ["rca", "asigurare", "legislație"],
    },
]


DAILY_GROQ_SYSTEM = """Ești curator MulberryEXO (România). Primești CATALOG_JSON (articole/promo cu id și url reale) și un REZUMAT_VEHICUL.
Selectează 3-5 intrări relevante pentru șofer. Poți adapta titlul (max 90 caractere) ca să menționezi marca/modelul dacă are sens.
REGULI STRICTE:
- Răspunde DOAR cu JSON valid, fără markdown, fără text în afara JSON.
- Nu inventa URL-uri: fiecare card folosește catalog_id din catalog (id existent).
- tag pentru fiecare card: \"AI INSIGHT\" sau \"PROMO\" (aliniat la intrarea din catalog).
- kind: \"article\" sau \"promo\".

Format exact:
{\"banner\":\"o propoziție scurtă în română despre ce ai găsit\",\"cards\":[{\"catalog_id\":\"id\",\"title\":\"titlu\",\"tag\":\"AI INSIGHT\",\"kind\":\"article\"}]}
"""

READING_ENRICH_SYSTEM = """Ești redactor MulberryEXO (România), ton inginer auto — creierul aplicației este MulberryEXO; nu menționa alte motoare sau furnizori.
Primești o listă de carduri (titlu, url temă, kind) și context vehicul.
Pentru FIECARE card, în EXACT aceeași ordine ca în listă, scrie:
- essence: max 240 caractere, rezumat dens (o singură propoziție sau două scurte), fără markdown.
- reading: articol în română, maximum 380 cuvinte (sub 2 minute citire), MINIMUM 3 paragrafe separate cu \\n\\n, cu argumente (nu slogane). Fără markdown, fără titluri #, fără bullet.
  Pentru teme de tehnologie la producător (ex. Škoda): denumește tehnologia, codul sau denumirea de proiect când e cazul, funcția în vehicul, de ce e utilă sau populară.

Răspunde DOAR JSON valid:
{\"items\":[{\"essence\":\"...\",\"reading\":\"...\"}]}
"""

TRIPLE_SLOTS_ORDER = ("brand_tech", "model_news", "model_issues")

TRIPLE_IMAGE_URLS = {
    "brand_tech": "https://images.unsplash.com/photo-1487754180451-c456f29a4ddc?w=900&q=80&auto=format&fit=crop",
    "model_news": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=900&q=80&auto=format&fit=crop",
    "model_issues": "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?w=900&q=80&auto=format&fit=crop",
}

# Imagini editoriale de rezervă (cadru tip cotidian) când og:image lipsește
UNSPLASH_NEWS_FRAMES = [
    "https://images.unsplash.com/photo-1545239351-1141bd82e8a6?w=1200&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1549921296-3b8b0e3e7e0e?w=1200&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=1200&q=80&auto=format&fit=crop",
]
UNSPLASH_SERVICE_FRAMES = [
    "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?w=1200&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=1200&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=1200&q=80&auto=format&fit=crop",
]

# Potrivire pe titlu+conținut (fără diacritice obligatoriu în keywords)
NEWS_ROMANIA_KEYWORDS: Tuple[str, ...] = (
    "benzin",
    "motorin",
    "pret",
    "combustibil",
    "pomp",
    "peco",
    "petrom",
    "rompetrol",
    "guvern",
    "ordonant",
    "lege",
    "minister",
    "drpciv",
    "rar",
    "itp",
    "taxa",
    "vignet",
    "rabla",
    "regulament",
    "anaf",
    "rca",
    "asigur",
    "circulatie",
    "accident",
    "roviniet",
    "poluare",
    "norme",
    "ue",
)

SERVICE_TOPIC_KEYWORDS: Tuple[str, ...] = (
    "recall",
    "defect",
    "problem",
    "service",
    "uzur",
    "pies",
    "demont",
    "repara",
    "garan",
    "fiabil",
    "turbo",
    "ambreiaj",
    "motor",
    "fran",
    "electro",
    "diagnostic",
    "rechemat",
    "campanie",
)

_OG_IMAGE_CACHE: Dict[str, Optional[str]] = {}


def _jsonl_load_recent(path: Path, max_lines: int = 220) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]
    except Exception:
        return []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _blob_matches_keywords(blob: str, kws: Tuple[str, ...]) -> bool:
    b = (blob or "").lower()
    return any(k in b for k in kws)


def _collect_articles_news(jsonl_path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for o in _jsonl_load_recent(jsonl_path):
        blob = (o.get("title") or "") + " " + (o.get("content") or "")[:950]
        if _blob_matches_keywords(blob, NEWS_ROMANIA_KEYWORDS):
            out.append(o)
        if len(out) >= 28:
            break
    return out


def _collect_articles_service(make: str, model: str, jsonl_path: Path) -> List[Dict[str, Any]]:
    toks = [t for t in re.split(r"\W+", f"{make} {model}".lower()) if len(t) >= 3]
    if not toks:
        toks = ["auto"]
    out: List[Dict[str, Any]] = []
    for o in _jsonl_load_recent(jsonl_path):
        blob = (o.get("title") or "") + " " + (o.get("content") or "")[:950]
        bl = blob.lower()
        if not any(t in bl for t in toks):
            continue
        if _blob_matches_keywords(bl, SERVICE_TOPIC_KEYWORDS) or "rechemat" in bl or "problema" in bl:
            out.append(o)
        if len(out) >= 28:
            break
    return out


def _try_fetch_og_image(url: str) -> Optional[str]:
    if not url or not str(url).startswith("http"):
        return None
    try:
        import httpx

        with httpx.Client(timeout=4.5, follow_redirects=True) as client:
            r = client.get(
                url,
                headers={"User-Agent": "MulberryEXO/1.0 (+https://mulberry.io; daily-insights)"},
            )
            if r.status_code >= 400:
                return None
            html = r.text[:280000]
        for pattern in (
            r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'"og:image"\s*:\s*"([^"]+)"',
        ):
            m = re.search(pattern, html, re.I)
            if m:
                return m.group(1).strip()[:2000]
    except Exception:
        return None
    return None


def _og_image_with_budget(url: str, budget: List[int]) -> Optional[str]:
    if os.getenv("DAILY_INSIGHTS_OG_IMAGES", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    if not url or not str(url).startswith("http"):
        return None
    if url in _OG_IMAGE_CACHE:
        return _OG_IMAGE_CACHE[url]
    if budget[0] <= 0:
        _OG_IMAGE_CACHE[url] = None
        return None
    img = _try_fetch_og_image(url)
    _OG_IMAGE_CACHE[url] = img
    if img:
        budget[0] -= 1
    return img


def _merge_unique_urls(primary: List[str], fallback: List[str], max_n: int = 4) -> List[str]:
    seen = set()
    out: List[str] = []
    for u in primary + fallback:
        if not u or not str(u).startswith("http") or u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= max_n:
            break
    return out


def _build_frames_news(budget: List[int], jsonl_path: Path) -> List[str]:
    arts = _collect_articles_news(jsonl_path)
    og: List[str] = []
    for a in arts:
        u = (a.get("url") or "").strip()
        if not u:
            continue
        im = _og_image_with_budget(u, budget)
        if im:
            og.append(im)
        if len(og) >= 3:
            break
    return _merge_unique_urls(og, list(UNSPLASH_NEWS_FRAMES), 4)


def _build_frames_service(make: str, model: str, budget: List[int], jsonl_path: Path) -> List[str]:
    arts = _collect_articles_service(make, model, jsonl_path)
    og: List[str] = []
    for a in arts:
        u = (a.get("url") or "").strip()
        if not u:
            continue
        im = _og_image_with_budget(u, budget)
        if im:
            og.append(im)
        if len(og) >= 3:
            break
    return _merge_unique_urls(og, list(UNSPLASH_SERVICE_FRAMES), 4)


def _build_frames_tech() -> List[str]:
    return [
        "https://images.unsplash.com/photo-1487754180451-c456f29a4ddc?w=1200&q=80&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=1200&q=80&auto=format&fit=crop",
    ]


def _research_block_romania_news(jsonl_path: Path) -> str:
    arts = _collect_articles_news(jsonl_path)
    if not arts:
        return ""
    lines: List[str] = []
    for a in arts[:10]:
        lines.append(
            f"- [{a.get('source') or '?'}] {(a.get('title') or '')[:150]} | {a.get('url') or ''}"
        )
    return "CONTEXT_STIRI_ROMANIA (combustibil, prețuri, guvern, reglementări oficiale, RAR/DRPCIV — din flux research):\n" + "\n".join(lines)


def _research_block_service(make: str, model: str, jsonl_path: Path) -> str:
    arts = _collect_articles_service(make, model, jsonl_path)
    if not arts:
        return ""
    lines: List[str] = []
    for a in arts[:10]:
        lines.append(
            f"- [{a.get('source') or '?'}] {(a.get('title') or '')[:150]} | {a.get('url') or ''}"
        )
    return "CONTEXT_SERVICE_RECALL (probleme, recall, piese — din flux research, legat de marcă/model):\n" + "\n".join(lines)


def _apply_frame_images_to_cards(cards: List[Dict[str, Any]], make: str, model: str) -> None:
    path = Path(__file__).resolve().parent / "research_data" / "articles_recent.jsonl"
    try:
        cap = int(os.getenv("DAILY_INSIGHTS_MAX_OG_FETCH", "6"))
    except ValueError:
        cap = 6
    budget = [max(0, min(cap, 12))]
    for c in cards:
        sl = (c.get("_slot") or "").strip()
        if sl == "brand_tech":
            c["frame_images"] = _build_frames_tech()
        elif sl == "model_news":
            c["frame_images"] = _build_frames_news(budget, path)
        elif sl == "model_issues":
            c["frame_images"] = _build_frames_service(make, model, budget, path)
        else:
            c["frame_images"] = c.get("frame_images") or []
        imgs = c.get("frame_images") or []
        if imgs:
            c["image_url"] = imgs[0]


DAILY_TRIPLE_SYSTEM = """Ești redactor senior MulberryEXO (România). MulberryEXO este creierul aplicației; redactezi articole tematice auto pentru șofer. Nu menționa alte motoare AI sau furnizori externi. Generezi EXACT 3 carduri.

Ordinea și rolul cardurilor (câmpul \"slot\" trebuie să fie exact unul din: brand_tech, model_news, model_issues):

1) brand_tech — Tehnologii și direcții de produs ale PRODUCĂTORULUI (marcă din profil). Exemplu Škoda: explică tehnologia (nume comercial și, când e relevant, cod sau denumire de platformă/proiect), ce face în mașină, de ce e utilă sau populară, cum se poziționează față de concurență. Nu repeta unghiul titlurilor din SUBIECTE_DE_EVITAT.

2) model_news — SECȚIUNEA ȘTIRI: articol despre contextul din România pentru șoferul de {marcă/model din profil}. OBLIGATORIU integrează (acolo unde e relevant, din CONTEXT_STIRI_ROMANIA): evoluția prețurilor la benzină/motorină sau la carburanți; anunțuri guvernamentale sau reglementări oficiale (taxe, vignetă, RAR, DRPCIV, circulație, mediu) care ating proprietarii de autovehicule; leagă știrile de modelul din profil sau de segmentul lui. Ton jurnalistic clar, fără speculații de preț fără sursă — folosește reperele din CONTEXT. Titlul să fie atractiv, de tip cotidian.

3) model_issues — SECȚIUNEA SERVICE: probleme noi sau recurente întâlnite la acest model/generație; ce ar trebui proprietarul să evite (obiceiuri, amânări, piese nepotrivite); calități reale ale vehiculului (spațiu, motor, costuri de întreținere) demonstrate cu argumente; ce îl ajută concret pe proprietar (întreținere, verificări, unde merită investiția). Folosește CONTEXT_SERVICE_RECALL dacă există. Nu induce panică; ton educativ, demonstrativ.

Stil articol (toate cardurile):
- Fiecare \"reading\" = MINIMUM 3 paragrafe, separate cu \\n\\n, cu argumente (nu doar liste de idei).
- Maximum ~380 cuvinte per card (sub 2 minute citire).
- \"essence\": maximum 220 caractere per card.
- \"tag\": TECH, ȘTIRI, SERVICE (card 1–3).
- Română, fără markdown, fără #, fără bullet în JSON.
- RESEARCH_SNIPPETS, CONTEXT_STIRI_ROMANIA, CONTEXT_SERVICE_RECALL, MARKET_INTEL: inspirație factuală; sintetizează, nu copia.

Răspunde DOAR JSON valid:
{\"banner\":\"string\",\"cards\":[{\"slot\":\"brand_tech\",\"tag\":\"TECH\",\"title\":\"\",\"essence\":\"\",\"reading\":\"\"},{\"slot\":\"model_news\",...},{\"slot\":\"model_issues\",...}]}
"""


def _clamp_reading_words(text: str, max_words: int = 380) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    words = t.split()
    if len(words) <= max_words:
        return t
    return " ".join(words[:max_words]).rstrip() + "…"


def _manufacturer_official_url(make: str) -> str:
    m = (make or "").strip().lower()
    if any(x in m for x in ("skoda", "škoda")):
        return "https://www.skoda-auto.ro/"
    if "dacia" in m:
        return "https://www.dacia.ro/"
    if "volkswagen" in m or m == "vw":
        return "https://www.volkswagen.ro/"
    if "bmw" in m:
        return "https://www.bmw.ro/"
    if "mercedes" in m:
        return "https://www.mercedes-benz.ro/"
    if "audi" in m:
        return "https://www.audi.ro/"
    if "renault" in m:
        return "https://www.renault.ro/"
    if "peugeot" in m:
        return "https://www.peugeot.ro/"
    if "ford" in m:
        return "https://www.ford.ro/"
    if "toyota" in m:
        return "https://www.toyota.ro/"
    return "https://www.google.com/search?q=" + quote_plus((make or "auto") + " site oficial")


def _url_for_model_news(make: str, model: str) -> str:
    q = " ".join(x for x in [(make or "").strip(), (model or "").strip()] if x)
    return "https://en.wikipedia.org/wiki/Special:Search?search=" + quote_plus(q or "automobile")


def _url_for_slot(slot: str, make: str, model: str) -> str:
    if slot == "brand_tech":
        return _manufacturer_official_url(make)
    if slot == "model_news":
        return _url_for_model_news(make, model)
    return "https://www.rarom.ro/"


def _is_skoda_fabia_profile(make: str, model: str, series: Optional[str]) -> bool:
    blob = f"{make} {model} {series or ''}".lower()
    return ("skoda" in blob or "škoda" in blob) and ("fabia" in blob or "6y" in blob)


def _market_intel_context_block(make: str, model: str, series: Optional[str]) -> str:
    if not _is_skoda_fabia_profile(make, model, series):
        return ""
    row = database.market_intel_get_synthesis(database.MODEL_KEY_SKODA_FABIA_6Y)
    if not row:
        return ""
    s = (row.get("synthesis_ro") or "").strip()
    if not s:
        return ""
    return "MARKET_INTEL (Fabia 6Y / Mk1 — sinteză internă Mulberry din surse enciclopedice):\n" + s[:2800]


def _research_snippets_from_jsonl(make: str, model: str, max_chars: int = 2600) -> str:
    p = Path(__file__).resolve().parent / "research_data" / "articles_recent.jsonl"
    if not p.is_file():
        return ""
    blob = f"{make} {model}".lower()
    toks = [t for t in re.split(r"\W+", blob) if len(t) >= 3]
    if not toks:
        toks = [blob[:20]]
    lines_out: List[str] = []
    try:
        raw_lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()[-120:]
    except Exception:
        return ""
    for line in reversed(raw_lines):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        title = (o.get("title") or "") + " " + (o.get("content") or "")[:800]
        tl = title.lower()
        if any(t in tl for t in toks):
            one = (o.get("title") or "")[:160] + ": " + (o.get("content") or "")[:420]
            one = re.sub(r"\s+", " ", one).strip()
            if one and one not in lines_out:
                lines_out.append(one)
        if sum(len(x) for x in lines_out) >= max_chars:
            break
    if not lines_out:
        return ""
    joined = "\n---\n".join(lines_out[:12])
    return "RESEARCH_SNIPPETS (flux RSS recent, filtrat pe marcă/model):\n" + joined[:max_chars]


def _materialize_triple_from_payload(
    payload: dict,
    make: str,
    model: str,
    series: Optional[str],
) -> Tuple[str, List[Dict[str, Any]]]:
    banner = (payload.get("banner") or "").strip() or "Recomandări zilnice MulberryEXO pentru profilul tău."
    raw_cards = payload.get("cards") or []
    by_slot: Dict[str, Dict[str, Any]] = {}
    for c in raw_cards:
        if not isinstance(c, dict):
            continue
        sl = (c.get("slot") or "").strip()
        if sl not in TRIPLE_SLOTS_ORDER:
            continue
        title = (c.get("title") or "").strip()
        if not title:
            continue
        tag = (c.get("tag") or "").strip() or (
            "TECH" if sl == "brand_tech" else ("ȘTIRI" if sl == "model_news" else "SERVICE")
        )
        essence = (c.get("essence") or "").strip()[:400]
        reading = _clamp_reading_words(c.get("reading") or "", 380)
        by_slot[sl] = {
            "title": title[:200],
            "url": _url_for_slot(sl, make, model),
            "image_url": TRIPLE_IMAGE_URLS.get(sl, TRIPLE_IMAGE_URLS["model_news"]),
            "tag": tag[:64],
            "kind": "article",
            "essence": essence,
            "reading_text": reading,
            "_slot": sl,
        }
    cards: List[Dict[str, Any]] = []
    for sl in TRIPLE_SLOTS_ORDER:
        if sl in by_slot:
            cards.append(by_slot[sl])
    return banner, cards


def _fallback_triple_cards(car_dict: Optional[Dict[str, Any]], prev_titles: List[str]) -> Tuple[str, List[Dict[str, Any]]]:
    make = str((car_dict or {}).get("make") or "vehicul").strip() or "vehicul"
    model = str((car_dict or {}).get("model") or "").strip()
    series = str((car_dict or {}).get("series") or "").strip() or None
    model_line = " ".join(x for x in [make, model] if x).strip() or make
    avoid = " ".join(prev_titles[:8]).lower()

    def _fresh(prefix: str, body: str) -> str:
        if body.lower() in avoid:
            return prefix + " (actualizare " + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ")"
        return body

    cards = [
        {
            "_slot": "brand_tech",
            "title": _fresh("tech", f"{make} — tehnologii și planuri de produs"),
            "url": _url_for_slot("brand_tech", make, model),
            "image_url": TRIPLE_IMAGE_URLS["brand_tech"],
            "tag": "TECH",
            "kind": "article",
            "essence": f"Rezumat orientativ despre direcția tehnologică a mărcii {make}.",
            "reading_text": _clamp_reading_words(
                f"MulberryEXO îți rezumă aici direcția tehnologică a mărcii {make}: platforme modulare, sisteme de asistență "
                f"și conectivitate — fără a înlocui comunicatele oficiale.\n\n"
                f"Pentru șoferul din România contează actualizările de software, disponibilitatea ADAS pe gamă și rețeaua "
                f"de service. Profilul tău ({model_line}) se raportează la aceste tendințe; urmărește istoricul de întreținere în aplicație.\n\n"
                f"Text generat local când redactarea MulberryEXO pe server nu e disponibilă; după sincronizare vei primi "
                f"articole cu minimum trei paragrafe și argumente tehnice (denumiri, rol, utilitate).",
                380,
            ),
        },
        {
            "_slot": "model_news",
            "title": _fresh("news", f"Știri și context: {model_line}"),
            "url": _url_for_slot("model_news", make, model),
            "image_url": TRIPLE_IMAGE_URLS["model_news"],
            "tag": "ȘTIRI",
            "kind": "article",
            "essence": f"Combustibil, reglementări și piață — pentru {model_line}.",
            "reading_text": _clamp_reading_words(
                f"Pentru șoferul din România, contează evoluția prețurilor la benzină și motorină, precum și cadrul legal — RAR, DRPCIV, vignetă, taxe și asigurări — care influențează costul total al vehiculului.\n\n"
                f"Leagă aceste tendințe de {model_line}: ce segment deservesc, și cum se reflectă în bugetul lunar (combustibil, taxe, întreținere).\n\n"
                f"Conținut MulberryEXO complet: articole cu surse din fluxul public și imagini în cadru după sincronizare.",
                380,
            ),
        },
        {
            "_slot": "model_issues",
            "title": _fresh("srv", f"Probleme uzuale și soluții — {model_line}"),
            "url": _url_for_slot("model_issues", make, model),
            "image_url": TRIPLE_IMAGE_URLS["model_issues"],
            "tag": "SERVICE",
            "kind": "article",
            "essence": f"Diagnostic orientativ și pași practici pentru {model_line}.",
            "reading_text": _clamp_reading_words(
                f"Pentru {model_line}, uzura ambreiajului în trafic urban, consumabile la intervale neregulate dacă istoricul lipsește "
                f"și suspensia pe drumuri denivelate sunt teme frecvente.\n\n"
                f"Soluții practice: inspecție la service autorizat, ulei și filtre la intervale recomandate, geometrie și direcție verificate. "
                f"Nu ignora supraîncălzirea sau bătăile la motor; Mulberry poate centraliza reminder-ele.\n\n"
                f"MulberryEXO redactează în producție diagnostice educate pe trei paragrafe; aici este variantă locală — confirmă mereu cu specialistul.",
                380,
            ),
        },
    ]
    _apply_frame_images_to_cards(cards, make, model)
    for c in cards:
        c.pop("_slot", None)
    return "Recomandări generale (mod fallback — articolele MulberryEXO complete după sincronizare).", cards


def _push_digest_to_exo(vin: str, cards: List[Dict[str, Any]]) -> None:
    if not cards:
        return
    try:
        titles = [str(c.get("title") or "") for c in cards]
        ess = [str(c.get("essence") or "") for c in cards]
        day = datetime.now(timezone.utc).date().isoformat()
        parts = [f"{t}: {(e or '')[:140]}" for t, e in zip(titles, ess)]
        digest = "Daily Insights MulberryEXO " + day + " — " + " | ".join(parts)
        database.insert_exo_insight(
            vin.strip().upper(),
            digest[:4500],
            insight_type="daily_insights_digest",
            raw_context=json.dumps(
                {"engine": "daily_insights_triple", "titles": titles, "day": day},
                ensure_ascii=False,
            )[:8000],
            engine="daily_insights_triple",
        )
    except Exception:
        pass


def _catalog_by_id() -> Dict[str, Dict[str, Any]]:
    return {c["id"]: c for c in INSIGHT_CATALOG if c.get("id")}


def _extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    s = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if fence:
        s = fence.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    i = s.find("{")
    j = s.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(s[i : j + 1])
        except json.JSONDecodeError:
            return None
    return None


def _vehicle_context_lines(vin: str) -> str:
    vin = (vin or "").strip().upper()
    lines: List[str] = []
    car = database.get_car_by_vin(vin)
    brain = database.get_vehicle_brain(vin)
    if car:
        lines.append(
            f"Vehicul: {car.make or '—'} {car.model or ''} {car.year or ''}, "
            f"{car.km_actuali if car.km_actuali is not None else '—'} km."
        )
    if brain:
        try:
            ss = float(getattr(brain, "soft_score", 0) or 0)
            lines.append(f"SoftScore brain: {ss:.1f}%. Stare: {getattr(brain, 'status_health', '—')}.")
        except Exception:
            pass
    try:
        hits = rag_qdata.query_vehicle_memory_for_message(vin, "întreținere consum valoare piață", n_results=1)
        if hits:
            t = re.sub(r"\s+", " ", (hits[0].get("text") or "").strip())[:450]
            if t:
                lines.append(f"Reper memorie vector (scurt): {t}")
    except Exception:
        pass
    return "\n".join(lines).strip() or "Fără detalii suplimentare."


def _fallback_pick_cards(car_dict: Optional[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """Fără apel MulberryEXO: potrivire simplă pe cuvinte cheie în marcă/model + intrări din catalog."""
    blob = " ".join(
        [
            str((car_dict or {}).get("make") or ""),
            str((car_dict or {}).get("model") or ""),
            str((car_dict or {}).get("series") or ""),
        ]
    ).lower()
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for c in INSIGHT_CATALOG:
        kws = [x.lower() for x in (c.get("keywords") or [])]
        score = sum(1 for k in kws if k and k in blob)
        if "skoda" in blob or "fabia" in blob:
            if "skoda" in " ".join(kws) or "fabia" in " ".join(kws):
                score += 2
        scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], INSIGHT_CATALOG.index(x[1])))
    picked = [x[1] for x in scored[:4]]
    if not picked:
        picked = INSIGHT_CATALOG[:4]
    cards_out: List[Dict[str, Any]] = []
    for c in picked:
        cards_out.append(
            {
                "title": c["title_default"],
                "url": c["url"],
                "image_url": c.get("image_url") or "",
                "tag": c.get("tag") or "AI INSIGHT",
                "kind": c.get("kind") or "article",
            }
        )
    banner = "Recomandări pentru vehiculul tău (selectate local)."
    return banner, cards_out


def _materialize_groq_cards(payload: dict) -> List[Dict[str, Any]]:
    cmap = _catalog_by_id()
    out: List[Dict[str, Any]] = []
    for c in payload.get("cards") or []:
        cid = (c.get("catalog_id") or "").strip()
        if cid not in cmap:
            continue
        base = cmap[cid]
        title = (c.get("title") or "").strip() or base["title_default"]
        out.append(
            {
                "title": title[:200],
                "url": base["url"],
                "image_url": (base.get("image_url") or "").strip(),
                "tag": (c.get("tag") or base.get("tag") or "AI INSIGHT")[:64],
                "kind": (c.get("kind") or base.get("kind") or "article")[:32],
            }
        )
        if len(out) >= 5:
            break
    return out


def _fallback_enrich_readings(cards: List[Dict[str, Any]]) -> None:
    """Completează essence/reading_text când redactarea MulberryEXO nu e disponibilă."""
    boiler = (
        "Material orientativ MulberryEXO: menține documentele la zi (RCA, ITP) și mentenanța periodică "
        "pentru valoarea vehiculului și SoftScore. Articolele complete au minimum trei paragrafe după sincronizare.\n\n"
        "Întrebări punctuale: deschide Mulberry Assistant din aplicație."
    )
    for c in cards:
        if not (c.get("essence") or "").strip():
            t = (c.get("title") or "").strip()
            c["essence"] = (t[:180] + "… — esență Mulberry pentru profilul tău.") if len(t) > 40 else (t + " — recomandare contextuală.")
        if not (c.get("reading_text") or "").strip():
            c["reading_text"] = boiler


def _enrich_cards_with_readings(cards: List[Dict[str, Any]], vehicle_ctx: str) -> None:
    """Adaugă essence + reading_text prin MulberryEXO (JSON structurat); modifică lista in-place."""
    if not cards:
        return
    if _env_skip_groq():
        _fallback_enrich_readings(cards)
        return
    slim = [{"title": c.get("title"), "url": c.get("url"), "kind": c.get("kind")} for c in cards]
    user_msg = (
        f"CONTEXT VEHICUL:\n{vehicle_ctx}\n\nCARDURI (această ordine):\n"
        f"{json.dumps(slim, ensure_ascii=False)}"
    )
    try:
        raw = ai_proxy.complete_simple(
            user_msg,
            system_override=READING_ENRICH_SYSTEM,
            task="json_structured",
            max_completion_tokens=8192,
        )
        payload = _extract_json_object(raw) or {}
        items = payload.get("items") or []
        for i, c in enumerate(cards):
            if i >= len(items):
                continue
            it = items[i] or {}
            ess = (it.get("essence") or "").strip()
            rd = (it.get("reading") or "").strip()
            if ess:
                c["essence"] = ess[:400]
            if rd:
                rd = _clamp_reading_words(rd, 380)
                if len(rd) > 4200:
                    rd = rd[:4200].rstrip() + "…"
                c["reading_text"] = rd
    except Exception:
        pass
    _fallback_enrich_readings(cards)


def refresh_daily_insights_for_vin(vin: str, user_id: Optional[int], car_dict: Optional[Dict[str, Any]] = None) -> Tuple[str, int]:
    """
    Regenerează 3 carduri (TECH / ȘTIRI / SERVICE) pentru un VIN. Returnează (banner, număr_carduri_scrise).
    """
    vin = (vin or "").strip().upper()
    if not vin:
        return "", 0

    if car_dict is None:
        row = database.get_car_by_vin(vin)
        if row:
            car_dict = {
                "make": row.make,
                "model": row.model,
                "series": row.series,
                "year": row.year,
                "km_actuali": row.km_actuali,
            }

    make = str((car_dict or {}).get("make") or "").strip() or "vehicul"
    model = str((car_dict or {}).get("model") or "").strip()
    series = (car_dict or {}).get("series")
    series_s = str(series).strip() if series is not None else ""
    year = (car_dict or {}).get("year")
    km = (car_dict or {}).get("km_actuali")

    prev_titles = database.get_recent_daily_insight_titles(vin, limit=24)
    avoid_lines = "\n".join(f"- {t}" for t in prev_titles[:18]) if prev_titles else "(primul batch — nimic de evitat)"

    ctx = _vehicle_context_lines(vin)
    research = _research_snippets_from_jsonl(make, model)
    intel = _market_intel_context_block(make, model, series_s or None)

    model_focus = (
        f"MODEL DIN PROFIL: {make} {model}"
        + (f" ({series_s})" if series_s else "")
        + (f", an {year}" if year is not None else "")
        + (f", {km} km" if km is not None else "")
        + ". Cardul 2 (model_news) trebuie să fie despre acest model exact (ex. pentru Škoda Fabia 6Y: știri/tehnice specifice acelei generații)."
    )

    _jp = Path(__file__).resolve().parent / "research_data" / "articles_recent.jsonl"
    news_ctx = _research_block_romania_news(_jp)
    serv_ctx = _research_block_service(make, model, _jp)

    user_msg = (
        f"DATA_UTC: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"{model_focus}\n\n"
        f"REZUMAT_VEHICUL (brain + memorie):\n{ctx}\n\n"
        f"SUBIECTE_DE_EVITAT (titluri recente — nu repea același articol sau unghi):\n{avoid_lines}\n\n"
    )
    if research:
        user_msg += research + "\n\n"
    if news_ctx:
        user_msg += news_ctx + "\n\n"
    if serv_ctx:
        user_msg += serv_ctx + "\n\n"
    if intel:
        user_msg += intel + "\n\n"
    user_msg += "Generează JSON conform DAILY_TRIPLE_SYSTEM (exact 3 carduri)."

    banner = ""
    cards: List[Dict[str, Any]] = []

    if _env_skip_groq():
        banner, cards = _fallback_triple_cards(car_dict, prev_titles)
    else:
        try:
            raw = ai_proxy.complete_simple(
                user_msg,
                system_override=DAILY_TRIPLE_SYSTEM,
                task="json_structured",
                max_completion_tokens=6000,
            )
            payload = _extract_json_object(raw) or {}
            banner, cards = _materialize_triple_from_payload(payload, make, model, series_s or None)
        except Exception:
            banner, cards = "", []

        if len(cards) < 3:
            banner, cards = _fallback_triple_cards(car_dict, prev_titles)

    if not cards:
        banner, cards = _fallback_triple_cards(car_dict, prev_titles)

    _apply_frame_images_to_cards(cards, make, model)
    for c in cards:
        c.pop("_slot", None)

    need_enrich = any(not (str(c.get("essence") or "").strip() and str(c.get("reading_text") or "").strip()) for c in cards)
    if need_enrich:
        _enrich_cards_with_readings(cards, ctx)

    database.replace_daily_insight_cards_for_vin(vin, user_id, cards)
    if cards:
        _push_digest_to_exo(vin, cards)
    return banner, len(cards)


def _env_skip_groq() -> bool:
    return os.getenv("DAILY_INSIGHTS_SKIP_GROQ", "").strip().lower() in ("1", "true", "yes", "on")


def polish_opinion_text(text: str) -> str:
    """Corectare / optimizare limbaj pentru opinii (MulberryEXO). Fără schimbarea sensului."""
    t = (text or "").strip()
    if not t:
        return ""
    if _env_skip_groq():
        return t
    system = (
        "Ești editor MulberryEXO. Corectează gramatica și ortografia, îmbunătățește claritatea fără a schimba sensul, "
        "ton respectuos, potrivit unui feed public de opinii (stil deschis, ca pe rețele sociale). Limba: română. "
        "Răspunde DOAR cu textul corectat, fără ghilimele, fără markdown, fără prefix sau explicații."
    )
    try:
        raw = ai_proxy.complete_simple(
            "Text de corectat:\n\n" + t[:6000],
            system_override=system,
            task="fast_chat",
            max_completion_tokens=1200,
        )
        out = (raw or "").strip()
        if len(out) < 2:
            return t
        return out[:8000]
    except Exception:
        return t


def _max_vehicles_nightly() -> int:
    try:
        n = int(os.getenv("DAILY_INSIGHTS_MAX_VEHICLES", "40"))
    except ValueError:
        n = 40
    return max(1, min(n, 500))


def run_nightly_daily_insights() -> Dict[str, Any]:
    """Apelat din scheduler (noaptea). Reîmprospătează carduri pentru fiecare VIN din flotă (limită)."""
    cars = database.get_all_cars_with_vin()[: _max_vehicles_nightly()]
    ok = 0
    err = 0
    for row in cars:
        vin = (row.get("vin") or "").strip().upper()
        uid = row.get("user_id")
        if not vin:
            continue
        try:
            refresh_daily_insights_for_vin(vin, int(uid) if uid is not None else None, car_dict=row)
            ok += 1
        except Exception:
            err += 1
    return {"vehicles_ok": ok, "errors": err, "total": len(cars)}


def _demo_cards_payload() -> List[Dict[str, Any]]:
    """3 carduri demo (aceeași structură ca producția) — UI populat când lipsește VIN/DB."""
    _, demo = _fallback_triple_cards(
        {"make": "Škoda", "model": "Fabia 6Y", "series": "Mk1"},
        [],
    )
    return demo


def _cards_to_api_list(cards: List[dict]) -> List[Dict[str, Any]]:
    out_cards: List[Dict[str, Any]] = []
    for c in cards:
        fi = c.get("frame_images")
        if isinstance(fi, str):
            try:
                fi = json.loads(fi)
            except Exception:
                fi = None
        if not isinstance(fi, list):
            fi = None
        out_cards.append(
            {
                "id": c.get("id"),
                "tag": c.get("tag") or "AI INSIGHT",
                "title": c.get("title") or "",
                "url": c.get("url") or "#",
                "image_url": c.get("image_url") or None,
                "kind": (c.get("card_kind") or c.get("kind") or "article"),
                "essence": (c.get("essence") or "").strip() or None,
                "reading_text": (c.get("reading_text") or "").strip() or None,
                "frame_images": fi,
            }
        )
    return out_cards


def build_insights_response_for_user(user_id: int) -> Dict[str, Any]:
    """Pentru GET /me/daily-insights: citește SQLite + mesaj banner; demo dacă lipsește VIN sau date."""
    car = database.get_car_for_user(user_id)
    if not car or not (car.vin or "").strip():
        demos = _demo_cards_payload()
        return {
            "banner": "Adaugă vehiculul în profil pentru articole MulberryEXO personalizate după VIN.",
            "cards": _cards_to_api_list(demos),
            "new_count_hint": 0,
        }

    vin = car.vin.strip().upper()
    cards = database.get_daily_insight_cards_for_vin(vin, limit=8)
    if not cards:
        _, _ = refresh_daily_insights_for_vin(vin, user_id, car_dict=None)
        cards = database.get_daily_insight_cards_for_vin(vin, limit=8)
    elif cards and not any((str(c.get("essence") or "").strip()) for c in cards):
        _, _ = refresh_daily_insights_for_vin(vin, user_id, car_dict=None)
        cards = database.get_daily_insight_cards_for_vin(vin, limit=8)

    if not cards:
        demos = _demo_cards_payload()
        return {
            "banner": "Recomandări generale MulberryEXO. După sincronizare, conținutul se aliniază la vehiculul tău.",
            "cards": _cards_to_api_list(demos),
            "new_count_hint": 0,
        }

    last_at = database.latest_daily_insight_batch_created_at(vin)
    new_hint = 0
    if last_at:
        try:
            raw = last_at.replace("Z", "+00:00") if "Z" in last_at else last_at
            if "T" not in raw and len(raw) >= 10:
                raw = raw[:10] + "T00:00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - dt < timedelta(hours=36):
                new_hint = min(len(cards), 5)
        except Exception:
            new_hint = min(len(cards), 3)

    banner = None
    if new_hint >= 2:
        mk = (car.make or "").strip()
        md = (car.model or "").strip()
        tail = f"{mk} {md}".strip() or "vehiculul tău"
        banner = f"MulberryEXO: {new_hint} articole noi pentru {tail} — vezi mai jos."
    elif cards:
        banner = "Articole zilnice MulberryEXO pentru profilul tău."

    out_cards = _cards_to_api_list(cards)

    return {"banner": banner, "cards": out_cards, "new_count_hint": new_hint}
