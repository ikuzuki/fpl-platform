"""Lambda handler for curating all dashboard datasets from enriched data."""

import logging
from typing import Any

import pyarrow as pa
from langfuse import observe, propagate_attributes

from fpl_curate.config import get_curate_settings
from fpl_curate.curators.fixture_ticker import build_fixture_ticker, build_team_map
from fpl_curate.curators.gameweek_briefing import build_gameweek_briefing
from fpl_curate.curators.player_dashboard import build_player_dashboard
from fpl_curate.curators.player_history import build_player_history
from fpl_curate.curators.team_strength import build_team_strength
from fpl_curate.curators.transfer_picks import build_transfer_picks
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import CurationResult
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

REQUIRED_PARAMS = ["season", "gameweek"]
OPTIONAL_PARAMS = ["output_bucket", "force"]

SCHEMA_VERSION = "1.0.0"


def _init_langfuse(region: str = "eu-west-2") -> None:
    """Initialise Langfuse with keys from Secrets Manager."""
    import os

    import boto3

    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        client = boto3.client("secretsmanager", region_name=region)
        resp = client.get_secret_value(SecretId="/fpl-platform/dev/langfuse-public-key")
        os.environ["LANGFUSE_PUBLIC_KEY"] = resp["SecretString"]
    if not os.environ.get("LANGFUSE_SECRET_KEY"):
        client = boto3.client("secretsmanager", region_name=region)
        resp = client.get_secret_value(SecretId="/fpl-platform/dev/langfuse-secret-key")
        os.environ["LANGFUSE_SECRET_KEY"] = resp["SecretString"]


