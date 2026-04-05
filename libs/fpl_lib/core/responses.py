"""Standard response models for Lambda handlers."""

from typing import Literal

from pydantic import BaseModel


class CollectionResponse(BaseModel):
    """Response from a data collection Lambda."""

    status: Literal["success", "partial", "failed"]
    records_collected: int
    output_path: str


class ValidationResult(BaseModel):
    """Response from a data validation Lambda."""

    status: Literal["valid", "invalid", "partial"]
    errors: list[str] = []
    warnings: list[str] = []
    records_valid: int = 0
    records_invalid: int = 0


class EnrichmentResult(BaseModel):
    """Response from an LLM enrichment Lambda."""

    status: Literal["success", "partial", "failed"]
    records_enriched: int = 0
    records_failed: int = 0
    cost_usd: float = 0.0
    model: str = ""


class CurationResult(BaseModel):
    """Response from a data curation Lambda."""

    status: Literal["success", "partial", "failed"]
    datasets_written: list[str] = []
    row_counts: dict[str, int] = {}
    output_paths: list[str] = []
