# Mulberry — arhitectură (AI & date)

Vezi și **[docs/MULBERRY_EXO_ARCHITECTURE.md](docs/MULBERRY_EXO_ARCHITECTURE.md)** — strat SoftScore real + MiniMax EXO + Hub (SSE).

## Baze de date

| Fișier | Rol |
|--------|-----|
| `backend/dev.db` | SQLite principal: users, cars, vehicle_brains, exo_daily_insights, chat, prefs |
| `backend/research_data/exo_research.db` | SQLite research: articole RSS/scrape, insights procesate, fuel |

Conexiuni: `PRAGMA foreign_keys=ON`, `journal_mode=WAL` (în `database.connect()` și `research_connect()`).

## EXO insights (`exo_daily_insights`)

Câmp **`engine`**: sursa rândului

- `exo_intelligence` — ciclul MiniMax per vehicul (`exo_engine.py`)
- `exo_research` — crawler + clasificare (`exo_research_engine.py`)
- `exo_research_ollama` — legacy Ollama (`exo_research.py`, endpoint deprecat)

Rotație cost: `EXO_MAX_VEHICLES_PER_CYCLE` (default 10) — vehiculele cu cele mai vechi insight-uri `exo_intelligence` sunt prioritizate.

## ChromaDB (`chroma_db/`)

| Colecție | Conținut |
|----------|----------|
| `mulberry_knowledge` | Legacy (înainte de split) |
| `mulberry_manual` | Chunk-uri din `resources/` (ingestion) |
| `mulberry_research` | Rezumate EXO Research |
| `mulberry_reports` | Rezervat rapoarte |

`vector_store.query()` interoghează implicit legacy + manual + research.

## Autentificare SSE

`GET /exo/stream` acceptă doar **`Authorization: Bearer <JWT>`** (fără `?token=`). Hub: `fetch` + `ReadableStream`.

## Variabile `.env`

- `JWT_SECRET` — obligatoriu puternic în producție (`secrets.token_hex(32)`).
- `MINIMAX_API_KEY` — MiniMax.
- `EXO_MAX_VEHICLES_PER_CYCLE` — opțional, limită vehicule/ciclu EXO Intelligence.

**Notă:** schimbarea `JWT_SECRET` invalidează toate token-urile existente → utilizatorii se loghează din nou.
