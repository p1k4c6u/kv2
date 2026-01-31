# config.py
"""
Configuration and environment variables for the API.
"""

import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

    # Authentication
    APP_PASSWORD: str = os.environ.get("APP_PASSWORD", "changeme")
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 7

    # OpenRouter API
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.environ.get(
        "OPENROUTER_MODEL", "anthropic/claude-sonnet-4"
    )

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # Add production URLs from environment
    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "")

    def __init__(self):
        if self.FRONTEND_URL:
            self.CORS_ORIGINS.append(self.FRONTEND_URL)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
