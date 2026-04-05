"""Lambda handler for LLM enrichment of player data."""

import asyncio
import logging
from typing import Any

import anthropic
import boto3
import pyarrow as pa
from langfuse import observe

from fpl_enrich.enrichers.base import RateLimiter
from fpl_enrich.enrichers.fixture_outlook import FixtureOutlookEnricher
from fpl_enrich.enrichers.injury_signal import InjurySignalEnricher
from fpl_enrich.enrichers.player_summary import PlayerSummaryEnricher
from fpl_enrich.enrichers.sentiment import SentimentEnricher
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

# Cost rates per million tokens (USD)
COST_RATES: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4-6-20250514": {"input": 3.0, "output": 15.0},
}


def _get_secret(secret_name: str, region: str = "eu-west-2") -> str:
    """Retrieve a secret value from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]


def _calculate_cost(enrichers: list[Any]) -> dict[str, Any]:
    """Build cost report from enricher token usage."""
    total_input = 0
    total_output = 0
    total_cost = 0.0
    model_breakdown: dict[str, dict[str, Any]] = {}

    for enricher in enrichers:
        model = enricher.MODEL
        rates = COST_RATES.get(model, {"input": 0.0, "output": 0.0})
        input_cost = enricher.total_input_tokens * rates["input"] / 1_000_000
        output_cost = enricher.total_output_tokens * rates["output"] / 1_000_000
        cost = input_cost + output_cost

        total_input += enricher.total_input_tokens
        total_output += enricher.total_output_tokens
        total_cost += cost

        model_breakdown[enricher.__class__.__name__] = {
            "model": model,
            "input_tokens": enricher.total_input_tokens,
            "output_tokens": enricher.total_output_tokens,
            "cost_usd": round(cost, 6),
        }

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_usd": round(total_cost, 6),
        "model_breakdown": model_breakdown,
    }


def _read_cached_summaries(
    s3_client: S3Client,
    bucket: str,
    season: str,
    gameweek: int,
) -> list[dict[str, Any]] | None:
    """Try to read enriched summaries from the previous gameweek as fallback."""
    if gameweek <= 1:
        return None
    prev_gw = gameweek - 1
    key = f"enriched/player_summaries/season={season}/gameweek={prev_gw:02d}/summaries.parquet"
    if not s3_client.object_exists(bucket, key):
        return None
    table = s3_client.read_parquet(bucket, key)
    return table.to_pydict()


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


async def _run_enricher(
    enricher: Any,
    players: list[dict[str, Any]],
    s3_client: S3Client,
    bucket: str,
    season: str,
    gameweek: int,
) -> tuple[str, list[dict[str, Any] | None]]:
    """Run a single enricher with fallback handling. Returns (name, results)."""
    name = enricher.__class__.__name__
    try:
        results = await enricher.apply(players)
        return (name, results)
    except anthropic.RateLimitError:
        logger.warning("%s hit rate limit — falling back to cached summaries", name)
        cached = _read_cached_summaries(s3_client, bucket, season, gameweek)
        return (name, [cached] if cached else [None] * len(players))
    except anthropic.APIError as e:
        logger.error("%s API error: %s — writing to DLQ", name, e)
        dlq_key = f"dlq/enrichment/season={season}/gameweek={gameweek:02d}/{name}.json"
        s3_client.put_json(bucket, dlq_key, {"error": str(e), "player_count": len(players)})
        return (name, [None] * len(players))


@observe(name="enrich_gameweek")
async def main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    cost_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run all enrichers on clean player data and write results to S3."""
    logger.info("Starting enrichment for %s GW%d", season, gameweek)
    s3_client = S3Client()

    # Read clean player data
    clean_key = f"clean/players/season={season}/gameweek={gameweek:02d}/players.parquet"
    table = s3_client.read_parquet(output_bucket, clean_key)
    players = table.to_pylist()
    logger.info("Read %d players from %s", len(players), clean_key)

    # Get API key from Secrets Manager
    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    async_client = anthropic.AsyncAnthropic(api_key=api_key)

    # Shared rate limiter — Tier 1 is 50 RPM, target 40 RPM to leave headroom
    rate_limiter = RateLimiter(requests_per_minute=40)

    # Initialise enrichers with shared client and rate limiter
    summary_enricher = PlayerSummaryEnricher(
        anthropic_client=async_client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    injury_enricher = InjurySignalEnricher(
        anthropic_client=async_client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    sentiment_enricher = SentimentEnricher(
        anthropic_client=async_client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    fixture_enricher = FixtureOutlookEnricher(
        anthropic_client=async_client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    all_enrichers = [summary_enricher, injury_enricher, sentiment_enricher, fixture_enricher]

    # Filter top 200 players by ownership for expensive Sonnet fixture outlook
    fixture_outlook_limit = 200
    top_player_ids = {
        p.get("id")
        for p in sorted(
            players,
            key=lambda p: float(p.get("selected_by_percent", 0)),
            reverse=True,
        )[:fixture_outlook_limit]
    }
    fixture_players = [p for p in players if p.get("id") in top_player_ids]
    logger.info(
        "Fixture outlook: %d/%d players (top by ownership)",
        len(fixture_players),
        len(players),
    )

    # Run Haiku enrichers on all players, Sonnet fixture outlook on top 200 only
    enricher_tasks = [
        _run_enricher(summary_enricher, players, s3_client, output_bucket, season, gameweek),
        _run_enricher(injury_enricher, players, s3_client, output_bucket, season, gameweek),
        _run_enricher(sentiment_enricher, players, s3_client, output_bucket, season, gameweek),
        _run_enricher(
            fixture_enricher, fixture_players, s3_client, output_bucket, season, gameweek
        ),
    ]
    enricher_outputs = await asyncio.gather(*enricher_tasks)

    # Build lookup for fixture outlook results (indexed by player id)
    fixture_name, fixture_results = enricher_outputs[3]
    fixture_by_id: dict[Any, dict[str, Any] | None] = {}
    for player, result in zip(fixture_players, fixture_results, strict=True):
        fixture_by_id[player.get("id")] = result

    # Merge enrichment results into player records
    enriched_players = []
    for i, player in enumerate(players):
        enriched = dict(player)
        # Haiku enrichers — aligned 1:1 with full player list
        for name, enricher_results in enricher_outputs[:3]:
            if i < len(enricher_results) and enricher_results[i] is not None:
                prefix = name.replace("Enricher", "").lower()
                for key, value in enricher_results[i].items():
                    enriched[f"{prefix}_{key}"] = value
        # Fixture outlook — lookup by player id (None if not in top 200)
        fixture_result = fixture_by_id.get(player.get("id"))
        if fixture_result is not None:
            for key, value in fixture_result.items():
                enriched[f"fixtureoutlook_{key}"] = value
        enriched_players.append(enriched)

    # Write enriched Parquet
    enriched_table = pa.Table.from_pylist(enriched_players)
    enriched_key = (
        f"enriched/player_summaries/season={season}/gameweek={gameweek:02d}/summaries.parquet"
    )
    s3_client.write_parquet(output_bucket, enriched_key, enriched_table)
    logger.info("Wrote enriched data to s3://%s/%s", output_bucket, enriched_key)

    # Write cost report
    cost_report = _calculate_cost(all_enrichers)
    cost_key = f"reports/costs/season={season}/gameweek={gameweek:02d}/cost_report.json"
    s3_client.put_json(cost_bucket, cost_key, cost_report)
    logger.info("Wrote cost report to s3://%s/%s", cost_bucket, cost_key)

    total_enriched = sum(
        1 for p in enriched_players if any(k.startswith("playersummary_") for k in p)
    )

    return {
        "status": "success" if total_enriched == len(players) else "partial",
        "records_enriched": total_enriched,
        "records_failed": len(players) - total_enriched,
        "cost_usd": cost_report["estimated_cost_usd"],
        "output_path": enriched_key,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for enrichment."""
    _init_langfuse()
    return RunHandler(
        main_func=main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "cost_bucket", "prompt_version"],
    ).lambda_executor(lambda_event=event)
