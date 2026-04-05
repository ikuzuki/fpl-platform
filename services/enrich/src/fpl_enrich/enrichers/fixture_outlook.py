"""Fixture outlook enricher — assesses upcoming fixture difficulty."""

import logging
from typing import Any

from pydantic import ValidationError

from fpl_enrich.enrichers.base import FPLEnricher
from fpl_enrich.enrichers.models import FixtureOutlookOutput
from fpl_enrich.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class FixtureOutlookEnricher(FPLEnricher):
    """Assess fixture difficulty outlook for FPL transfer decisions.

    Uses Sonnet for complex reasoning about fixture runs.
    Batch size of 5 balances context size with cost efficiency.
    """

    BATCH_SIZE = 5
    MODEL = "claude-sonnet-4-6-20250514"

    def _get_system_prompt(self) -> str:
        return load_prompt("fixture_outlook", self.prompt_version)

    def _validate_output(self, output: dict[str, Any]) -> dict[str, Any] | None:
        try:
            validated = FixtureOutlookOutput.model_validate(output)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning("Invalid fixture outlook output: %s", e)
            return None
