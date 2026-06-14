# RAG QData — memorie vehicul în ChromaDB

## Flux

1. **Embedding** — `python backend/scripts/embed_vehicle_qdata.py --vin <VIN>` (sau `--all`) citește SQLite (`cars`, `vehicle_brains`) și face **upsert** într-un document per VIN în colecția **`mulberry_vehicle_memory`**.
2. **Interogare** — la fiecare mesaj către MulberryEXO (`ask_exo`), se rulează căutare semantică pe această colecție (filtru `vin`), iar fragmentele relevante sunt injectate în **system prompt** înainte de Groq.
3. **Feedback** (viitor) — `rag_qdata.boost_confidence_placeholder()` rezervat pentru creșterea încrederii când utilizatorul confirmă răspunsul.

## Comenzi

```bash
# Un vehicul
python backend/scripts/embed_vehicle_qdata.py --vin WVWZZZ1JZ3W386752

# Flotă
python backend/scripts/embed_vehicle_qdata.py --all

# Previzualizare text, fără scriere
python backend/scripts/embed_vehicle_qdata.py --vin ... --dry-run
```

## Variabile

- `SQLITE_PATH`, `CHROMA_PERSIST_PATH` — aliniate cu API-ul (inclusiv Docker `/data/chroma_db`).

## Siguranță

Textul din RAG nu înlocuiește fișa din prompt; instrucțiunea către model cere prioritate pentru datele structurate și menționarea incertitudinii la conflict.
