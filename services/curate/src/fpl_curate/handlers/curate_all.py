"""Lambda handler for curating all dashboard datasets from enriched data."""

import logging
from typing import Any

import pyarrow as pa

from fpl_curate.config import get_curate_settings
from fpl_curate.curators.fixture_ticker import build_fixture_ticker, build_team_map
from fpl_curate.curators.player_dashboard import build_player_dashboard
from fpl_curate.curators.team_strength import build_team_strength
from fpl_curate.curators.transfer_picks import build_transfer_picks
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import CurationResult
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

REQUIRED_PARAMS = ["season", "gameweek"]
OPTIONAL_PARAMS = ["output_bucket", "force"]

SCHEMA_VERSION = "1.0.0"


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
        f"curated/player_dashboard/season={season}/gameweek={gameweek:02d}/"
        f"player_dashboard.parquet"
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
        f"enriched/player_summaries/season={season}/gameweek={gameweek:02d}/"
        f"summaries.parquet"
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
        key = f"curated/{name}/season={season}/gameweek={gameweek:02d}/{name}.parquet"
        table = pa.Table.from_pylist(rows)
        table = table.replace_schema_metadata({
            **(table.schema.metadata or {}),
            b"schema_version": SCHEMA_VERSION.encode(),
        })
        s3_client.write_parquet(output_bucket, key, table)
        output_paths.append(f"s3://{output_bucket}/{key}")
        row_counts[name] = len(rows)
        logger.info("Wrote %d rows to %s", len(rows), key)

    return CurationResult(
        status="success",
        datasets_written=list(datasets.keys()),
        row_counts=row_counts,
        output_paths=output_paths,
    ).model_dump()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for data curation."""
    return RunHandler(
        main_func=main,
        required_main_params=REQUIRED_PARAMS,
        optional_main_params=OPTIONAL_PARAMS,
    ).lambda_executor(lambda_event=event)
