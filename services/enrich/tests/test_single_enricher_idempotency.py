"""Unit tests for the enrichers' skip-if-already-enriched guard.

Enrichment is the only paid step in the pipeline, and it had no idempotency
check while transform and curate_all both did — so a repeat run bought a full
LLM pass to rewrite identical output.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fpl_enrich.handlers.single_enricher import (
    _already_enriched,
    _enriched_output_key,
    sentiment_main,
)


def _s3(exists: bool) -> MagicMock:
    client = MagicMock()
    client.object_exists.return_value = exists
    return client


def test_output_key_is_partitioned_by_season_and_gameweek() -> None:
    key = _enriched_output_key("sentiment", "2026-27", 7)
    assert key == "enriched/sentiment/season=2026-27/gameweek=07/results.json"


def test_already_enriched_returns_none_when_output_is_absent() -> None:
    assert _already_enriched(_s3(False), "bucket", "sentiment", "2026-27", 7) is None


def test_already_enriched_reports_zero_cost_when_output_exists() -> None:
    result = _already_enriched(_s3(True), "bucket", "sentiment", "2026-27", 7)

    assert result is not None
    assert result["skipped"] is True
    assert result["cost"]["cost_usd"] == 0.0
    assert result["records_enriched"] == 0


@pytest.mark.asyncio
async def test_enricher_makes_no_llm_call_when_the_gameweek_is_already_enriched() -> None:
    """The guard must sit ahead of the secret fetch and the Anthropic client."""
    secret = MagicMock()
    runner = AsyncMock()

    with (
        patch("fpl_enrich.handlers.single_enricher.S3Client", return_value=_s3(True)),
        patch("fpl_enrich.handlers.single_enricher._get_secret", secret),
        patch("fpl_enrich.handlers.single_enricher._run_single_enricher", runner),
    ):
        result = await sentiment_main(season="2026-27", gameweek=7)

    assert result["skipped"] is True
    secret.assert_not_called()
    runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_force_re_enriches_even_when_output_exists() -> None:
    runner = AsyncMock(return_value={"enricher": "sentiment"})

    with (
        patch("fpl_enrich.handlers.single_enricher.S3Client", return_value=_s3(True)),
        patch("fpl_enrich.handlers.single_enricher._load_players", return_value=[]),
        patch("fpl_enrich.handlers.single_enricher._load_news_articles", return_value=[]),
        patch("fpl_enrich.handlers.single_enricher._attach_news_to_players", return_value=[]),
        patch("fpl_enrich.handlers.single_enricher._get_secret", return_value="key"),
        patch("fpl_enrich.handlers.single_enricher.anthropic"),
        patch("fpl_enrich.handlers.single_enricher._run_single_enricher", runner),
    ):
        result = await sentiment_main(season="2026-27", gameweek=7, force=True)

    assert "skipped" not in result
    runner.assert_awaited_once()
