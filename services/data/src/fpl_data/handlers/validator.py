"""Lambda handler for raw data validation."""

import json
import logging
from typing import Any

from fpl_data.validators.engine import validate_records
from fpl_data.validators.schemas import FIXTURE_EXPECTATIONS, PLAYER_EXPECTATIONS
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import ValidationResult
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

REQUIRED_PARAMS = ["season", "gameweek"]
OPTIONAL_PARAMS = ["output_bucket"]

DEFAULT_BUCKET = "fpl-data-lake-dev"


async def main(
    season: str,
    gameweek: int,
    output_bucket: str = DEFAULT_BUCKET,
) -> dict[str, Any]:
    """Validate raw FPL data for a given season and gameweek.

    Args:
        season: Season identifier, e.g. "2025-26".
        gameweek: Gameweek number (1-38).
        output_bucket: S3 bucket containing raw data.

    Returns:
        Dict with ValidationResult fields.
    """
    s3_client = S3Client()
    all_errors: list[str] = []
    all_warnings: list[str] = []
    total_valid = 0
    total_invalid = 0

    # Validate player data (bootstrap)
    bootstrap_prefix = f"raw/fpl-api/season={season}/bootstrap/"
    bootstrap_keys = s3_client.list_objects(output_bucket, bootstrap_prefix)
    if bootstrap_keys:
        latest_key = sorted(bootstrap_keys)[-1]
        raw_data = s3_client.read_json(output_bucket, latest_key)
        players = raw_data.get("elements", []) if isinstance(raw_data, dict) else []

        valid, failed = validate_records(players, PLAYER_EXPECTATIONS, "players")
        total_valid += len(valid)
        total_invalid += len(failed)

        if failed:
            _write_dlq(s3_client, output_bucket, season, gameweek, "players", failed)
            all_errors.extend(
                f"Player {f['record'].get('id', '?')}: {', '.join(f['errors'])}" for f in failed
            )
    else:
        all_errors.append(f"No bootstrap data found at {bootstrap_prefix}")

    # Validate fixture data
    fixtures_prefix = f"raw/fpl-api/season={season}/fixtures/"
    fixtures_keys = s3_client.list_objects(output_bucket, fixtures_prefix)
    if fixtures_keys:
        latest_key = sorted(fixtures_keys)[-1]
        raw_data = s3_client.read_json(output_bucket, latest_key)
        fixtures = raw_data if isinstance(raw_data, list) else []

        valid, failed = validate_records(fixtures, FIXTURE_EXPECTATIONS, "fixtures")
        total_valid += len(valid)
        total_invalid += len(failed)

        if failed:
            _write_dlq(s3_client, output_bucket, season, gameweek, "fixtures", failed)
            all_errors.extend(
                f"Fixture {f['record'].get('id', '?')}: {', '.join(f['errors'])}" for f in failed
            )
    else:
        all_warnings.append(f"No fixture data found at {fixtures_prefix}")

    status = "valid" if not all_errors else ("partial" if total_valid > 0 else "invalid")

    result = ValidationResult(
        status=status,
        errors=all_errors,
        warnings=all_warnings,
        records_valid=total_valid,
        records_invalid=total_invalid,
    )
    return result.model_dump()


def _write_dlq(
    s3_client: S3Client,
    bucket: str,
    season: str,
    gameweek: int,
    dataset: str,
    failed_records: list[dict],
) -> None:
    """Write failed records to the DLQ prefix."""
    key = f"raw/dlq/season={season}/gameweek={gameweek:02d}/{dataset}_validation_failures.jsonl"
    jsonl = "\n".join(json.dumps(f, default=str) for f in failed_records)
    s3_client.put_json(bucket, key, jsonl)
    logger.info("Wrote %d failed %s records to DLQ: %s", len(failed_records), dataset, key)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for data validation."""
    return RunHandler(
        main_func=main,
        required_main_params=REQUIRED_PARAMS,
        optional_main_params=OPTIONAL_PARAMS,
    ).lambda_executor(lambda_event=event)
