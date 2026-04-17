"""
Persistare insight SoftScore multi-factor — apelat din API și din job-uri background (ex. după upload Cloud).
"""

from __future__ import annotations

import threading
from typing import Optional

from backend import database, valuation_engine
from backend.vehicle_dto import market_intel_synthesis_row_for_dto, vehicle_dto_from_car_row


def persist_multifactor_insight_for_vehicle(user_id: int, vin: str) -> Optional[int]:
  """
  Recalculează SoftScore v1 pentru mașina user+VIN și inserează în vehicle_insights.
  Returnează id insight sau None dacă nu există mașina.
  """
  vin_norm = (vin or "").strip().upper()
  if len(vin_norm) != 17:
    return None
  car = database.get_car_by_user_and_vin(user_id, vin_norm)
  if not car:
    return None
  try:
    v = vehicle_dto_from_car_row(car)
  except ValueError:
    return None
  intel_row = market_intel_synthesis_row_for_dto(v)
  base_eur, base_src = valuation_engine.resolve_market_base_eur(v, intel_row)
  calc = valuation_engine.calculate_softscore(v, base_eur)
  analysis = {
    "reply": calc["reply"],
    "softscore": calc["softscore"],
    "market_value": calc["market_value_eur"],
    "currency": calc["currency"],
    "market_base_eur": calc["market_base_eur"],
    "base_source": base_src,
    "health_band": calc["health_band"],
    "breakdown": calc["breakdown"],
    "kind": "softscore_multifactor_v1",
  }
  aid = database.vehicle_insight_insert(
    user_id,
    v.vin,
    valuation_engine.SOFTSCORE_INSIGHT_QUESTION_V1,
    analysis,
    score=calc["softscore"],
  )

  def _bg_market_snapshot() -> None:
    try:
      from backend.softscore_market_groq import background_snapshot_for_vehicle

      background_snapshot_for_vehicle(user_id, vin_norm)
    except Exception:
      pass

  threading.Thread(target=_bg_market_snapshot, daemon=True).start()
  return aid
