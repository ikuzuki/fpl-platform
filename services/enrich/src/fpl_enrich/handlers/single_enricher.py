"""Lambda handlers for individual enrichers.

Each handler runs a single enricher on the top N players by ownership,
writes the enricher-specific output to S3, and returns a cost summary.
Designed to be invoked in parallel via Step Functions Parallel state.
"""

import json
import logging
from datetime import UTC, datetime
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


def _load_news_articles(s3_client: S3Client, bucket: str) -> list[dict[str, Any]]:
    """Load recent news articles from S3. Returns list of article dicts."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"raw/news/date={today}/rss_articles.jsonl"

    if not s3_client.object_exists(bucket, key):
        logger.warning("No news articles found at %s", key)
        return []

    raw = s3_client.read_json(bucket, key)
    if isinstance(raw, str):
        # JSONL format — parse each line
        articles = [json.loads(line) for line in raw.strip().split("\n") if line.strip()]
    elif isinstance(raw, list):
        articles = raw
    else:
        logger.warning("Unexpected news format: %s", type(raw))
        return []

    logger.info("Loaded %d news articles", len(articles))
    return articles


def _attach_news_to_players(
    players: list[dict[str, Any]], articles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach relevant news articles to each player by name matching."""
    for player in players:
        name_lower = player.get("web_name", "").lower()
        full_name = (player.get("first_name", "") + " " + player.get("second_name", "")).lower()

        matched = []
        for article in articles:
            text = (article.get("title", "") + " " + article.get("summary", "")).lower()
            if name_lower in text or full_name in text:
                matched.append(
                    {
                        "title": article.get("title", ""),
                        "summary": article.get("summary", ""),
                        "source": article.get("source", ""),
                    }
                )

        player["news_articles"] = matched

    matched_count = sum(1 for p in players if p["news_articles"])
    logger.info(
        "News attached: %d/%d players have articles",
        matched_count,
        len(players),
    )
    return players


def _load_fixtures(s3_client: S3Client, bucket: str, season: str) -> list[dict[str, Any]]:
    """Load fixture data from raw FPL API."""
    prefix = f"raw/fpl-api/season={season}/fixtures/"
    keys = s3_client.list_objects(bucket, prefix)
    if not keys:
        logger.warning("No fixture data found at %s", prefix)
        return []

    latest = sorted(keys)[-1]
    data = s3_client.read_json(bucket, latest)
    fixtures = data if isinstance(data, list) else []
    logger.info("Loaded %d fixtures", len(fixtures))
    return fixtures


def _attach_fixtures_to_players(
    players: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    gameweek: int,
    window: int = 5,
) -> list[dict[str, Any]]:
    """Attach upcoming fixtures (next N gameweeks) to each player."""
    upcoming = [
        f
        for f in fixtures
        if f.get("event") is not None and gameweek < f["event"] <= gameweek + window
    ]

    for player in players:
        team_id = player.get("team")
        player_fixtures = []
        for f in upcoming:
            if f.get("team_h") == team_id:
                player_fixtures.append(
                    {
                        "gameweek": f["event"],
                        "opponent": f["team_a"],
                        "is_home": True,
                        "difficulty": f.get("team_h_difficulty", 3),
                    }
                )
            elif f.get("team_a") == team_id:
                player_fixtures.append(
                    {
                        "gameweek": f["event"],
                        "opponent": f["team_h"],
                        "is_home": False,
                        "difficulty": f.get("team_a_difficulty", 3),
                    }
                )

        player["upcoming_fixtures"] = sorted(player_fixtures, key=lambda x: x["gameweek"])

    with_fixtures = sum(1 for p in players if p["upcoming_fixtures"])
    logger.info(
        "Fixtures attached: %d/%d players have upcoming fixtures (GW%d-%d)",
        with_fixtures,
        len(players),
        gameweek + 1,
        gameweek + window,
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
    players: list[dict[str, Any]],
    season: str,
    gameweek: int,
    bucket: str,
) -> dict[str, Any]:
    """Run one enricher on pre-loaded player data, write output."""
    s3_client = S3Client()

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
    """Run player summary enricher. Uses clean player stats only."""
    s3_client = S3Client()
    players = _load_players(s3_client, output_bucket, season, gameweek)

    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=HAIKU_RPM)
    enricher = PlayerSummaryEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher(
        "player_summary", enricher, players, season, gameweek, output_bucket
    )


@observe(name="enrich_injury_signal")
async def injury_signal_main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run injury signal enricher. Attaches news articles to each player."""
    s3_client = S3Client()
    players = _load_players(s3_client, output_bucket, season, gameweek)
    articles = _load_news_articles(s3_client, output_bucket)
    players = _attach_news_to_players(players, articles)

    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=HAIKU_RPM)
    enricher = InjurySignalEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher(
        "injury_signal", enricher, players, season, gameweek, output_bucket
    )


@observe(name="enrich_sentiment")
async def sentiment_main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run sentiment enricher. Attaches news articles to each player."""
    s3_client = S3Client()
    players = _load_players(s3_client, output_bucket, season, gameweek)
    articles = _load_news_articles(s3_client, output_bucket)
    players = _attach_news_to_players(players, articles)

    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=HAIKU_RPM)
    enricher = SentimentEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher(
        "sentiment", enricher, players, season, gameweek, output_bucket
    )


@observe(name="enrich_fixture_outlook")
async def fixture_outlook_main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Run fixture outlook enricher. Attaches upcoming fixtures to each player."""
    s3_client = S3Client()
    players = _load_players(s3_client, output_bucket, season, gameweek)
    fixtures = _load_fixtures(s3_client, output_bucket, season)
    players = _attach_fixtures_to_players(players, fixtures, gameweek)

    api_key = _get_secret("/fpl-platform/dev/anthropic-api-key")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    rate_limiter = RateLimiter(requests_per_minute=SONNET_RPM)
    enricher = FixtureOutlookEnricher(
        anthropic_client=client, prompt_version=prompt_version, rate_limiter=rate_limiter
    )
    return await _run_single_enricher(
        "fixture_outlook", enricher, players, season, gameweek, output_bucket
    )


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
