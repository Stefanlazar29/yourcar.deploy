# -*- coding: utf-8 -*-
"""
Contract unic vehicul Mulberry (DTO) — „legea” pentru JSON API și pentru analiză LLM.

Orice ieșire canonică spre client sau spre Groq trece prin MulberryVehicleDTO.
Mapări acceptate din surse haotice: make/marca/brandName, plate/nr, series/serie, etc.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, field_validator

from backend import database


def _strip(s: Optional[Union[str, int, float]]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


def _norm_vin(raw: Optional[str]) -> str:
    s = _strip(raw) or ""
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


class MulberryVehicleDTO(BaseModel):
    """Model canonic — aliniază UI, SQLite (cars) și prompturi LLM."""

    vin: str = Field(..., min_length=1, description="VIN normalizat A-Z0-9")
    mlbr_id: Optional[str] = None
    marca: Optional[str] = None
    model: Optional[str] = None
    series: Optional[str] = None
    an: Optional[str] = None
    plate: Optional[str] = None
    fuel: Optional[str] = None
    km_actuali: Optional[int] = None
    rca_expiry: Optional[str] = None
    itp_expiry: Optional[str] = None
    ycs_score: Optional[float] = Field(None, description="Scor software din backend (cars.ycs_score), dacă există")

    model_config = {"extra": "forbid"}

    @field_validator("vin", mode="before")
    @classmethod
    def validate_vin(cls, v: Any) -> str:
        nv = _norm_vin(v if isinstance(v, str) else str(v) if v is not None else "")
        if len(nv) != 17:
            raise ValueError("VIN trebuie să aibă exact 17 caractere alfanumerice.")
        return nv

    @field_validator("km_actuali", mode="before")
    @classmethod
    def coerce_km(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None


def _first(*vals: Optional[str]) -> Optional[str]:
    for x in vals:
        t = _strip(x)
        if t:
            return t
    return None


def vehicle_dto_from_payload(raw: Dict[str, Any]) -> MulberryVehicleDTO:
    """
    Construiește DTO din dict client (localStorage, body JSON) cu chei eterogene.
    Ridică ValueError dacă VIN invalid — apelatorul → HTTP 400.
    """
    if not raw:
        raise ValueError("Payload vehicul gol.")
    d = raw
    vin = _norm_vin(d.get("vin"))
    if len(vin) != 17:
        raise ValueError("VIN invalid în payload.")

    marca = _first(
        d.get("marca"),
        d.get("make"),
        d.get("brand"),
        d.get("brandName"),
        d.get("marca_auto"),
    )
    model = _first(d.get("model"), d.get("modelName"), d.get("modelo"))
    series = _first(d.get("series"), d.get("serie"), d.get("ycr_series"))
    an = _first(d.get("an"), d.get("year"))
    plate = _first(d.get("plate"), d.get("nr"), d.get("plateNumber"))
    fuel = _first(d.get("fuel"), d.get("combustibil"))
    mlbr = _first(d.get("mlbr_id"), d.get("mlbr_code"), d.get("ycr_id"))

    km = d.get("km_actuali")
    if km is None:
        km = d.get("km")

    ycs = d.get("ycs_score")
    if ycs is None:
        ycs = d.get("soft_score")

    return MulberryVehicleDTO(
        vin=vin,
        mlbr_id=mlbr,
        marca=marca,
        model=model,
        series=series,
        an=an,
        plate=plate,
        fuel=fuel,
        km_actuali=km,
        rca_expiry=_strip(d.get("rca_expiry")),
        itp_expiry=_strip(d.get("itp_expiry")),
        ycs_score=float(ycs) if ycs is not None and str(ycs).strip() != "" else None,
    )


def vehicle_dto_from_car_row(car: database.CarRow) -> MulberryVehicleDTO:
    """Filtrează rând SQLite prin contractul canonic."""
    vin = _norm_vin(car.vin)
    if len(vin) != 17:
        raise ValueError("VIN invalid în baza de date pentru acest utilizator.")
    mlbr = database.resolve_mlbr_id_for_car(car)
    return MulberryVehicleDTO(
        vin=vin,
        mlbr_id=_strip(mlbr) or None,
        marca=_strip(car.make),
        model=_strip(car.model),
        series=_strip(car.series),
        an=_strip(car.year),
        plate=_strip(car.plate),
        fuel=_strip(car.fuel),
        km_actuali=car.km_actuali,
        rca_expiry=_strip(car.rca_expiry),
        itp_expiry=_strip(car.itp_expiry),
        ycs_score=float(car.ycs_score) if car.ycs_score is not None else None,
    )


def market_intel_synthesis_row_for_dto(v: MulberryVehicleDTO) -> Optional[dict]:
    """
    Rând `market_intel_synthesis` când profilul se potrivește cu enciclopedia stocată (ex. Škoda Fabia 6Y).
    """
    mk = (v.marca or "").lower().replace("š", "s")
    md = (v.model or "").lower()
    sr = (v.series or "").lower().replace("š", "s")
    if "skoda" not in mk or "fabia" not in md:
        return None
    try:
        y = int(str(v.an or "").strip()[:4])
    except (TypeError, ValueError):
        y = None
    if y is not None and 1999 <= y <= 2007:
        return database.market_intel_get_synthesis(database.MODEL_KEY_SKODA_FABIA_6Y)
    if any(x in sr or x in md for x in ("6y", "mk1", "typ 6y")):
        return database.market_intel_get_synthesis(database.MODEL_KEY_SKODA_FABIA_6Y)
    return None
