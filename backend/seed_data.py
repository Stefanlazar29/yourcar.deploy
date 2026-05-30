"""
Run once to populate Supabase with development mock data.
Usage:  python backend/seed_data.py
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars (or a .env file).
"""
import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://yvpjfmjxunoxmfljixwo.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

MOCK_VEHICLES = [
    {
        "plate": "B-12-MLB",
        "vin": "WAUZZZ8K9DA123456",
        "cod_k": "e1*2001/116*0123*00",
        "owner": "Alexandru Popescu",
        "brand": "Audi",
        "model": "A4",
        "year": 2018,
        "status": "verified",
    },
    {
        "plate": "CJ-45-ABC",
        "vin": "WBA3A5G50ENS12345",
        "cod_k": "e1*2007/46*0456*01",
        "owner": "Maria Ionescu",
        "brand": "BMW",
        "model": "320d",
        "year": 2020,
        "status": "verified",
    },
    {
        "plate": "TM-99-XYZ",
        "vin": "VSSZZZ6FZHR012345",
        "cod_k": "e9*2001/116*0789*00",
        "owner": "Radu Dumitrescu",
        "brand": "SEAT",
        "model": "Leon",
        "year": 2017,
        "status": "pending",
    },
]

MOCK_OFFERS = [
    {
        "partner": "Allianz România",
        "type": "RCA",
        "price": 420,
        "currency": "RON",
        "valid_days": 365,
    },
    {
        "partner": "Generali",
        "type": "CASCO",
        "price": 1850,
        "currency": "RON",
        "valid_days": 365,
    },
]


async def seed():
    print("Seeding date simulate...")

    for v in MOCK_VEHICLES:
        sb.table("vehicles").upsert(v, on_conflict="vin").execute()
        print(f"  ✅ Vehicul: {v['plate']} — {v['brand']} {v['model']}")

    for o in MOCK_OFFERS:
        sb.table("offers").upsert(o, on_conflict="partner,type").execute()
        print(f"  ✅ Ofertă: {o['partner']} {o['type']} — {o['price']} {o['currency']}")

    print("\nDone. Tabelele vehicles și offers sunt populate.")


asyncio.run(seed())
