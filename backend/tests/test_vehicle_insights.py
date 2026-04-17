"""Teste vehicle_insights — cache, VIN, izolare user."""

from pathlib import Path

import pytest

from backend import database

_VIN = "WVWZZZ1JZXW000099"


@pytest.fixture
def iso_db(monkeypatch, tmp_path):
    dbp = str(tmp_path / "insights_test.db")
    monkeypatch.setattr(database, "DB_PATH", dbp)
    database.init_db()
    yield dbp
    Path(dbp).unlink(missing_ok=True)


def test_insight_insert_and_cache_hit(iso_db):
    u = database.create_user("insight_u1@t.com", "h1")
    database.upsert_car_for_user(
        u.id,
        {
            "vin": _VIN,
            "make": "Skoda",
            "model": "Fabia",
            "year": "2004",
            "fuel": "B",
            "plate": "B 01",
            "series": "6Y",
            "ycs_score": 81.0,
        },
    )
    iid = database.vehicle_insight_insert(
        u.id,
        _VIN,
        "Care sunt costurile RCA?",
        {"reply": "Text analiză", "vehicle": {"vin": _VIN}},
        score=81.0,
    )
    assert iid > 0
    cached = database.vehicle_insight_get_cached(u.id, _VIN, "Care sunt costurile RCA?", hours=24)
    assert cached is not None
    assert cached["reply"] == "Text analiză"
    assert cached["id"] == iid


def test_insight_get_by_id_rejects_other_user(iso_db):
    u1 = database.create_user("a@t.com", "x")
    u2 = database.create_user("b@t.com", "y")
    database.upsert_car_for_user(
        u1.id,
        {
            "vin": _VIN,
            "make": "S",
            "model": "F",
            "year": "2004",
            "fuel": "B",
            "plate": "B",
            "series": "6Y",
        },
    )
    iid = database.vehicle_insight_insert(
        u1.id,
        _VIN,
        "Q?",
        {"reply": "secret"},
        score=None,
    )
    assert database.vehicle_insight_get_by_id(u1.id, iid, _VIN) is not None
    assert database.vehicle_insight_get_by_id(u2.id, iid, _VIN) is None


def test_question_hash_normalizes_whitespace(iso_db):
    u = database.create_user("norm@t.com", "z")
    database.upsert_car_for_user(
        u.id,
        {
            "vin": _VIN,
            "make": "S",
            "model": "F",
            "year": "2004",
            "fuel": "B",
            "plate": "B",
            "series": "6Y",
        },
    )
    database.vehicle_insight_insert(u.id, _VIN, "Same  question", {"reply": "x"}, score=None)
    assert database.vehicle_insight_get_cached(u.id, _VIN, "  same   question  ", hours=24) is not None
