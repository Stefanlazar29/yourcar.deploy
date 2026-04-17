"""Test formulă SoftScore multi-factor (depreciere aditivă din 100)."""

from backend.vehicle_dto import MulberryVehicleDTO
from backend import valuation_engine


def _dto(**kwargs) -> MulberryVehicleDTO:
    base = {
        "vin": "TM9B631N30B123456",
        "marca": "Skoda",
        "model": "Fabia",
        "an": "2004",
        "km_actuali": 200000,
        "rca_expiry": None,
        "itp_expiry": None,
    }
    base.update(kwargs)
    return MulberryVehicleDTO(**base)


def test_softscore_age_km_only_2026():
    # vârstă 22 → peste 15 cu 7 ani → 14 pt; km 200k → 50k/20k = 2.5 → scor 83.5
    out = valuation_engine.calculate_softscore(_dto(), 4000.0, current_year=2026)
    assert out["softscore"] == 83.5
    assert out["breakdown"]["pen_varsta"] == 14.0
    assert out["breakdown"]["pen_km"] == 2.5
    assert out["breakdown"]["pen_documente"] == 0.0
    assert out["market_value_eur"] == round(4000.0 * 0.835, 2)


def test_softscore_documents_penalty():
    out = valuation_engine.calculate_softscore(
        _dto(rca_expiry="2020-01-01", itp_expiry="2027-01-01"),
        3000.0,
        current_year=2026,
    )
    # RCA expirat → urgență documente
    assert out["breakdown"]["pen_documente"] == 10.0
    assert out["softscore"] == 73.5


def test_softscore_clamped_at_zero():
    out = valuation_engine.calculate_softscore(
        _dto(an="1980", km_actuali=1_200_000),
        5000.0,
        current_year=2026,
    )
    assert out["softscore"] == 0.0