@observe(name="curate_gameweek")
async def main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
    force: bool = False,
) -> dict[str, Any]:
    """Curate all dashboard datasets from enriched data.

    Args:
        season: Season identifier, e.g. "2025-26".
        gameweek: Gameweek number (1-38).
        output_bucket: S3 bucket for input and output.
        force: If True, overwrite existing curated data.

    Returns:
        Dict with CurationResult fields.
    """
    settings = get_curate_settings()
    s3_client = S3Client()

    # Idempotency check — use player_dashboard as the sentinel
    sentinel_key = (
        f"curated/player_dashboard/season={season}/gameweek={gameweek:02d}/player_dashboard.parquet"
    )
    if not force and s3_client.object_exists(output_bucket, sentinel_key):
        logger.info("Curated data already exists at %s, skipping", sentinel_key)
        return CurationResult(
            status="success",
            datasets_written=[],
        ).model_dump()

    # --- Read inputs ---

    # 1. Enriched player summaries
    enriched_key = (
        f"enriched/player_summaries/season={season}/gameweek={gameweek:02d}/summaries.parquet"
    )
    enriched_table = s3_client.read_parquet(output_bucket, enriched_key)
    enriched_df = enriched_table.to_pandas()
    logger.info("Read %d enriched players from %s", len(enriched_df), enriched_key)

    # 2. Raw fixtures
    fixtures_prefix = f"raw/fpl-api/season={season}/fixtures/"
    fixtures_keys = s3_client.list_objects(output_bucket, fixtures_prefix)
    if not fixtures_keys:
        return CurationResult(
            status="failed",
            datasets_written=[],
        ).model_dump()
    fixtures_raw = s3_client.read_json(output_bucket, sorted(fixtures_keys)[-1])

    # 3. Bootstrap (team mappings)
    bootstrap_prefix = f"raw/fpl-api/season={season}/bootstrap/"
    bootstrap_keys = s3_client.list_objects(output_bucket, bootstrap_prefix)
    if not bootstrap_keys:
        return CurationResult(
            status="failed",
            datasets_written=[],
        ).model_dump()
    bootstrap_data = s3_client.read_json(output_bucket, sorted(bootstrap_keys)[-1])

    team_map = build_team_map(bootstrap_data)

    # --- Build curated datasets ---

    # 1. Fixture ticker (needed first — provides FDR lookup for scoring)
    fixture_rows, fixture_fdr = build_fixture_ticker(
        fixtures_raw=fixtures_raw,
        team_map=team_map,
        current_gw=gameweek,
        season=season,
    )

    # 2. Player dashboard (uses fixture FDR for scoring)
    dashboard_rows = build_player_dashboard(
        enriched_df=enriched_df,
        team_map=team_map,
        fixture_fdr=fixture_fdr,
        weights=settings.FPL_SCORE_WEIGHTS,
        season=season,
        gameweek=gameweek,
    )

    # 3. Transfer picks (derived from dashboard)
    transfer_rows = build_transfer_picks(
        dashboard_rows=dashboard_rows,
        season=season,
        gameweek=gameweek,
    )

    # 4. Team strength (derived from dashboard + fixtures)
    team_rows = build_team_strength(
        dashboard_rows=dashboard_rows,
        fixture_fdr=fixture_fdr,
        team_map=team_map,
        season=season,
        gameweek=gameweek,
    )

    # 5. Gameweek briefing (aggregates signals from all curated data)
    briefing = build_gameweek_briefing(
        dashboard_rows=dashboard_rows,
        transfer_rows=transfer_rows,
        fixture_fdr=fixture_fdr,
        team_map=team_map,
        season=season,
        gameweek=gameweek,
    )

    # --- Write outputs ---
    datasets = {
        "player_dashboard": dashboard_rows,
        "fixture_ticker": fixture_rows,
        "transfer_picks": transfer_rows,
        "team_strength": team_rows,
    }

    output_paths: list[str] = []
    row_counts: dict[str, int] = {}

    for name, rows in datasets.items():
        # Write Parquet (analytics)
        parquet_key = f"curated/{name}/season={season}/gameweek={gameweek:02d}/{name}.parquet"
        table = pa.Table.from_pylist(rows)
        table = table.replace_schema_metadata(
            {
                **(table.schema.metadata or {}),
                b"schema_version": SCHEMA_VERSION.encode(),
            }
        )
        s3_client.write_parquet(output_bucket, parquet_key, table)
        output_paths.append(f"s3://{output_bucket}/{parquet_key}")
        row_counts[name] = len(rows)
        logger.info("Wrote %d rows to %s", len(rows), parquet_key)

    # --- Update player history (upsert by gameweek) ---
    history_key = "public/api/v1/player_history.json"
    try:
        existing_history: list[dict[str, Any]] = s3_client.read_json(output_bucket, history_key)
    except Exception:
        existing_history = []
        logger.info("No existing player history found, starting fresh")

    # Only overwrite latest JSON files if this is the most recent gameweek
    max_existing_gw = max((r.get("gameweek", 0) for r in existing_history), default=0)
    is_latest = gameweek >= max_existing_gw

    if is_latest:
        for name, rows in datasets.items():
            json_key = f"public/api/v1/{name}.json"
            s3_client.put_json(output_bucket, json_key, rows)
            logger.info("Wrote %d rows to %s", len(rows), json_key)

        # Write briefing JSON
        briefing_key = "public/api/v1/gameweek_briefing.json"
        s3_client.put_json(output_bucket, briefing_key, briefing)
        output_paths.append(f"s3://{output_bucket}/{briefing_key}")
        row_counts["gameweek_briefing"] = 1
        logger.info("Wrote briefing to %s", briefing_key)
    else:
        logger.info(
            "Skipping latest JSON writes — GW%d is older than current latest GW%d",
            gameweek,
            max_existing_gw,
        )

    history_rows = build_player_history(
        dashboard_rows=dashboard_rows,
        existing_history=existing_history,
        season=season,
        gameweek=gameweek,
    )
    s3_client.put_json(output_bucket, history_key, history_rows)
    row_counts["player_history"] = len(history_rows)
    output_paths.append(f"s3://{output_bucket}/{history_key}")

    return CurationResult(
        status="success",
        datasets_written=list(datasets.keys()),
        row_counts=row_counts,
        output_paths=output_paths,
    ).model_dump()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for data curation."""
    _init_langfuse()
    season = event.get("season", "unknown")
    gameweek = event.get("gameweek", 0)
    with propagate_attributes(
        session_id=f"{season}-gw{gameweek}",
        metadata={"pipeline": "curate"},
    ):
        return RunHandler(
            main_func=main,
            required_main_params=REQUIRED_PARAMS,
            optional_main_params=OPTIONAL_PARAMS,
        ).lambda_executor(lambda_event=event)
