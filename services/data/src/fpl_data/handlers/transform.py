"""Lambda handler for raw → clean data transformation."""

import logging
from typing import Any

import pyarrow as pa

from fpl_data.transformers.player_transformer import deduplicate, flatten_player_data
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import ValidationResult
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

REQUIRED_PARAMS = ["season", "gameweek"]
OPTIONAL_PARAMS = ["output_bucket", "force"]

DEFAULT_BUCKET = "fpl-data-lake-dev"
SCHEMA_VERSION = "1.0.0"


async def main(
    season: str,
    gameweek: int,
    output_bucket: str = DEFAULT_BUCKET,
    force: bool = False,
) -> dict[str, Any]:
    """Transform raw FPL data into clean Parquet.

    Args:
        season: Season identifier, e.g. "2025-26".
        gameweek: Gameweek number (1-38).
        output_bucket: S3 bucket for input and output.
        force: If True, overwrite existing clean data.

    Returns:
        Dict with ValidationResult fields.
    """
    s3_client = S3Client()
    output_key = f"clean/players/season={season}/gameweek={gameweek:02d}/players.parquet"

    # Idempotency check
    if not force and s3_client.object_exists(output_bucket, output_key):
        logger.info("Clean data already exists at %s, skipping", output_key)
        return ValidationResult(
            status="valid",
            records_valid=0,
            warnings=["Skipped — output already exists"],
        ).model_dump()

    # Read raw bootstrap data
    bootstrap_prefix = f"raw/fpl-api/season={season}/bootstrap/"
    bootstrap_keys = s3_client.list_objects(output_bucket, bootstrap_prefix)
    if not bootstrap_keys:
        return ValidationResult(
            status="invalid",
            errors=[f"No bootstrap data found at {bootstrap_prefix}"],
        ).model_dump()

    latest_key = sorted(bootstrap_keys)[-1]
    raw_data = s3_client.read_json(output_bucket, latest_key)

    # Transform
    df = flatten_player_data(raw_data, season)
    if df.empty:
        return ValidationResult(
            status="invalid",
            errors=["No player elements in bootstrap data"],
        ).model_dump()

    df = deduplicate(df, ["id"])

    # Write Parquet with schema version metadata
    table = pa.Table.from_pandas(df)
    table = table.replace_schema_metadata(
        {
            **(table.schema.metadata or {}),
            b"schema_version": SCHEMA_VERSION.encode(),
        }
    )
    s3_client.write_parquet(output_bucket, output_key, table)

    logger.info(
        "Transformed %d players to %s (schema v%s)",
        len(df),
        output_key,
        SCHEMA_VERSION,
    )

    return ValidationResult(
        status="valid",
        records_valid=len(df),
    ).model_dump()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for data transformation."""
    return RunHandler(
        main_func=main,
        required_main_params=REQUIRED_PARAMS,
        optional_main_params=OPTIONAL_PARAMS,
    ).lambda_executor(lambda_event=event)
