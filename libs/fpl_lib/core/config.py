"""Application configuration using Pydantic BaseSettings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class FPLSettings(BaseSettings):
    """Base settings for FPL services. Extend per-service."""

    ENV: Literal["dev", "prod"] = "dev"
    AWS_REGION: str = "eu-west-2"
    DATA_LAKE_BUCKET: str = "fpl-data-lake-dev"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> FPLSettings:
    """Return cached settings instance."""
    return FPLSettings()
