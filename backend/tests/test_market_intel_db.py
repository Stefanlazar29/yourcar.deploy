"""Teste SQLite market intel (fără rețea)."""

from pathlib import Path

import pytest

from backend import database


@pytest.fixture
def intel_db(monkeypatch, tmp_path):
    dbp = str(tmp_path / "mi.db")
    monkeypatch.setattr(database, "DB_PATH", dbp)
    database.init_db()
    yield dbp
    Path(dbp).unlink(missing_ok=True)


def test_synthesis_roundtrip(intel_db):
    mk = database.MODEL_KEY_SKODA_FABIA_6Y
    database.market_intel_replace_sources(
        mk,
        [
            {
                "source_url": "https://en.wikipedia.org/wiki/X",
                "source_title": "T1",
                "source_type": "test",
                "lang": "en",
                "raw_excerpt": "abc",
            }
        ],
    )
    database.market_intel_set_synthesis(
        mk, "rezumat test", '{"a":1}', 1, groq_model="test-model"
    )
    row = database.market_intel_get_synthesis(mk)
    assert row is not None
    assert "rezumat test" in row["synthesis_ro"]
    assert row["sources_count"] == 1
    src = database.market_intel_list_sources(mk)
    assert len(src) == 1
