"""Enrichment service configuration extending base FPL settings."""

from functools import lru_cache

from fpl_lib.core.config import FPLSettings


class EnrichSettings(FPLSettings):
    """Settings for the enrichment service, including Langfuse credentials."""

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    COST_BUCKET: str = "fpl-data-lake-dev"
    PROMPT_VERSION: str = "v1"


@lru_cache
def get_enrich_settings() -> EnrichSettings:
    """Return cached enrichment settings instance."""
    return EnrichSettings()
