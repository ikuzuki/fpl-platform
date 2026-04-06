"""End-to-end pipeline test: Validation → Transform → Enrichment → Curation.

Runs the full pipeline sequentially against moto S3 with mocked external APIs.
Proves all services wire together correctly through S3 data contracts.
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
@pytest.mark.slow
class TestPipelineE2E:
    """Full pipeline integration test from raw data to curated outputs."""

    def test_full_pipeline_collection_to_curation(
        self,
        seed_raw_data: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Run Validation → Transform → Merge Enrichment → Curation end-to-end.

        Raw data is pre-seeded (simulating collector output).
        Enricher JSON results are seeded directly (simulating single_enricher Lambdas).
        Everything else runs for real against moto S3.
        """
        bucket = seed_raw_data
        s3 = S3Client()

        # --- Step 1: Validation ---
        from fpl_data.handlers.validator import main as validate_main

        val_result = asyncio.run(
            validate_main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=bucket,
            )
        )
        assert val_result["status"] == "valid", f"Validation failed: {val_result}"
        assert val_result["records_valid"] > 0

        # --- Step 2: Transformation ---
        from fpl_data.handlers.transform import main as transform_main

        tf_result = asyncio.run(
            transform_main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=bucket,
                force=True,
            )
        )
        assert tf_result["status"] == "valid", f"Transform failed: {tf_result}"
        assert tf_result["records_valid"] == 5

        # Verify clean Parquet
        clean_key = (
            f"clean/players/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/players.parquet"
        )
        clean_table = s3.read_parquet(bucket, clean_key)
        assert clean_table.num_rows == 5
        clean_cols = set(clean_table.column_names)
        assert "understat_xg" in clean_cols
        assert "season" in clean_cols
        assert "id" in clean_cols

        # --- Step 3: Seed enricher results (simulating single_enricher Lambdas) ---
        _seed_enricher_results(bucket)

        # --- Step 4: Merge Enrichments ---
        from fpl_enrich.handlers.merge_enrichments import main as merge_main

        merge_result = asyncio.run(
            merge_main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=bucket,
            )
        )
        assert merge_result["status"] == "success", f"Merge failed: {merge_result}"
        assert merge_result["records_enriched"] >= 2

        # Verify enriched Parquet
        enriched_key = f"enriched/player_summaries/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/summaries.parquet"
        enriched_table = s3.read_parquet(bucket, enriched_key)
        assert enriched_table.num_rows == 5
        enriched_cols = set(enriched_table.column_names)
        assert "player_summary_summary" in enriched_cols
        assert "injury_signal_risk_score" in enriched_cols
        assert "sentiment_sentiment" in enriched_cols
        assert "fixture_outlook_recommendation" in enriched_cols

        # --- Step 5: Curation ---
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
        monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:0")
        monkeypatch.setenv("ENV", "dev")

        from fpl_curate.config import get_curate_settings

        get_curate_settings.cache_clear()

        from fpl_curate.handlers.curate_all import main as curate_main

        curate_result = asyncio.run(
            curate_main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=bucket,
                force=True,
            )
        )
        assert curate_result["status"] == "success", f"Curation failed: {curate_result}"
        assert "player_dashboard" in curate_result["datasets_written"]

        # --- Step 6: Final assertions — verify complete S3 inventory ---
        all_keys = s3.list_objects(bucket, "")

        # Group keys by layer
        layers = {"raw/": [], "clean/": [], "enriched/": [], "curated/": [], "public/": []}
        for key in all_keys:
            for prefix in layers:
                if key.startswith(prefix):
                    layers[prefix].append(key)
                    break

        # Every layer should have data
        for layer, keys in layers.items():
            assert len(keys) > 0, f"No objects in {layer} layer"

        # Specific checks
        assert any("bootstrap" in k for k in layers["raw/"]), "Missing raw bootstrap"
        assert any("fixtures" in k for k in layers["raw/"]), "Missing raw fixtures"
        assert any("understat" in k for k in layers["raw/"]), "Missing raw understat"
        assert any("players.parquet" in k for k in layers["clean/"]), "Missing clean Parquet"
        assert any("summaries.parquet" in k for k in layers["enriched/"]), (
            "Missing enriched Parquet"
        )

        curated_datasets = {"player_dashboard", "fixture_ticker", "transfer_picks", "team_strength"}
        for dataset in curated_datasets:
            assert any(dataset in k for k in layers["curated/"]), f"Missing curated {dataset}"
            assert any(dataset in k for k in layers["public/"]), f"Missing public {dataset}"

        # Verify dashboard JSON is readable and non-empty
        dashboard_json = s3.read_json(bucket, "public/api/v1/player_dashboard.json")
        assert len(dashboard_json) > 0, "Player dashboard JSON is empty"

        # Verify player history was written
        history = s3.read_json(bucket, "public/api/v1/player_history.json")
        assert len(history) > 0, "Player history is empty"


