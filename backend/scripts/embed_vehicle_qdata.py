"""
Embedding QData → ChromaDB (colecția mulberry_vehicle_memory).

Construiește text canonic din rândul `cars` + opțional `vehicle_brains` și face upsert
(un document per VIN). După rulare, EXO primește memorie RAG injectată înainte de Groq.

Rulare din rădăcina proiectului:
  python backend/scripts/embed_vehicle_qdata.py --vin WVWZZZ...
  python backend/scripts/embed_vehicle_qdata.py --all

Variabile:
  SQLITE_PATH, CHROMA_PERSIST_PATH (ca la API / Docker)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / "backend" / ".env")
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="QData → embeddings ChromaDB (Mulberry RAG)")
    parser.add_argument("--vin", help="VIN 17 caractere")
    parser.add_argument("--all", action="store_true", help="Toate mașinile cu VIN din SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Afișează textul, fără scriere în Chroma")
    args = parser.parse_args()

    if not args.vin and not args.all:
        parser.error("Specifică --vin sau --all")

    from backend import database
    from backend import rag_qdata

    if args.vin:
        vins = [args.vin.strip().upper()]
    else:
        rows = database.get_all_cars_with_vin()
        vins = []
        for r in rows:
            v = (r.get("vin") or "").strip().upper()
            if len(v) == 17:
                vins.append(v)
        if not vins:
            print("Nu există VIN-uri în baza de date.", file=sys.stderr)
            return 1

    ok_n = 0
    for vin in vins:
        if args.dry_run:
            car = database.get_car_by_vin(vin)
            brain = database.get_vehicle_brain(vin)
            if car:
                text = rag_qdata.build_qdata_text_from_car(car, brain)
            elif brain:
                text = rag_qdata.build_qdata_text_brain_only(brain)
            else:
                print(f"[skip] {vin}: fără date", file=sys.stderr)
                continue
            print(f"=== {vin} ({len(text)} chars) ===\n{text}\n")
            ok_n += 1
            continue

        ok, msg = rag_qdata.upsert_vehicle_qdata_embedding(vin)
        print(f"{vin}: {msg}")
        if ok:
            ok_n += 1

    print(f"Finalizat: {ok_n}/{len(vins)} reușite.")
    return 0 if ok_n == len(vins) else 1


if __name__ == "__main__":
    raise SystemExit(main())
