"""
exo_research_engine.py — EXO Autonomous Research
Crawler autonom: RSS, pagini publice, BNR, prețuri combustibil — clasificare LLM (Groq / Ollama),
stocare SQLite dedicată + snapshot JSON în app + opțional ChromaDB.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from backend import database
from backend import ai_proxy

# ── Stocare în proiect ──
RESEARCH_DIR = Path(__file__).resolve().parent / "research_data"
RESEARCH_DIR.mkdir(exist_ok=True)
RESEARCH_DB = str(RESEARCH_DIR / "exo_research.db")
SNAPSHOT_JSON = RESEARCH_DIR / "last_cycle_summary.json"
ARTIFACTS_JSONL = RESEARCH_DIR / "articles_recent.jsonl"

# ── Surse (RSS + scrape; API-urile publice sunt best-effort) ──
RESEARCH_SOURCES_RSS: List[Tuple[str, str]] = [
    ("https://www.automarket.ro/rss/", "automarket.ro"),
    ("https://www.autobild.ro/rss/", "autobild.ro"),
    ("https://www.autovit.ro/blog/feed/", "autovit.ro"),
    ("https://www.topgear.ro/feed/", "topgear.ro"),
    ("https://www.motorsport.com/rss/all/news/", "motorsport.com"),
]

SCRAPE_SOURCES: List[Dict[str, str]] = [
    {
        "url": "https://www.automarket.ro/stiri/",
        "selector": "article, .article-item, .news-item, .story-item",
        "source": "automarket.ro",
    },
]

OPTIONAL_API_URLS: List[Tuple[str, str]] = [
    ("https://www.bnr.ro/nbrfxrates.xml", "bnr_fx"),
    ("https://www.peco-online.ro/", "peco_home"),
]


CLASSIFY_PROMPT = """
Ești un clasificator de articole auto pentru piața românească.
Analizează textul și returnează DOAR JSON valid.

FORMAT:
{
  "relevant": true,
  "insight_type": "recall|maintenance|legal|market|fuel|technical|weather|general",
  "makes": ["Skoda", "Dacia"],
  "models": ["Fabia", "Logan"],
  "year_from": null,
  "year_to": null,
  "title": "Titlu scurt max 60 chars",
  "summary": "Rezumat max 120 chars",
  "tags": ["tag1"],
  "relevance": 0.8,
  "severity": "critical|high|normal|low"
}

Returnează relevant: false dacă articolul nu e despre mașini sau piața auto.
"""


def init_research_db() -> None:
    con = sqlite3.connect(RESEARCH_DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS raw_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            source TEXT,
            title TEXT,
            content TEXT,
            content_hash TEXT UNIQUE,
            fetched_at TEXT,
            processed INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS processed_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER,
            insight_type TEXT,
            make TEXT,
            model TEXT,
            year_from INTEGER,
            year_to INTEGER,
            title TEXT,
            content TEXT,
            tags TEXT,
            relevance REAL DEFAULT 0.5,
            source_url TEXT,
            created_at TEXT,
            FOREIGN KEY(article_id) REFERENCES raw_articles(id)
        );

        CREATE TABLE IF NOT EXISTS fuel_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuel_type TEXT,
            price_ron REAL,
            city TEXT DEFAULT 'Romania',
            source TEXT,
            recorded_at TEXT
        );

        CREATE TABLE IF NOT EXISTS market_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT,
            model TEXT,
            year INTEGER,
            price_ron REAL,
            mileage_avg INTEGER,
            source TEXT,
            recorded_at TEXT
        );

        CREATE TABLE IF NOT EXISTS recall_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT,
            model TEXT,
            year_from INTEGER,
            year_to INTEGER,
            description TEXT,
            severity TEXT,
            source_url TEXT,
            published_at TEXT,
            content_hash TEXT UNIQUE
        );

        CREATE INDEX IF NOT EXISTS idx_insights_make_model ON processed_insights(make, model);
        CREATE INDEX IF NOT EXISTS idx_insights_type ON processed_insights(insight_type);
        CREATE INDEX IF NOT EXISTS idx_fuel_type ON fuel_prices(fuel_type, recorded_at);
        """
    )
    con.commit()
    con.close()
    print("[EXO Research DB] Inițializat:", RESEARCH_DB)


