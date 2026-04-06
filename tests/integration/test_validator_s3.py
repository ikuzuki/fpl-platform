"""Integration tests for the validator handler with moto S3."""

import asyncio
import json

import boto3
import pytest

from fpl_lib.clients.s3 import S3Client

TEST_REGION = "eu-west-2"
TEST_SEASON = "2025-26"
TEST_GAMEWEEK = 31


@pytest.mark.integration
class TestValidatorS3:
    """Test validator handler reads raw JSON from S3 and validates."""

    def test_validator_valid_data(self, seed_raw_data: str) -> None:
        """Validator returns valid status for well-formed bootstrap + fixtures."""
        from fpl_data.handlers.validator import main

        result = asyncio.run(
            main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=seed_raw_data,
            )
        )

        assert result["status"] == "valid"
        assert result["records_valid"] > 0
        assert result["records_invalid"] == 0

    def test_validator_writes_dlq_on_invalid_records(self, moto_s3: str) -> None:
        """Validator writes DLQ file when bootstrap has a player with null id."""
        client = boto3.client("s3", region_name=TEST_REGION)
        season = TEST_SEASON
        ts = "2026-04-05T08-00-00"

        # Write bootstrap with one invalid player (null id)
        bootstrap = {
            "elements": [
                {
                    "id": None,  # Invalid — not_null constraint
                    "web_name": "Ghost",
                    "team": 1,
                    "element_type": 3,
                    "total_points": 0,
                    "minutes": 0,
                },
                {
                    "id": 99,
                    "web_name": "Valid",
                    "team": 1,
                    "element_type": 2,
                    "total_points": 50,
                    "minutes": 1000,
                },
            ],
        }
        client.put_object(
            Bucket=moto_s3,
            Key=f"raw/fpl-api/season={season}/bootstrap/{ts}.json",
            Body=json.dumps(bootstrap),
        )

        # Write valid fixtures so we don't get a warning there
        fixtures = [
            {
                "id": 1,
                "event": 31,
                "team_h": 1,
                "team_a": 13,
                "team_h_difficulty": 3,
                "team_a_difficulty": 3,
            },
        ]
        client.put_object(
            Bucket=moto_s3,
            Key=f"raw/fpl-api/season={season}/fixtures/{ts}.json",
            Body=json.dumps(fixtures),
        )

        from fpl_data.handlers.validator import main

        result = asyncio.run(main(season=season, gameweek=TEST_GAMEWEEK, output_bucket=moto_s3))

        assert result["status"] == "partial"
        assert result["records_invalid"] == 1

        # Verify DLQ file was written
        s3 = S3Client()
        dlq_key = f"raw/dlq/season={season}/gameweek={TEST_GAMEWEEK:02d}/players_validation_failures.jsonl"
        assert s3.object_exists(moto_s3, dlq_key)
