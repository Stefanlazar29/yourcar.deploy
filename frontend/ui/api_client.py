import requests
from typing import Optional, Dict, Any
import json


class ApiClient:
    """HTTP client wrapper for Mulberry API."""

    def __init__(self, base_url: str = "http://46.225.100.8:8080"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.email: Optional[str] = None
        self.phone: Optional[str] = None

    def set_token(self, token: str, user_id: int, email: Optional[str] = None, phone: Optional[str] = None):
        """Set authentication token."""
        self.token = token
        self.user_id = user_id
        self.email = email
        self.phone = phone

    def clear_token(self):
        """Clear authentication token."""
        self.token = None
        self.user_id = None
        self.email = None
        self.phone = None

    def _headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def register(self, email: Optional[str] = None, phone: Optional[str] = None, password: str = "") -> Dict[str, Any]:
        """Register a new user."""
        if not email and not phone:
            raise ValueError("Either email or phone must be provided")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        payload = {
            "email": email,
            "phone": phone,
            "password": password
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/register",
                json=payload,
                headers=self._headers(),
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            self.set_token(data["token"], data["user_id"], data.get("email"), data.get("phone"))
            return data
        except requests.exceptions.RequestException as e:
            raise Exception(f"Registration failed: {str(e)}")

    def login(self, email: Optional[str] = None, phone: Optional[str] = None, password: str = "") -> Dict[str, Any]:
        """Login a user."""
        if not email and not phone:
            raise ValueError("Either email or phone must be provided")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        payload = {
            "email": email,
            "phone": phone,
            "password": password
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/login",
                json=payload,
                headers=self._headers(),
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            self.set_token(data["token"], data["user_id"], data.get("email"), data.get("phone"))
            return data
        except requests.exceptions.RequestException as e:
            raise Exception(f"Login failed: {str(e)}")

    def health_check(self) -> bool:
        """Check if backend is running."""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                headers=self._headers(),
                timeout=5
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
