"""Integration tests for the enricher handler with moto S3.

Tests the merge_enrichments handler (production Step Functions path) which
reads per-enricher JSON results and merges them into final enriched Parquet.
"""

import asyncio
import json

import boto3
import pytest

from fpl_lib.clients.s3 import S3Client

TEST_REGION = "eu-west-2"
TEST_SEASON = "2025-26"
TEST_GAMEWEEK = 31


@pytest.mark.integration
class TestMergeEnrichmentS3:
    """Test merge_enrichments handler reads enricher outputs and writes merged Parquet."""

    def test_merge_reads_enricher_jsons_writes_merged_parquet(self, seed_clean_data: str) -> None:
        """Merge handler reads per-enricher JSON, writes combined enriched Parquet."""
        client = boto3.client("s3", region_name=TEST_REGION)
        bucket = seed_clean_data

        # Seed per-enricher JSON results (simulating single_enricher Lambda outputs)
        enricher_results = {
            "player_summary": [
                {
                    "player_id": 1,
                    "enrichment": {
                        "summary": "Haaland has delivered 22 goals this season.",
                        "form_trend": "stable",
                        "confidence": 0.95,
                    },
                },
                {
                    "player_id": 2,
                    "enrichment": {
                        "summary": "Saka is a consistent performer on the wing.",
                        "form_trend": "improving",
                        "confidence": 0.90,
                    },
                },
            ],
            "injury_signal": [
                {
                    "player_id": 1,
                    "enrichment": {
                        "risk_score": 0,
                        "reasoning": "No injury concerns.",
                        "injury_type": None,
                        "sources": [],
                    },
                },
                {
                    "player_id": 2,
                    "enrichment": {
                        "risk_score": 2,
                        "reasoning": "Minor knock.",
                        "injury_type": "knock",
                        "sources": ["BBC Sport"],
                    },
                },
            ],
            "sentiment": [
                {
                    "player_id": 1,
                    "enrichment": {
                        "sentiment": "positive",
                        "score": 0.85,
                        "key_themes": ["clinical"],
                    },
                },
                {
                    "player_id": 2,
                    "enrichment": {
                        "sentiment": "positive",
                        "score": 0.6,
                        "key_themes": ["creative"],
                    },
                },
            ],
            "fixture_outlook": [
                {
                    "player_id": 1,
                    "enrichment": {
                        "difficulty_score": 3,
                        "recommendation": "Hold.",
                        "best_gameweeks": [33, 35],
                    },
                },
                {
                    "player_id": 2,
                    "enrichment": {
                        "difficulty_score": 4,
                        "recommendation": "Tough run.",
                        "best_gameweeks": [35, 36],
                    },
                },
            ],
        }

        for enricher_name, records in enricher_results.items():
            key = f"enriched/{enricher_name}/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/results.json"
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(records),
            )

        from fpl_enrich.handlers.merge_enrichments import main

        result = asyncio.run(
            main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=bucket,
            )
        )

        assert result["status"] == "success"
        assert result["records_enriched"] == 2  # Haaland + Saka had enrichments

        # Verify merged Parquet exists and has enrichment columns
        s3 = S3Client()
        enriched_key = f"enriched/player_summaries/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/summaries.parquet"
        assert s3.object_exists(bucket, enriched_key)

        table = s3.read_parquet(bucket, enriched_key)
        # All 5 players should be in output (enriched + unenriched)
        assert table.num_rows == 5

        col_names = set(table.column_names)
        # Verify enrichment columns with correct prefixes
        assert "player_summary_summary" in col_names
        assert "injury_signal_risk_score" in col_names
        assert "sentiment_sentiment" in col_names
        assert "fixture_outlook_recommendation" in col_names
