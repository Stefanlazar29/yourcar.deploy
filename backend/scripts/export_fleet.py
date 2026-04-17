"""
Export inventar flotă din SQLite (dev.db) — doar date tehnice vehicul, fără user_id.

Rulare din rădăcina proiectului:
  python backend/scripts/export_fleet.py

Sau cu variabile:
  SQLITE_PATH=backend/dev.db python backend/scripts/export_fleet.py
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _backend_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def export_fleet_data(
    db_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> int:
    backend = _backend_dir()
    if db_path is None:
        db_path = os.getenv("SQLITE_PATH", str(backend / "dev.db"))
    if output_path is None:
        out_dir = backend / "research_data"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / "fleet_inventory.json")

    if not os.path.isfile(db_path):
        print(f"ERROR: Baza de date nu a fost găsită la {db_path}", file=sys.stderr)
        return 1

    # Schema reală `cars`: fără engine_code / plate_number (vezi database.py)
    query = """
        SELECT vin, make, model, year, fuel, plate, series
        FROM cars
        ORDER BY id ASC
    """

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
    except sqlite3.Error as e:
        print(f"DATABASE ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    fleet = []
    for row in rows:
        fleet.append(
            {
                "vin": row[0],
                "make": row[1],
                "model": row[2],
                "year": row[3],
                "fuel": row[4],
                "plate": row[5],
                "series": row[6],
            }
        )

    last_update = datetime.now(timezone.utc).isoformat(timespec="seconds")

    payload = {
        "total_vehicles": len(fleet),
        "last_update": last_update,
        "vehicles": fleet,
    }

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"SUCCESS: {len(fleet)} vehicule exportate în {out_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(export_fleet_data())
