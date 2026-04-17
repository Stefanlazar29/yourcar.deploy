# Mulberry EXO — arhitectură integrată

Document de referință pentru cele 3 straturi: **SoftScore real**, **MiniMax (creier)**, **Hub live**.

## Stratul 1 — SoftScore & piață (`valuation_engine.py`)

| Componentă | Rol |
|------------|-----|
| `get_market_prices_autovit(...)` | Încearcă extragerea unui eșantion de prețuri din listări Autovit (HTML evolutiv — poate eșua; indicativ). |
| `calculate_real_softscore(...)` | Scor 0–100 din: documente (15), stare mecanică (25), piață (30), proprietari (15), recall (15). |
| `snapshot_for_vehicle(car, brain)` | Agregă Autovit + SoftScore extins pentru prompt-uri și API. |

**API:** `GET /valuation/estimate?vin=...&live_market=1`  
Răspunsul clasic (depreciere + SoftScore din brain) rămâne neschimbat; cu `live_market=1` apar câmpurile extra:

- `market_live` — rezultat Autovit  
- `soft_score_real` — dicționar cu `soft_score`, `breakdown`, `status_health`  
- `market_live_error` — dacă snapshot-ul eșuează  

> **Notă legală / tehnică:** scraping-ul site-uri terțe trebuie respectat (ToS, rate-limit). În producție: cache, CDN, sau API parteneri.

## Stratul 2 — MiniMax ca creier (`exo_assistant.py` + `minimax_client.py`)

| Fișier | Rol |
|--------|-----|
| `exo_assistant.py` | `ask_exo()` construiește system prompt cu vehicul, brain, evaluare live (best-effort), insights EXO, prețuri carburant din DB. |
| `minimax_client.py` | `call_minimax_with_history(system, messages)` — istoric user/assistant + system. |

**API:** `POST /assistant/exo`  
Body (compatibil cu `ChatRequest`):

```json
{
  "message": "întrebarea",
  "vin": "WVW...",
  "thread_id": "optional",
  "context": {
    "history": [
      { "role": "user", "content": "..." },
      { "role": "assistant", "content": "..." }
    ]
  }
}
```

Răspuns: `ChatResponse` (`reply`). Mesajele se salvează în SQLite dacă utilizatorul are JWT.

**Frontend:** `mulberry_chat.html` folosește `/assistant/exo` și trimite `context.history` (ultimele 6 mesaje, fără mesajul curent duplicat).

Endpointul clasic **`POST /assistant/ask`** (if/elif + manual Skoda + RAG) rămâne disponibil pentru fallback sau integrări vechi.

## Stratul 3 — Hub live (SSE / WebSocket — deja în proiect)

| Canal | Descriere |
|-------|-----------|
| `GET /exo/stream` | SSE autentificat: insights + stare scheduler la ~20s (vezi `mulberry_exo_menu.js`). |
| `WS /ws/notifications/{user_id}` | Notificări proactive (ITP/RCA/SoftScore). |

**Roadmap (viitor):** extinde payload-ul SSE cu `soft_score` / `valuation` după fiecare ciclu EXO sau eveniment dedicat, fără a înlocui stream-ul existent.

## Diagramă (rezumat)

```
[ AppDB / SQLite ]     [ Autovit (indicativ) ]
        \                    /
         v                  v
   valuation_engine  →  snapshot + soft_score_real
         \                  /
          v                v
      exo_assistant.build_exo_system_prompt
                  +
         minimax_client.call_minimax_with_history
                  |
                  v
   POST /assistant/exo  →  mulberry_chat.html
                  |
                  v
   GET /valuation/estimate?live_market=1  →  Dashboard / Hub
                  |
                  v
   GET /exo/stream  →  insights + scheduler (Hub live)
```

## Variabile de mediu

- `MINIMAX_API_KEY`, `MINIMAX_MODEL` — deja folosite în `minimax_client.py`.
- `MLBR_SECRET` — HMAC pentru **MLBR Digital File** (obligatoriu puternic în producție).
- `MLBR_PUBLIC_BASE` — baza URL în câmpul `verify_url` din JSON (ex. `https://id.mulberry.ro`). QR-ul din dashboard folosește `apiBaseUrl` + `mlbr_file.html?mlbr=…`.

## MLBR Digital File (`backend/mlbr_file.py`)

| Element | Rol |
|--------|-----|
| `generate_mlbr_file` | Payload JSON cu `mlbr_id`, VIN, vehicul, `verify_url`, `signature` HMAC-SHA256. |
| `verify_mlbr_file` | Verifică semnătura (orice modificare în payload = invalid). |
| Tabel `mlbr_files` | Un rând per VIN; trigger `mlbr_file_immutable` blochează schimbarea câmpurilor critice. |

**API**

- `POST /mlbr/generate` — JWT; dacă există fișier pentru VIN → returnează existentul.
- `GET /mlbr/{mlbr_id}` — public; incrementează `views`; returnează `valid`, `data`, `signature_preview`.
- `GET /mlbr/{mlbr_id}/verify` — public; `valid` + `generated_at`.
- `GET /mlbr_file.html` — servește pagina publică (scan QR).

**QR pe card:** `colorDark: #000`, `colorLight: #E1FF00`, `CorrectLevel.H`, text = URL către `mlbr_file.html?mlbr=…`.
