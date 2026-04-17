"""Teste contract MulberryVehicleDTO."""

import pytest

from backend import database
from backend.vehicle_dto import MulberryVehicleDTO, vehicle_dto_from_car_row, vehicle_dto_from_payload


def test_payload_maps_aliases():
    raw = {
        "vin": "WVWZZZ1JZxw000001",
        "brandName": "Škoda",
        "model": "Fabia",
        "serie": "6Y",
        "nr": "B 01 ABC",
        "combustibil": "Benzină",
        "mlbr_code": "MLBR-TEST",
        "km": 120000,
    }
    dto = vehicle_dto_from_payload(raw)
    assert dto.vin == "WVWZZZ1JZXW000001"
    assert dto.marca == "Škoda"
    assert dto.plate == "B 01 ABC"
    assert dto.km_actuali == 120000
    assert dto.mlbr_id == "MLBR-TEST"


def test_payload_invalid_vin():
    with pytest.raises(ValueError):
        vehicle_dto_from_payload({"vin": "SHORT", "marca": "X"})


def test_car_row_roundtrip():
    car = database.CarRow(
        id=1,
        user_id=1,
        ycr_id="YCR-1",
        make="Skoda",
        model="Fabia",
        year="2004",
        fuel="Benzină",
        plate="B 99 XYZ",
        vin="WVWZZZ1JZXW000099",
        series="6Y",
        ycr_code=None,
        km_actuali=90000,
        rca_expiry="2026-01-01",
        itp_expiry="2026-06-01",
        ycs_score=88.5,
        updated_at=None,
        mlbr_code="MLBR-99",
    )
    dto = vehicle_dto_from_car_row(car)
    assert isinstance(dto, MulberryVehicleDTO)
    assert dto.vin == "WVWZZZ1JZXW000099"
    assert dto.ycs_score == 88.5