def _seed_enricher_results(bucket: str) -> None:
    """Write per-enricher JSON results to S3 (simulating single_enricher Lambdas)."""
    client = boto3.client("s3", region_name=TEST_REGION)

    # Enrichment data for players 1 (Haaland) and 2 (Saka)
    enrichers = {
        "player_summary": [
            {
                "player_id": 1,
                "enrichment": {
                    "summary": "Haaland: 22 goals, consistent returns.",
                    "form_trend": "stable",
                    "confidence": 0.95,
                },
            },
            {
                "player_id": 2,
                "enrichment": {
                    "summary": "Saka: creative force with 12 assists.",
                    "form_trend": "improving",
                    "confidence": 0.90,
                },
            },
            {
                "player_id": 3,
                "enrichment": {
                    "summary": "Fernandes: leading assists with creative play.",
                    "form_trend": "improving",
                    "confidence": 0.88,
                },
            },
            {
                "player_id": 4,
                "enrichment": {
                    "summary": "Chalobah: struggling for minutes this term.",
                    "form_trend": "declining",
                    "confidence": 0.70,
                },
            },
        ],
        "injury_signal": [
            {
                "player_id": 1,
                "enrichment": {
                    "risk_score": 0,
                    "reasoning": "Fully fit.",
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
                    "sources": ["BBC"],
                },
            },
            {
                "player_id": 3,
                "enrichment": {
                    "risk_score": 0,
                    "reasoning": "No concerns.",
                    "injury_type": None,
                    "sources": [],
                },
            },
            {
                "player_id": 4,
                "enrichment": {
                    "risk_score": 5,
                    "reasoning": "Limited minutes.",
                    "injury_type": None,
                    "sources": [],
                },
            },
        ],
        "sentiment": [
            {
                "player_id": 1,
                "enrichment": {"sentiment": "positive", "score": 0.85, "key_themes": ["clinical"]},
            },
            {
                "player_id": 2,
                "enrichment": {"sentiment": "positive", "score": 0.6, "key_themes": ["creative"]},
            },
            {
                "player_id": 3,
                "enrichment": {"sentiment": "neutral", "score": 0.0, "key_themes": []},
            },
            {
                "player_id": 4,
                "enrichment": {"sentiment": "negative", "score": -0.4, "key_themes": ["benched"]},
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
                    "best_gameweeks": [35],
                },
            },
            {
                "player_id": 3,
                "enrichment": {
                    "difficulty_score": 3,
                    "recommendation": "Favorable home.",
                    "best_gameweeks": [32],
                },
            },
            {
                "player_id": 4,
                "enrichment": {
                    "difficulty_score": 3,
                    "recommendation": "Mixed.",
                    "best_gameweeks": [32],
                },
            },
        ],
    }

    for enricher_name, records in enrichers.items():
        key = f"enriched/{enricher_name}/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/results.json"
        client.put_object(Bucket=bucket, Key=key, Body=json.dumps(records))
