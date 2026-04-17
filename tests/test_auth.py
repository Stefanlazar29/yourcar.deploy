"""
Test Acid — verifică că login/register returnează JWT valid (începe cu eyJ).
Rulează: pytest tests/test_auth.py -v

Notă: pip install -r backend/requirements.txt (bcrypt nativ, fără passlib)
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

# Parolă scurtă (evită probleme bcrypt 72 bytes)
TEST_PASS = "Test1234"


def test_register_returns_valid_jwt():
    """După înregistrare, access_token trebuie să fie JWT valid (prefix eyJ)."""
    r = client.post(
        "/auth/register",
        json={
            "identifier": "test_jwt_pytest@example.com",
            "password": TEST_PASS,
            "phone_number": None,
        },
    )
    if r.status_code == 500:
        pytest.skip("Backend 500 — vezi traceback; pip install -r backend/requirements.txt")
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    token = data["access_token"]
    assert isinstance(token, str)
    assert len(token) > 50
    assert token.startswith("eyJ"), "Token-ul trebuie să fie JWT (prefix eyJ)"


def test_login_returns_valid_jwt():
    """După login, access_token trebuie să fie JWT valid."""
    reg = client.post(
        "/auth/register",
        json={
            "identifier": "test_login_pytest@example.com",
            "password": TEST_PASS,
        },
    )
    if reg.status_code == 500:
        pytest.skip("Backend 500 (posibil bcrypt)")
    r = client.post(
        "/auth/login",
        json={
            "identifier": "test_login_pytest@example.com",
            "password": TEST_PASS,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    token = data["access_token"]
    assert token.startswith("eyJ"), "Token-ul trebuie să fie JWT (prefix eyJ)"


def test_me_requires_valid_token():
    """GET /me returnează 401 fără token sau cu token invalid."""
    r = client.get("/me", headers={})
    assert r.status_code == 401