def research_connect() -> sqlite3.Connection:
    con = sqlite3.connect(RESEARCH_DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def _content_hash(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8"), usedforsecurity=False).hexdigest()


def _parse_json_from_llm(raw: str) -> Optional[dict]:
    if not raw:
        return None
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        inner: List[str] = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            inner.append(line)
        clean = "\n".join(inner).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    if m:
        clean = m.group(0)
    try:
        return json.loads(clean)
    except Exception:
        return None


# ── Fetchers ──


async def fetch_rss(url: str, source_name: str) -> List[dict]:
    articles: List[dict] = []
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "MulberryEXO/2.8 (research; +https://mulberry.local)"},
            )
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")
        items = soup.find_all("item") or soup.find_all("entry")
        for item in items[:20]:
            title_el = item.find("title")
            desc = item.find("description") or item.find("summary") or item.find("content")
            link_el = item.find("link")
            pub = item.find("pubDate") or item.find("published")

            title_text = title_el.get_text(strip=True) if title_el else ""
            raw_desc = desc.get_text(strip=True) if desc else ""
            desc_text = BeautifulSoup(raw_desc, "html.parser").get_text()[:500]

            link_text = url
            if link_el:
                if link_el.name == "link" and link_el.get("href"):
                    link_text = link_el["href"]
                else:
                    link_text = link_el.get_text(strip=True) or url

            if not title_text:
                continue
            full_text = f"{title_text} {desc_text}"
            articles.append(
                {
                    "url": link_text,
                    "source": source_name,
                    "title": title_text,
                    "content": desc_text,
                    "hash": _content_hash(full_text),
                    "fetched_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
            )
    except Exception as e:
        print(f"[EXO Research] RSS error {url}: {e}")
    return articles


async def fetch_fuel_prices() -> List[dict]:
    prices: List[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.peco-online.ro/",
                headers={"User-Agent": "MulberryEXO/2.8"},
            )
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.select(".fuel-row, .price-row, tr, .pret, .fuel"):
            cells = row.find_all(["td", "span", "div"])
            if len(cells) < 2:
                continue
            text = " ".join(c.get_text(strip=True) for c in cells)
            tl = text.lower()
            fuel_type: Optional[str] = None
            if any(w in tl for w in ("benzin", "95", "98", "e10")):
                fuel_type = "benzina"
            elif any(w in tl for w in ("motorin", "diesel")):
                fuel_type = "motorina"
            elif "gpl" in tl:
                fuel_type = "gpl"
            price_match = re.search(r"(\d+[.,]\d{2,3})", text)
            if fuel_type and price_match:
                price = float(price_match.group(1).replace(",", "."))
                if 3.0 < price < 20.0:
                    prices.append(
                        {
                            "fuel_type": fuel_type,
                            "price_ron": price,
                            "city": "Romania",
                            "source": "peco-online.ro",
                            "recorded_at": datetime.utcnow().isoformat(timespec="seconds"),
                        }
                    )
    except Exception as e:
        print(f"[EXO Research] Fuel fetch error: {e}")
    return prices


async def fetch_bnr_eur() -> Optional[float]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://www.bnr.ro/nbrfxrates.xml")
        soup = BeautifulSoup(resp.text, "xml")
        for rate in soup.find_all("Rate"):
            if rate.get("currency") == "EUR":
                return float(rate.get_text(strip=True).replace(",", "."))
    except Exception as e:
        print(f"[EXO Research] BNR error: {e}")
    return None


async def scrape_page(url: str, selector: str, source: str) -> List[dict]:
    articles: List[dict] = []
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MulberryEXO/2.8)"},
            )
        soup = BeautifulSoup(resp.text, "html.parser")
        base = f"{resp.url.scheme}://{resp.url.host}"
        items = soup.select(selector)[:15]
        for item in items:
            title_el = item.find(["h1", "h2", "h3", "h4", "a"])
            link_el = item.find("a", href=True)
            text_el = item.find("p") or item.find("div")
            title = title_el.get_text(strip=True) if title_el else ""
            content = (text_el.get_text(strip=True)[:400] if text_el else "") if text_el else ""
            href = link_el["href"] if link_el else url
            if not title:
                continue
            if href.startswith("http"):
                link = href
            else:
                link = base.rstrip("/") + "/" + href.lstrip("/")
            articles.append(
                {
                    "url": link,
                    "source": source,
                    "title": title[:300],
                    "content": content,
                    "hash": _content_hash(title + content),
                    "fetched_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
            )
    except Exception as e:
        print(f"[EXO Research] Scrape error {url}: {e}")
    return articles


def classify_article(title: str, content: str) -> Optional[dict]:
    try:
        text = f"TITLU: {title}\n\nCONȚINUT: {(content or '')[:800]}"
        raw = ai_proxy.complete_simple(
            text,
            "",
            system_override=CLASSIFY_PROMPT,
            task="classify",
            max_completion_tokens=800,
        )
        return _parse_json_from_llm(raw)
    except Exception as e:
        print(f"[EXO Research] Classify error: {e}")
        return None


def store_raw_article(article: dict) -> Optional[int]:
    con = research_connect()
    try:
        h = article["hash"]
        row = con.execute("SELECT id FROM raw_articles WHERE content_hash = ?", (h,)).fetchone()
        if row:
            return None
        cur = con.execute(
            """
            INSERT INTO raw_articles (url, source, title, content, content_hash, fetched_at, processed)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                article["url"],
                article["source"],
                article["title"],
                article["content"],
                h,
                article["fetched_at"],
            ),
        )
        con.commit()
        return int(cur.lastrowid) if cur.lastrowid else None
    except Exception as e:
        print(f"[EXO Research] Store raw error: {e}")
        return None
    finally:
        con.close()


def store_processed_insight(article_id: int, classified: dict, source_url: str) -> None:
    con = research_connect()
    try:
        makes = classified.get("makes") or []
        models = classified.get("models") or []
        if not isinstance(makes, list):
            makes = []
        if not isinstance(models, list):
            models = []

        entries: List[Tuple[Optional[str], Optional[str]]] = []
        if makes:
            for make in makes:
                model = models[0] if models else None
                entries.append((str(make) if make else None, str(model) if model else None))
        else:
            entries.append((None, None))

        tags_json = json.dumps(classified.get("tags") or [], ensure_ascii=False)
        for make, model in entries:
            con.execute(
                """
                INSERT INTO processed_insights
                (article_id, insight_type, make, model, year_from, year_to,
                 title, content, tags, relevance, source_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    str(classified.get("insight_type") or "general"),
                    make,
                    model,
                    classified.get("year_from"),
                    classified.get("year_to"),
                    str(classified.get("title") or "")[:200],
                    str(classified.get("summary") or "")[:500],
                    tags_json,
                    float(classified.get("relevance") or 0.5),
                    source_url,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
        con.execute("UPDATE raw_articles SET processed = 1 WHERE id = ?", (article_id,))
        con.commit()
    except Exception as e:
        print(f"[EXO Research] Store insight error: {e}")
    finally:
        con.close()


def store_fuel_prices(prices: List[dict]) -> None:
    if not prices:
        return
    con = research_connect()
    try:
        for p in prices:
            con.execute(
                """
                INSERT INTO fuel_prices (fuel_type, price_ron, city, source, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    p["fuel_type"],
                    float(p["price_ron"]),
                    p.get("city", "Romania"),
                    p.get("source", ""),
                    p.get("recorded_at", datetime.utcnow().isoformat(timespec="seconds")),
                ),
            )
        con.commit()
        print(f"[EXO Research] Prețuri combustibil salvate: {len(prices)}")
    finally:
        con.close()


def _maybe_chroma_index(title: str, summary: str, meta: dict) -> None:
    try:
        from backend import vector_store

        text = f"{title}\n{summary}".strip()
        if len(text) < 20:
            return
        nid = _content_hash(text)[:16]
        vector_store.add_documents(
            [text[:8000]],
            ids=[f"exo_research_{nid}"],
            metadatas=[meta],
            collection_source="research",
        )
    except Exception as e:
        print(f"[EXO Research] Chroma index skip: {e}")


def _push_to_vehicle_feeds(classified: dict, source_url: str) -> None:
    try:
        cars = database.get_all_cars_with_vin()
        makes = [str(m).lower() for m in (classified.get("makes") or [])]
        models = [str(m).lower() for m in (classified.get("models") or [])]
        for car in cars:
            car_make = (car.get("make") or "").lower()
            car_model = (car.get("model") or "").lower()
            vin = (car.get("vin") or "").strip().upper()
            if not vin:
                continue
            is_general = not makes
            make_match = any(m in car_make or car_make in m for m in makes) if makes else False
            model_match = (
                any(m in car_model or car_model in m for m in models) if models else True
            )
            if is_general or (make_match and model_match):
                severity = classified.get("severity") or "normal"
                prefix = "⚠️ " if severity in ("critical", "high") else ""
                text = f"{prefix}{classified.get('title', '')} — {classified.get('summary', '')}"
                database.insert_exo_insight(
                    vin=vin,
                    insight_text=text[:2000],
                    insight_type=str(classified.get("insight_type") or "general")[:64],
                    raw_context=json.dumps(
                        {"source": source_url, "severity": severity, "tags": classified.get("tags", [])},
                        ensure_ascii=False,
                    ),
                    engine="exo_research",
                )
    except Exception as e:
        print(f"[EXO Research] Push feeds error: {e}")


def get_insights_for_vehicle(
    make: str,
    model: str,
    year: Optional[int] = None,
    limit: int = 10,
) -> List[dict]:
    con = research_connect()
    try:
        make_pat = f"%{(make or '').lower().strip()}%"
        model_pat = f"%{(model or '').lower().strip()}%"
        lim = max(1, min(limit, 50))
        if year is None:
            rows = con.execute(
                """
                SELECT * FROM processed_insights
                WHERE (
                    make IS NULL
                    OR (lower(ifnull(make,'')) LIKE ? AND lower(ifnull(model,'')) LIKE ?)
                )
                ORDER BY relevance DESC, datetime(created_at) DESC
                LIMIT ?
                """,
                (make_pat, model_pat, lim),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT * FROM processed_insights
                WHERE (
                    make IS NULL
                    OR (lower(ifnull(make,'')) LIKE ? AND lower(ifnull(model,'')) LIKE ?)
                )
                AND (year_from IS NULL OR year_from <= ?)
                AND (year_to IS NULL OR year_to >= ?)
                ORDER BY relevance DESC, datetime(created_at) DESC
                LIMIT ?
                """,
                (make_pat, model_pat, year, year, lim),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_latest_fuel_prices() -> Dict[str, float]:
    con = research_connect()
    try:
        rows = con.execute(
            """
            SELECT fuel_type, price_ron, recorded_at
            FROM fuel_prices f1
            WHERE recorded_at = (
                SELECT MAX(recorded_at) FROM fuel_prices f2 WHERE f2.fuel_type = f1.fuel_type
            )
            ORDER BY fuel_type
            """
        ).fetchall()
        return {r["fuel_type"]: float(r["price_ron"]) for r in rows}
    finally:
        con.close()


def get_research_status_counts() -> dict:
    init_research_db()
    con = research_connect()
    try:
        articles = con.execute("SELECT COUNT(*) AS c FROM raw_articles").fetchone()["c"]
        processed = con.execute(
            "SELECT COUNT(*) AS c FROM raw_articles WHERE processed = 1"
        ).fetchone()["c"]
        insights = con.execute("SELECT COUNT(*) AS c FROM processed_insights").fetchone()["c"]
        fuel = con.execute("SELECT COUNT(*) AS c FROM fuel_prices").fetchone()["c"]
        last = con.execute("SELECT MAX(created_at) AS m FROM processed_insights").fetchone()["m"]
        return {
            "articles_total": articles,
            "articles_processed": processed,
            "insights_stored": insights,
            "fuel_records": fuel,
            "last_research": last,
        }
    finally:
        con.close()


def _append_jsonl(path: Path, obj: dict) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[EXO Research] jsonl error: {e}")


def _write_snapshot(results: dict, bnr_eur: Optional[float], extra: dict) -> None:
    payload = {
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "cycle": results,
        "bnr_eur": bnr_eur,
        "extra": extra,
    }
    try:
        SNAPSHOT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[EXO Research] Snapshot:", SNAPSHOT_JSON)
    except Exception as e:
        print(f"[EXO Research] Snapshot error: {e}")


async def _async_research_cycle() -> dict:
    results: Dict[str, Any] = {
        "articles_fetched": 0,
        "articles_new": 0,
        "insights_classified": 0,
        "fuel_prices_updated": 0,
        "errors": 0,
        "chroma_indexed": 0,
    }
    all_articles: List[dict] = []

    print("[EXO Research] Fetch RSS…")
    for url, source in RESEARCH_SOURCES_RSS:
        try:
            arts = await fetch_rss(url, source)
            all_articles.extend(arts)
            print(f"[EXO Research] {source}: {len(arts)} articole")
        except Exception as e:
            results["errors"] += 1
            print(f"[EXO Research] RSS fail {source}: {e}")

    print("[EXO Research] Scrape…")
    for src in SCRAPE_SOURCES:
        try:
            arts = await scrape_page(src["url"], src["selector"], src["source"])
            all_articles.extend(arts)
        except Exception as e:
            results["errors"] += 1
            print(f"[EXO Research] Scrape fail: {e}")

    results["articles_fetched"] = len(all_articles)

    new_ids: List[Tuple[int, dict]] = []
    for article in all_articles:
        aid = store_raw_article(article)
        if aid:
            new_ids.append((aid, article))
            results["articles_new"] += 1
            _append_jsonl(ARTIFACTS_JSONL, {"id": aid, **article})

    print(f"[EXO Research] Articole noi: {results['articles_new']} / {len(all_articles)}")

    max_classify = int(os_env_int("EXO_RESEARCH_MAX_CLASSIFY", 30))
    for article_id, article in new_ids[:max_classify]:
        try:
            classified = classify_article(article["title"], article["content"])
            rel = False
            if classified:
                r = classified.get("relevant")
                rel = r is True or (isinstance(r, str) and r.lower() in ("true", "1", "yes"))
            score = float(classified.get("relevance") or 0) if classified else 0.0
            if classified and rel and score > 0.4:
                store_processed_insight(article_id, classified, article["url"])
                _push_to_vehicle_feeds(classified, article["url"])
                _maybe_chroma_index(
                    str(classified.get("title") or ""),
                    str(classified.get("summary") or ""),
                    {"source": "exo_research", "url": article["url"]},
                )
                results["insights_classified"] += 1
                results["chroma_indexed"] += 1
        except Exception as e:
            results["errors"] += 1
            print(f"[EXO Research] classify/store: {e}")
        await asyncio.sleep(0.5)

    fuel_prices = await fetch_fuel_prices()
    if fuel_prices:
        store_fuel_prices(fuel_prices)
        results["fuel_prices_updated"] = len(fuel_prices)

    bnr_eur = await fetch_bnr_eur()
    extra: Dict[str, Any] = {"optional_urls_tried": [u for u, _ in OPTIONAL_API_URLS]}
    return results, bnr_eur, extra


def os_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def run_research_cycle() -> dict:
    init_research_db()
    results: dict = {"error": None}
    bnr: Optional[float] = None
    extra: dict = {}
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results, bnr, extra = loop.run_until_complete(_async_research_cycle())
        loop.close()
    except Exception as e:
        print(f"[EXO Research] Ciclu: {e}")
        results = {
            "articles_fetched": 0,
            "articles_new": 0,
            "insights_classified": 0,
            "fuel_prices_updated": 0,
            "errors": 1,
            "error": str(e),
        }
        bnr = None
        extra = {}

    _write_snapshot(results, bnr, extra)
    print(f"[EXO Research] Rezultat: {results}")
    return results
