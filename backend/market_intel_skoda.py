# -*- coding: utf-8 -*-
"""
Intel piață Škoda Fabia 6Y / Mk1 — surse Wikipedia (API) + sinteză Groq în SQLite.
Reîmprospătare la 24h (scheduler). MulberryEXO primește sinteza în system prompt când vehiculul se potrivește.

Notă: Groq nu „răsfoiește” internetul; articolele reale sunt aduse prin Wikipedia API (legal, stabil),
apoi modelul extrage structură pentru evaluare de piață.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from backend import ai_proxy
from backend import database

# Politica Wikimedia: User-Agent descriptiv + contact (override din .env dacă vrei)
def _http_headers() -> dict:
    ua = (
        os.getenv("MARKET_INTEL_USER_AGENT", "").strip()
        or "MulberryEXO-MarketIntel/1.0 (+https://mulberry.io; backend-research) httpx/Python"
    )
    return {
        "User-Agent": ua,
        "Accept": "application/json",
        "Api-User-Agent": ua[:220],
    }


# Pagini enciclopedice directe (REST v1 summary) — mai tolerant decât search API
REST_SEEDS: List[Tuple[str, str]] = [
    ("en", "Škoda_Fabia"),
    ("en", "Škoda_Fabia_I"),
    ("en", "Skoda_Fabia"),
    ("cs", "Škoda_Fabia"),
    ("ro", "Škoda_Fabia"),
]

SEARCH_QUERIES: List[Tuple[str, str]] = [
    ("en", "Skoda Fabia first generation"),
    ("en", "Skoda Fabia"),
    ("ro", "Skoda Fabia"),
    ("cs", "Skoda Fabia"),
]


def _wiki_api(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def rest_page_summary(lang: str, title: str) -> Optional[dict]:
    enc = quote(title.replace(" ", "_"), safe="")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{enc}"
    try:
        with httpx.Client(timeout=45.0, headers=_http_headers()) as c:
            r = c.get(url)
            if r.status_code == 404:
                return None
            if r.status_code == 403:
                print(f"[market_intel] REST 403 (policy/UA): {lang} {title!r}")
                return None
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[market_intel] REST {lang}/{title!r}: {e}")
        return None


def wiki_search(lang: str, query: str, limit: int = 8) -> List[Dict[str, str]]:
    url = _wiki_api(lang)
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "utf8": 1,
    }
    with httpx.Client(timeout=45.0, headers=_http_headers()) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    hits = (data.get("query") or {}).get("search") or []
    out: List[Dict[str, str]] = []
    for h in hits:
        t = h.get("title")
        if t:
            out.append({"title": t, "lang": lang})
    return out


def wiki_extract(lang: str, title: str, max_chars: int = 5000) -> Tuple[str, str]:
    url = _wiki_api(lang)
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "exchars": max_chars,
        "explaintext": 1,
        "titles": title,
        "utf8": 1,
    }
    with httpx.Client(timeout=45.0, headers=_http_headers()) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    pages = (data.get("query") or {}).get("pages") or {}
    for _pid, page in pages.items():
        extract = (page.get("extract") or "").strip()
        slug = title.replace(" ", "_")
        fullurl = f"https://{lang}.wikipedia.org/wiki/{slug}"
        return fullurl, extract
    slug = title.replace(" ", "_")
    return f"https://{lang}.wikipedia.org/wiki/{slug}", ""


def collect_sources(max_pages: int = 18) -> List[dict]:
    rows: List[dict] = []
    seen: set[str] = set()

    for lang, title in REST_SEEDS:
        if len(rows) >= max_pages:
            break
        data = rest_page_summary(lang, title)
        time.sleep(0.4)
        if not data:
            continue
        if data.get("type") in ("disambiguation", "redirect"):
            # pagină ajutătoare, nu articol; continuați cu alte seed-uri
            continue
        extract = (data.get("extract") or "").strip()
        if len(extract) < 60:
            continue
        cu = data.get("content_urls") or {}
        desktop = cu.get("desktop") if isinstance(cu, dict) else {}
        page_url = desktop.get("page") if isinstance(desktop, dict) else ""
        tit = (data.get("title") or title).strip()
        key = page_url or f"{lang}:{tit}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "source_url": page_url or f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                "source_title": tit,
                "source_type": "wikipedia_rest",
                "lang": lang,
                "raw_excerpt": extract[:14000],
            }
        )

    if len(rows) >= 3:
        return rows[:max_pages]

    for lang, q in SEARCH_QUERIES:
        if len(rows) >= max_pages:
            break
        try:
            hits = wiki_search(lang, q, limit=6)
        except Exception as e:
            print(f"[market_intel] wiki search {lang!r} {q!r}: {e}")
            continue
        time.sleep(0.4)
        for h in hits:
            if len(rows) >= max_pages:
                break
            keyf = f'{h["lang"]}:{h["title"]}'
            if keyf in seen:
                continue
            try:
                page_url, extract = wiki_extract(h["lang"], h["title"])
            except Exception as e:
                print(f"[market_intel] extract {h}: {e}")
                continue
            time.sleep(0.35)
            if not extract or len(extract) < 60:
                continue
            if page_url in seen:
                continue
            seen.add(page_url or keyf)
            rows.append(
                {
                    "source_url": page_url,
                    "source_title": h["title"],
                    "source_type": "wikipedia",
                    "lang": h["lang"],
                    "raw_excerpt": extract[:14000],
                }
            )

    return rows


def _parse_groq_json(raw: str) -> Dict[str, Any]:
    t = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.I)
    if m:
        t = m.group(1).strip()
    try:
        data = json.loads(t)
        return data if isinstance(data, dict) else {"rezumat_piata_ro": t[:4000]}
    except json.JSONDecodeError:
        return {"rezumat_piata_ro": t[:4000], "_parse_error": True}


def synthesize_with_groq(sources: List[dict]) -> Tuple[str, str]:
    parts: List[str] = []
    for i, s in enumerate(sources[:18], 1):
        parts.append(
            f"=== SURSA {i}: {s.get('source_title')} ({s.get('lang')}) ===\n"
            f"{(s.get('raw_excerpt') or '')[:4000]}\n"
        )
    bundle = "\n".join(parts)[:28000]

    system = (
        "Ești analist auto piață second-hand România. Primești fragmente din Wikipedia despre Škoda Fabia, "
        "inclusiv generația 6Y / prima generație Mk1 (circa 1999–2007).\n"
        "Răspunde DOAR cu un obiect JSON valid, fără markdown, fără ```. Chei exacte:\n"
        "{\n"
        '  "rezumat_piata_ro": "string, 4-8 propoziții: cum se poziționează modelul pe piața RO SH, ce urmăresc cumpărătorii",\n'
        '  "probleme_frecvente": ["string"],\n'
        '  "motorizari_notabile": ["string"],\n'
        '  "sfaturi_achizitie": ["string"],\n'
        '  "factori_pret": ["string"],\n'
        '  "disclaimer_surse": "string scurt: surse enciclopedice, nu prețuri live"\n'
        "}\n"
        "Nu inventa prețuri concrete RON/EUR. Pentru liste, dacă sursa nu spune nimic util, folosește []."
    )
    user_msg = "Analizează pentru evaluare de piață (nu service manual exhaustiv):\n\n" + bundle

    reply = ai_proxy.complete_chat(
        system,
        [{"role": "user", "content": user_msg}],
        task="json_structured",
        max_completion_tokens=2500,
    )
    data = _parse_groq_json(reply)
    lines: List[str] = []
    r = data.get("rezumat_piata_ro")
    if r:
        lines.append("Rezumat piață (context enciclopedic): " + str(r).strip())
    for label, key in (
        ("Probleme frecvente (din surse)", "probleme_frecvente"),
        ("Motorizări / versiuni notabile", "motorizari_notabile"),
        ("Sfaturi achiziție", "sfaturi_achizitie"),
        ("Factori care influențează valoarea", "factori_pret"),
    ):
        xs = data.get(key)
        if isinstance(xs, list) and xs:
            lines.append(label + ":")
            for x in xs[:14]:
                if x:
                    lines.append(f"  • {x}")
    disc = data.get("disclaimer_surse")
    if disc:
        lines.append("Note surse: " + str(disc).strip())

    synthesis_ro = "\n".join(lines) if lines else json.dumps(data, ensure_ascii=False)[:6000]
    return synthesis_ro, json.dumps(data, ensure_ascii=False)


def refresh_skoda_fabia_6y() -> Dict[str, Any]:
    """Un ciclu complet: Wikipedia → SQLite → Groq → SQLite synthesis."""
    if os.getenv("MARKET_INTEL_DISABLE", "").strip().lower() in ("1", "true", "yes", "on"):
        return {"ok": False, "skipped": True, "reason": "MARKET_INTEL_DISABLE"}

    mk = database.MODEL_KEY_SKODA_FABIA_6Y
    sources = collect_sources()
    if not sources:
        return {"ok": False, "error": "no_wikipedia_sources", "hint": "rețea sau ratelimit"}

    database.market_intel_replace_sources(mk, sources)
    try:
        synthesis_ro, synthesis_json = synthesize_with_groq(sources)
    except Exception as e:
        print(f"[market_intel] Groq synthesis failed: {e}")
        return {"ok": False, "error": str(e), "sources_stored": len(sources)}

    groq_model = (os.getenv("GROQ_MODEL_FAST") or "").strip() or None
    database.market_intel_set_synthesis(
        mk,
        synthesis_ro,
        synthesis_json,
        len(sources),
        groq_model=groq_model,
    )
    return {
        "ok": True,
        "model_key": mk,
        "sources": len(sources),
        "synthesis_chars": len(synthesis_ro),
    }


if __name__ == "__main__":
    # Din rădăcina proiectului: python -m backend.market_intel_skoda
    from backend import database as _db

    _db.init_db()
    print(refresh_skoda_fabia_6y())
