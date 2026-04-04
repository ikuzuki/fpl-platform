"""Backfill FPL pipeline for a range of gameweeks.

Usage:
    python -m fpl_data.scripts.backfill --season 2025-26 --start-gw 1 --end-gw 20
    python -m fpl_data.scripts.backfill --season 2025-26 --start-gw 5 --end-gw 5  # single GW
"""

import argparse
import asyncio
import logging
import sys
import time

from fpl_data.handlers.fpl_api_handler import main as collect_fpl
from fpl_data.handlers.transform import main as transform
from fpl_data.handlers.validator import main as validate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def backfill_gameweek(season: str, gameweek: int) -> dict[str, str]:
    """Run the full pipeline for a single gameweek with force=True."""
    results: dict[str, str] = {}

    # Step 1: Collect
    try:
        result = await collect_fpl(season=season, gameweek=gameweek, force=True)
        results["collect"] = result.get("status", "unknown")
    except Exception as e:
        logger.error("Collection failed for GW%d: %s", gameweek, e)
        results["collect"] = f"failed: {e}"
        return results

    # Step 2: Validate
    try:
        result = await validate(season=season, gameweek=gameweek)
        results["validate"] = result.get("status", "unknown")
    except Exception as e:
        logger.error("Validation failed for GW%d: %s", gameweek, e)
        results["validate"] = f"failed: {e}"
        return results

    # Step 3: Transform
    try:
        result = await transform(season=season, gameweek=gameweek, force=True)
        results["transform"] = result.get("status", "unknown")
    except Exception as e:
        logger.error("Transform failed for GW%d: %s", gameweek, e)
        results["transform"] = f"failed: {e}"

    return results


def main() -> None:
    """Parse args and run backfill across gameweek range."""
    parser = argparse.ArgumentParser(description="Backfill FPL pipeline for a range of gameweeks")
    parser.add_argument("--season", required=True, help="Season string, e.g. 2025-26")
    parser.add_argument("--start-gw", type=int, required=True, help="First gameweek to backfill")
    parser.add_argument("--end-gw", type=int, required=True, help="Last gameweek to backfill")
    args = parser.parse_args()

    if args.start_gw < 1 or args.end_gw > 38 or args.start_gw > args.end_gw:
        logger.error("Invalid gameweek range: %d-%d", args.start_gw, args.end_gw)
        sys.exit(1)

    logger.info(
        "Backfilling %s from GW%d to GW%d",
        args.season,
        args.start_gw,
        args.end_gw,
    )

    all_results: dict[int, dict[str, str]] = {}

    for gw in range(args.start_gw, args.end_gw + 1):
        logger.info("--- Gameweek %d ---", gw)
        results = asyncio.run(backfill_gameweek(args.season, gw))
        all_results[gw] = results

        if gw < args.end_gw:
            logger.info("Sleeping 2s before next gameweek...")
            time.sleep(2)

    # Summary
    logger.info("=== Backfill Summary ===")
    succeeded = 0
    failed = 0
    for gw, results in all_results.items():
        status = "OK" if all("failed" not in v for v in results.values()) else "FAILED"
        if status == "OK":
            succeeded += 1
        else:
            failed += 1
        logger.info("  GW%02d: %s — %s", gw, status, results)

    logger.info("Total: %d succeeded, %d failed", succeeded, failed)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
