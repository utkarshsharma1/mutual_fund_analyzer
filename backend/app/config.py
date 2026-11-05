"""Configuration management for the Stateless Indian Mutual Fund Evaluation Agent."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    risk_free_rate: float = float(os.getenv("RISK_FREE_RATE", "0.066"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "1800"))
    http_timeout_seconds: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20.0"))
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    )


settings = Settings()

