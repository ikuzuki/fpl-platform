"""Backfill FPL pipeline for a range of gameweeks via Step Functions.

Triggers a Step Functions execution for each gameweek, waits for completion,
and reports results. Uses the same pipeline as the weekly scheduled run.

Usage:
    python scripts/backfill.py --season 2025-26 --start-gw 1 --end-gw 20
    python scripts/backfill.py --season 2025-26 --start-gw 32 --end-gw 32
"""

import argparse
import json
import logging
import sys
import time

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_STATE_MACHINE = "fpl-dev-collection-pipeline"
DEFAULT_REGION = "eu-west-2"
POLL_INTERVAL_SECONDS = 10


def _get_state_machine_arn(name: str, region: str) -> str:
    """Resolve state machine name to ARN."""
    client = boto3.client("stepfunctions", region_name=region)
    paginator = client.get_paginator("list_state_machines")
    for page in paginator.paginate():
        for sm in page["stateMachines"]:
            if sm["name"] == name:
                return sm["stateMachineArn"]
    raise ValueError(f"State machine '{name}' not found in {region}")


def _start_execution(
    sfn_client: boto3.client,
    state_machine_arn: str,
    season: str,
    gameweek: int,
) -> str:
    """Start a Step Functions execution and return the execution ARN."""
    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=f"backfill-{season}-gw{gameweek:02d}-{int(time.time())}",
        input=json.dumps(
            {
                "season": season,
                "gameweek": gameweek,
                "force": True,
            }
        ),
    )
    return response["executionArn"]


def _wait_for_execution(sfn_client: boto3.client, execution_arn: str) -> dict[str, str]:
    """Poll until the execution completes. Returns status and details."""
    while True:
        response = sfn_client.describe_execution(executionArn=execution_arn)
        status = response["status"]

        if status == "RUNNING":
            logger.info("  ... still running")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        result: dict[str, str] = {"status": status}
        if status == "SUCCEEDED":
            result["output"] = response.get("output", "")
        elif status == "FAILED":
            result["error"] = response.get("error", "unknown")
            result["cause"] = response.get("cause", "")
        return result


def main() -> None:
    """Parse args and run backfill via Step Functions."""
    parser = argparse.ArgumentParser(
        description="Backfill FPL pipeline via Step Functions for a range of gameweeks"
    )
    parser.add_argument("--season", required=True, help="Season string, e.g. 2025-26")
    parser.add_argument("--start-gw", type=int, required=True, help="First gameweek to backfill")
    parser.add_argument("--end-gw", type=int, required=True, help="Last gameweek to backfill")
    parser.add_argument(
        "--state-machine",
        default=DEFAULT_STATE_MACHINE,
        help=f"Step Functions state machine name (default: {DEFAULT_STATE_MACHINE})",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region (default: {DEFAULT_REGION})",
    )
    args = parser.parse_args()

    if args.start_gw < 1 or args.end_gw > 38 or args.start_gw > args.end_gw:
        logger.error("Invalid gameweek range: %d-%d", args.start_gw, args.end_gw)
        sys.exit(1)

    # Resolve state machine ARN
    state_machine_arn = _get_state_machine_arn(args.state_machine, args.region)
    logger.info("Using state machine: %s", state_machine_arn)

    sfn_client = boto3.client("stepfunctions", region_name=args.region)

    logger.info(
        "Backfilling %s from GW%d to GW%d",
        args.season,
        args.start_gw,
        args.end_gw,
    )

    all_results: dict[int, dict[str, str]] = {}

    for gw in range(args.start_gw, args.end_gw + 1):
        logger.info("--- Gameweek %d ---", gw)

        execution_arn = _start_execution(sfn_client, state_machine_arn, args.season, gw)
        logger.info("  Started execution: %s", execution_arn.split(":")[-1])

        result = _wait_for_execution(sfn_client, execution_arn)
        all_results[gw] = result

        if result["status"] == "SUCCEEDED":
            logger.info("  GW%d succeeded", gw)
        else:
            logger.error("  GW%d failed: %s", gw, result.get("cause", result.get("error", "")))

        if gw < args.end_gw:
            logger.info("  Sleeping 2s before next gameweek...")
            time.sleep(2)

    # Summary
    logger.info("=== Backfill Summary ===")
    succeeded = sum(1 for r in all_results.values() if r["status"] == "SUCCEEDED")
    failed = sum(1 for r in all_results.values() if r["status"] != "SUCCEEDED")

    for gw, result in all_results.items():
        logger.info("  GW%02d: %s", gw, result["status"])

    logger.info("Total: %d succeeded, %d failed", succeeded, failed)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
