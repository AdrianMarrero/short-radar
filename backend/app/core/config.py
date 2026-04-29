"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")

    # External APIs
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    fred_api_key: str = Field(default="", alias="FRED_API_KEY")

    # General
    env: str = Field(default="development", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    admin_token: str = Field(default="change-me", alias="ADMIN_TOKEN")

    # Scoring weights
    weight_technical: float = Field(default=0.30, alias="WEIGHT_TECHNICAL")
    weight_news: float = Field(default=0.25, alias="WEIGHT_NEWS")
    weight_fundamental: float = Field(default=0.20, alias="WEIGHT_FUNDAMENTAL")
    weight_macro: float = Field(default=0.15, alias="WEIGHT_MACRO")
    weight_liquidity: float = Field(default=0.10, alias="WEIGHT_LIQUIDITY")

    # Universe sizing (per-market cap to keep free-tier execution under time limits)
    max_tickers_per_market: int = Field(default=80, alias="MAX_TICKERS_PER_MARKET")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_database_url(self) -> str:
        """Returns DATABASE_URL or fallback to local SQLite."""
        if self.database_url:
            # Render usa postgres://, SQLAlchemy 2.x requiere postgresql://
            return self.database_url.replace("postgres://", "postgresql://", 1)
        return "sqlite:///./short_radar.db"

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
