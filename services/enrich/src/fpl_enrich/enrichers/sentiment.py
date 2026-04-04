"""Sentiment enricher — analyses media sentiment about players."""

import logging
from typing import Any

from pydantic import ValidationError

from fpl_enrich.enrichers.base import FPLEnricher
from fpl_enrich.enrichers.models import SentimentOutput
from fpl_enrich.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class SentimentEnricher(FPLEnricher):
    """Assess media sentiment from news and social media mentions.

    Uses Haiku for bulk processing. Batch size of 5 for simple classification.
    """

    BATCH_SIZE = 5
    MODEL = "claude-haiku-4-5-20251001"

    def _get_system_prompt(self) -> str:
        return load_prompt("sentiment", self.prompt_version)

    def _validate_output(self, output: dict[str, Any]) -> dict[str, Any] | None:
        try:
            validated = SentimentOutput.model_validate(output)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning("Invalid sentiment output: %s", e)
            return None
