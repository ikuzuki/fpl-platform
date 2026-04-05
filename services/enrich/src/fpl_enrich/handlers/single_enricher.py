"""Lambda handlers for individual enrichers.

Each handler runs a single enricher on the top N players by ownership,
writes the enricher-specific output to S3, and returns a cost summary.
Designed to be invoked in parallel via Step Functions Parallel state.
"""

import logging
from typing import Any

import anthropic
import boto3
from langfuse import observe

from fpl_enrich.enrichers.base import RateLimiter
from fpl_enrich.enrichers.fixture_outlook import FixtureOutlookEnricher
from fpl_enrich.enrichers.injury_signal import InjurySignalEnricher
from fpl_enrich.enrichers.player_summary import PlayerSummaryEnricher
from fpl_enrich.enrichers.sentiment import SentimentEnricher
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

# Tier 1: 50 RPM per model, 10K output TPM for Haiku, 8K for Sonnet.
# Rate limits are per-model, so 3 parallel Haiku Lambdas share 50 RPM / 10K TPM.
# At ~700 output tokens per batch: 10K TPM / 700 ≈ 14 RPM total for Haiku.
# Split across 3 Lambdas → 5 RPM each. Sonnet runs alone at 15 RPM.
HAIKU_RPM = 5
SONNET_RPM = 15

# Cost rates per million tokens (USD)
COST_RATES: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
}

ENRICHMENT_LIMIT = 300


def _get_secret(secret_name: str, region: str = "eu-west-2") -> str:
    """Retrieve a secret value from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]


def _init_langfuse(region: str = "eu-west-2") -> None:
    """Initialise Langfuse with keys from Secrets Manager."""
    import os

    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        os.environ["LANGFUSE_PUBLIC_KEY"] = _get_secret(
            "/fpl-platform/dev/langfuse-public-key", region
        )
    if not os.environ.get("LANGFUSE_SECRET_KEY"):
        os.environ["LANGFUSE_SECRET_KEY"] = _get_secret(
            "/fpl-platform/dev/langfuse-secret-key", region
        )


def _load_players(
    s3_client: S3Client, bucket: str, season: str, gameweek: int
) -> list[dict[str, Any]]:
    """Read clean player data and return top N by ownership."""
    clean_key = f"clean/players/season={season}/gameweek={gameweek:02d}/players.parquet"
    table = s3_client.read_parquet(bucket, clean_key)
    all_players = table.to_pylist()

    sorted_players = sorted(
        all_players,
        key=lambda p: float(p.get("selected_by_percent", 0)),
        reverse=True,
    )
    players = sorted_players[:ENRICHMENT_LIMIT]
    logger.info(
        "Loaded %d/%d players by ownership for enrichment",
        len(players),
        len(all_players),
    )
    return players


def _calculate_single_cost(enricher: Any) -> dict[str, Any]:
    """Build cost report for a single enricher."""
    model = enricher.MODEL
    rates = COST_RATES.get(model, {"input": 0.0, "output": 0.0})
    input_cost = enricher.total_input_tokens * rates["input"] / 1_000_000
    output_cost = enricher.total_output_tokens * rates["output"] / 1_000_000
    return {
        "model": model,
        "input_tokens": enricher.total_input_tokens,
        "output_tokens": enricher.total_output_tokens,
        "cost_usd": round(input_cost + output_cost, 6),
    }


async def _run_single_enricher(
    enricher_name: str,
    enricher: Any,
    season: str,
    gameweek: int,
    bucket: str,
) -> dict[str, Any]:
    """Run one enricher end-to-end: load data, enrich, write output."""
    s3_client = S3Client()
    players = _load_players(s3_client, bucket, season, gameweek)

    results = await enricher.apply(players)

    # Write per-enricher results as JSON list (player_id → enrichment)
    output_records = []
    for player, result in zip(players, results, strict=True):
        output_records.append(
            {
                "player_id": player.get("id"),
                "enrichment": result,
            }
        )

    output_key = f"enriched/{enricher_name}/season={season}/gameweek={gameweek:02d}/results.json"
    s3_client.put_json(bucket, output_key, output_records)
    logger.info("Wrote %s results to s3://%s/%s", enricher_name, bucket, output_key)

    cost = _calculate_single_cost(enricher)

    return {
        "enricher": enricher_name,
        "records_enriched": enricher.valid_count,
        "records_failed": enricher.invalid_count,
        "cost": cost,
        "output_path": output_key,
    }


# --- Individual enricher main functions -------------------------------------


@observe(name="enrich_player_summary")
async def player_summary_main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run player summary enricher."""
    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=HAIKU_RPM)
    enricher = PlayerSummaryEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher("player_summary", enricher, season, gameweek, output_bucket)


@observe(name="enrich_injury_signal")
async def injury_signal_main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run injury signal enricher."""
    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=HAIKU_RPM)
    enricher = InjurySignalEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher("injury_signal", enricher, season, gameweek, output_bucket)


@observe(name="enrich_sentiment")
async def sentiment_main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run sentiment enricher."""
    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=HAIKU_RPM)
    enricher = SentimentEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher("sentiment", enricher, season, gameweek, output_bucket)


@observe(name="enrich_fixture_outlook")
async def fixture_outlook_main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run fixture outlook enricher."""
    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=SONNET_RPM)
    enricher = FixtureOutlookEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher("fixture_outlook", enricher, season, gameweek, output_bucket)


# --- Lambda entry points ----------------------------------------------------


def player_summary_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for player summary enrichment."""
    _init_langfuse()
    return RunHandler(
        main_func=player_summary_main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "prompt_version"],
    ).lambda_executor(lambda_event=event)


def injury_signal_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for injury signal enrichment."""
    _init_langfuse()
    return RunHandler(
        main_func=injury_signal_main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "prompt_version"],
    ).lambda_executor(lambda_event=event)


def sentiment_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for sentiment enrichment."""
    _init_langfuse()
    return RunHandler(
        main_func=sentiment_main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "prompt_version"],
    ).lambda_executor(lambda_event=event)


def fixture_outlook_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for fixture outlook enrichment."""
    _init_langfuse()
    return RunHandler(
        main_func=fixture_outlook_main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "prompt_version"],
    ).lambda_executor(lambda_event=event)
