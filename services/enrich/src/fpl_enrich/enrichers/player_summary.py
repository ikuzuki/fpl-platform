"""Player summary enricher — generates form summaries from recent gameweek stats."""

import logging
from typing import Any

from pydantic import ValidationError

from fpl_enrich.enrichers.base import FPLEnricher
from fpl_enrich.enrichers.models import PlayerSummaryOutput
from fpl_enrich.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class PlayerSummaryEnricher(FPLEnricher):
    """Summarise player form over a rolling gameweek window.

    Uses Haiku for bulk processing. Batch size of 10 for cost efficiency.
    """

    BATCH_SIZE = 10
    MODEL = "claude-haiku-4-5-20251001"
    RELEVANT_FIELDS = [
        "web_name",
        "team",
        "element_type",
        "total_points",
        "minutes",
        "goals_scored",
        "assists",
        "clean_sheets",
        "bonus",
        "form",
        "points_per_game",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "understat_xg",
        "understat_xa",
        "understat_npxg",
    ]

    def __init__(self, *args: Any, window_size: int = 5, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.window_size = window_size

    def _get_system_prompt(self) -> str:
        template = load_prompt("player_summary", self.prompt_version)
        return template.format(window_size=self.window_size, batch_size="{batch_size}")

    def _validate_output(self, output: dict[str, Any]) -> dict[str, Any] | None:
        try:
            validated = PlayerSummaryOutput.model_validate(output)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning("Invalid player summary output: %s", e)
            return None
