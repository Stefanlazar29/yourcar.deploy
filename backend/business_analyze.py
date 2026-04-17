# -*- coding: utf-8 -*-
"""
Analiză business / flotă prin LLM (Groq via AIProxy) — context strict din MulberryVehicleDTO.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.ai_proxy import complete_chat

if TYPE_CHECKING:
    from backend.vehicle_dto import MulberryVehicleDTO

SYSTEM_FLEET = (
    "Ești un consultant de flotă auto B2B (România), orientat pe cifre și pragmatism. "
    "Primești un obiect JSON cu datele canonice ale unui vehicul din sistemul Mulberry (VIN, marcă, "
    "km, expirări RCA/ITP, scoruri dacă există). "
    "Analizează strict pe baza acestor date și a întrebării utilizatorului. "
    "Dacă o informație nu e în JSON (ex. preț închiriere 31€), trateaz-o ca ipoteză enunțată de user "
    "și explică ce ai nevoie ca să compari cu mentenanță (sau fă scenarii cu ipoteze explicite). "
    "Nu inventa kilometri, date expirare sau scoruri care nu apar în JSON. "
    "Răspuns în română: structură clară (titluri scurte + bullet), fără salutări de politețe. "
    "Unde e cazul, menționează riscuri, costuri tipice orientative RON și urgență."
)


def run_business_analysis(vehicle: "MulberryVehicleDTO", question: str) -> str:
    q = (question or "").strip()
    if len(q) < 3:
        raise ValueError("Întrebarea este prea scurtă.")
    payload = json.dumps(vehicle.model_dump(mode="json"), ensure_ascii=False, indent=2)
    messages = [
        {
            "role": "user",
            "content": "Date vehicul (JSON canonic Mulberry):\n" + payload + "\n\nÎntrebare:\n" + q,
        }
    ]
    return complete_chat(SYSTEM_FLEET, messages, task="fast_chat", max_completion_tokens=2000)
