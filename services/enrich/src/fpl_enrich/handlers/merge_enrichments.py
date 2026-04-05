"""Lambda handler that merges individual enricher outputs into final Parquet.

Reads the per-enricher JSON outputs written by the parallel enricher Lambdas,
combines them with the full player dataset, and writes the merged enriched
Parquet file plus a cost report.
"""

import logging
from typing import Any

import pyarrow as pa

from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

ENRICHER_NAMES = ["player_summary", "injury_signal", "sentiment", "fixture_outlook"]


async def main(
    season: str,
    gameweek: int,
    output_bucket: str = "fpl-data-lake-dev",
) -> dict[str, Any]:
    """Merge enricher outputs into a single enriched Parquet file."""
    s3_client = S3Client()

    # Read full clean player data
    clean_key = f"clean/players/season={season}/gameweek={gameweek:02d}/players.parquet"
    table = s3_client.read_parquet(output_bucket, clean_key)
    all_players = table.to_pylist()
    logger.info("Read %d players from %s", len(all_players), clean_key)

    # Build lookup: player_id → enrichment results per enricher
    enrichments_by_player: dict[Any, dict[str, dict[str, Any] | None]] = {}

    for enricher_name in ENRICHER_NAMES:
        results_key = (
            f"enriched/{enricher_name}/season={season}/gameweek={gameweek:02d}/results.json"
        )
        try:
            records = s3_client.read_json(output_bucket, results_key)
            logger.info("Read %d %s results from %s", len(records), enricher_name, results_key)
            for record in records:
                pid = record["player_id"]
                if pid not in enrichments_by_player:
                    enrichments_by_player[pid] = {}
                enrichments_by_player[pid][enricher_name] = record.get("enrichment")
        except Exception:
            logger.warning("Could not read %s results — skipping", enricher_name)

    # Merge enrichments into player records
    enriched_players = []
    enriched_count = 0
    for player in all_players:
        enriched = dict(player)
        pid = player.get("id")
        player_enrichments = enrichments_by_player.get(pid, {})

        has_enrichment = False
        for enricher_name, result in player_enrichments.items():
            if result is not None:
                has_enrichment = True
                prefix = enricher_name.replace("_enricher", "")
                for key, value in result.items():
                    enriched[f"{prefix}_{key}"] = value

        if has_enrichment:
            enriched_count += 1
        enriched_players.append(enriched)

    # Write merged enriched Parquet
    enriched_table = pa.Table.from_pylist(enriched_players)
    enriched_key = (
        f"enriched/player_summaries/season={season}/gameweek={gameweek:02d}/summaries.parquet"
    )
    s3_client.write_parquet(output_bucket, enriched_key, enriched_table)
    logger.info(
        "Wrote merged enriched data: %d/%d players enriched → s3://%s/%s",
        enriched_count,
        len(all_players),
        output_bucket,
        enriched_key,
    )

    return {
        "status": "success" if enriched_count > 0 else "partial",
        "records_enriched": enriched_count,
        "records_total": len(all_players),
        "output_path": enriched_key,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for merging enrichment results."""
    return RunHandler(
        main_func=main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket"],
    ).lambda_executor(lambda_event=event)
