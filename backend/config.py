import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jwt_secret: str
    database_url: str = "postgresql://mulberry_user:mulberry_pass@localhost/mulberry"
    jwt_expiry_hours: int = 24
    cors_origins: list[str] = [
        "http://localhost:8000",
        "http://localhost:5000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://46.225.100.151:8080",
        "null",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **data):
        super().__init__(**data)
        if not self.jwt_secret:
            raise ValueError("JWT_SECRET environment variable is required")


settings = Settings()
