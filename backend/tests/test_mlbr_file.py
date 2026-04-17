"""Teste MLBR Digital File — semnătură HMAC."""

import pytest

from backend import mlbr_file


def test_generate_and_verify_roundtrip():
  car = {
    "vin": "WVWZZZ1JZXW000001",
    "plate": "B 01 ABC",
    "make": "Skoda",
    "model": "Fabia",
    "series": "6Y",
    "year": "2004",
    "fuel": "Benzină",
    "ycr_id": "",
  }
  user = {"identifier": "test@example.com", "id": 1}
  p = mlbr_file.generate_mlbr_file(car, user, mlbr_id_override="MLBR-TEST-1234")
  assert p["signature"]
  assert mlbr_file.verify_mlbr_file(dict(p))
  p2 = dict(p)
  p2["model"] = "Octavia"
  assert not mlbr_file.verify_mlbr_file(p2)


def test_normalize_mlbr_id():
  assert mlbr_file.normalize_mlbr_id("MLBR 12 34 - AB") == "MLBR-12-34-AB"
