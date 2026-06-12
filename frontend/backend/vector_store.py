# backend/vector_store.py — ChromaDB: colecții separate (manual / research / legacy)

import os
from datetime import datetime
from typing import Dict, List, Optional

VECTOR_DB_PATH = os.getenv(
  "CHROMA_PERSIST_PATH",
  os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db"),
)
RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")
os.makedirs(RESOURCES_DIR, exist_ok=True)
os.makedirs(VECTOR_DB_PATH, exist_ok=True)

LEGACY_COLLECTION = "mulberry_knowledge"
# Memorie RAG per vehicul (QData + brain) — un document upsert per VIN
VEHICLE_MEMORY_COLLECTION = "mulberry_vehicle_memory"

# Colecții: legacy = vechiul nume unic; manual/research = noi
COLLECTION_BY_SOURCE: Dict[str, str] = {
    "manual": "mulberry_manual",
    "research": "mulberry_research",
    "reports": "mulberry_reports",
    "vehicle_qdata": VEHICLE_MEMORY_COLLECTION,
}

_CHROMA_CLIENT = None
_COLLECTION_CACHE: Dict[str, object] = {}


def _get_client():
    global _CHROMA_CLIENT
    if _CHROMA_CLIENT is not None:
        return _CHROMA_CLIENT
    try:
        import chromadb
        from chromadb.config import Settings

        _CHROMA_CLIENT = chromadb.PersistentClient(
            path=VECTOR_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        return _CHROMA_CLIENT
    except ImportError:
        return None


def _get_named_collection(name: str):
    """Returnează colecția după nume exact (create dacă lipsește la add)."""
    if name in _COLLECTION_CACHE:
        return _COLLECTION_CACHE[name]
    client = _get_client()
    if not client:
        return None
    try:
        col = client.get_or_create_collection(
            name=name,
            metadata={"description": f"Mulberry · {name}"},
        )
        _COLLECTION_CACHE[name] = col
        return col
    except Exception:
        return None


def _try_get_collection_readonly(name: str):
    """Pentru query: nu creează colecție goală inutil."""
    client = _get_client()
    if not client:
        return None
    try:
        return client.get_collection(name)
    except Exception:
        return None


def get_collection_for_source(source: str = "manual"):
    """source: manual | research | reports"""
    key = COLLECTION_BY_SOURCE.get(source, COLLECTION_BY_SOURCE["manual"])
    return _get_named_collection(key)


def add_documents(
    documents: List[str],
    ids: Optional[List[str]] = None,
    metadatas: Optional[List[dict]] = None,
    *,
    collection_source: str = "manual",
) -> int:
    """
    Adaugă documente. collection_source: manual (resources), research (EXO), reports.
    """
    name = COLLECTION_BY_SOURCE.get(collection_source, COLLECTION_BY_SOURCE["manual"])
    col = _get_named_collection(name)
    if not col or not documents:
        return 0
    try:
        ids = ids or [f"doc_{i}_{hash(d[:50]) % 10**8}" for i, d in enumerate(documents)]
        col.add(documents=documents, ids=ids[: len(documents)], metadatas=metadatas)
        return len(documents)
    except Exception as e:
        print(f"[VectorStore] Eroare add ({name}): {e}")
        return 0


def query(
    query_text: str,
    n_results: int = 5,
    where: Optional[dict] = None,
    *,
    sources: Optional[List[str]] = None,
) -> List[dict]:
    """
    Căutare semantică. sources: nume colecții Chroma sau chei manual/research/legacy.
    Implicit: legacy + manual + research (toate care există).
    """
    n_results = max(1, min(n_results, 20))
    default_names = [LEGACY_COLLECTION, COLLECTION_BY_SOURCE["manual"], COLLECTION_BY_SOURCE["research"]]
    if sources is None:
        names_to_query = default_names
    else:
        names_to_query = []
        for s in sources:
            if s in COLLECTION_BY_SOURCE:
                names_to_query.append(COLLECTION_BY_SOURCE[s])
            elif s in COLLECTION_BY_SOURCE.values() or s == LEGACY_COLLECTION:
                names_to_query.append(s)
        if not names_to_query:
            names_to_query = default_names

    all_hits: List[dict] = []
    per = max(1, n_results // max(1, len(names_to_query)) + 1)

    for name in names_to_query:
        col = _try_get_collection_readonly(name)
        if not col:
            continue
        try:
            res = col.query(query_texts=[query_text], n_results=per, where=where)
            if res and res.get("documents") and res["documents"][0]:
                for i, doc in enumerate(res["documents"][0]):
                    meta = (res.get("metadatas") or [[]])[0]
                    meta = meta[i] if i < len(meta) else {}
                    dist = (res.get("distances") or [[]])[0]
                    dist = dist[i] if i < len(dist) else None
                    m = dict(meta) if meta else {}
                    m["_collection"] = name
                    all_hits.append({"text": doc, "metadata": m, "distance": dist})
        except Exception as e:
            print(f"[VectorStore] Eroare query ({name}): {e}")

    all_hits.sort(key=lambda h: h["distance"] if h.get("distance") is not None else 1e9)
    return all_hits[:n_results]


def count() -> int:
    """Total documente în toate colecțiile cunoscute."""
    total = 0
    names = list(
        set([LEGACY_COLLECTION, VEHICLE_MEMORY_COLLECTION] + list(COLLECTION_BY_SOURCE.values()))
    )
    for name in names:
        col = _try_get_collection_readonly(name)
        if not col:
            continue
        try:
            total += col.count()
        except Exception:
            pass
    return total


def upsert_vehicle_qdata(
    vin: str,
    text: str,
    *,
    user_id: Optional[int] = None,
    confidence: float = 1.0,
    source: str = "qdata_sqlite",
) -> bool:
    """
    Salvează / actualizează un singur document per VIN în colecția mulberry_vehicle_memory.
    ID stabil: qdata_{VIN} — pentru re-embed fără duplicate.
    """
    vin = (vin or "").strip().upper()
    if not vin or not (text or "").strip():
        return False
    col = _get_named_collection(VEHICLE_MEMORY_COLLECTION)
    if not col:
        return False
    doc_id = f"qdata_{vin}"
    meta = {
        "vin": vin,
        "source": source,
        "confidence": float(confidence),
        "kind": "vehicle_profile",
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }
    if user_id is not None:
        meta["user_id"] = int(user_id)
    try:
        col.upsert(ids=[doc_id], documents=[text.strip()], metadatas=[meta])
        return True
    except Exception as e:
        print(f"[VectorStore] Eroare upsert_vehicle_qdata ({vin}): {e}")
        return False


def query_vehicle_memory(vin: str, query_text: str, n_results: int = 4) -> List[dict]:
    """
    Căutare semantică doar în memoria vehiculului (filtru metadata vin).
    """
    vin = (vin or "").strip().upper()
    if not vin or not (query_text or "").strip():
        return []
    col = _try_get_collection_readonly(VEHICLE_MEMORY_COLLECTION)
    if not col:
        return []
    n_results = max(1, min(int(n_results), 12))
    try:
        res = col.query(
            query_texts=[query_text.strip()],
            n_results=n_results,
            where={"vin": {"$eq": vin}},
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out: List[dict] = []
        for i, doc in enumerate(docs):
            if not doc:
                continue
            meta = dict(metas[i]) if i < len(metas) and metas[i] else {}
            dist = dists[i] if i < len(dists) else None
            out.append({"text": doc, "metadata": meta, "distance": dist})
        return out
    except Exception as e:
        print(f"[VectorStore] Eroare query_vehicle_memory ({vin}): {e}")
        return []


def ingest_from_resources() -> dict:
    """
    Citește fișiere din resources/ și le adaugă în colecția **mulberry_manual**.
    """
    if not os.path.isdir(RESOURCES_DIR):
        return {"added": 0, "files": []}
    added = 0
    files_processed = []
    chunk_size = 500
    overlap = 50

    for fn in os.listdir(RESOURCES_DIR):
        if not fn.lower().endswith((".txt", ".md")):
            continue
        path = os.path.join(RESOURCES_DIR, fn)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            print(f"[VectorStore] Eroare citire {fn}: {e}")
            continue

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if len(chunk) > 30:
                chunks.append(chunk)
            start = end - overlap

        if chunks:
            ids = [f"res_{fn}_{i}" for i in range(len(chunks))]
            meta = [{"source": fn, "kind": "manual"}] * len(chunks)
            n = add_documents(chunks, ids=ids, metadatas=meta, collection_source="manual")
            added += n
            files_processed.append(fn)
    return {"added": added, "files": files_processed}
