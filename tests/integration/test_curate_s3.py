"""Integration tests for the curate handler with moto S3."""

import asyncio

import pytest

from fpl_lib.clients.s3 import S3Client

TEST_SEASON = "2025-26"
TEST_GAMEWEEK = 31


@pytest.mark.integration
class TestCurateS3:
    """Test curate handler reads enriched data and writes all curated datasets."""

    def test_curate_writes_all_datasets(
        self, seed_enriched_data: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Curate reads enriched Parquet + raw inputs and writes 4 curated + public JSON."""
        # Set env vars to avoid SecretsManager calls and satisfy settings validation
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
        monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:0")
        monkeypatch.setenv("ENV", "dev")

        # Clear LRU cache so CurateSettings picks up monkeypatched env
        from fpl_curate.config import get_curate_settings

        get_curate_settings.cache_clear()

        from fpl_curate.handlers.curate_all import main

        result = asyncio.run(
            main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=seed_enriched_data,
                force=True,
            )
        )

        assert result["status"] == "success"
        assert "player_dashboard" in result["datasets_written"]
        assert "fixture_ticker" in result["datasets_written"]
        assert "transfer_picks" in result["datasets_written"]
        assert "team_strength" in result["datasets_written"]

        s3 = S3Client()
        bucket = seed_enriched_data

        # Verify all curated Parquet files
        for dataset in ["player_dashboard", "fixture_ticker", "transfer_picks", "team_strength"]:
            key = f"curated/{dataset}/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/{dataset}.parquet"
            assert s3.object_exists(bucket, key), f"Missing curated Parquet: {key}"

        # Verify public JSON files
        for dataset in ["player_dashboard", "fixture_ticker", "transfer_picks", "team_strength"]:
            key = f"public/api/v1/{dataset}.json"
            assert s3.object_exists(bucket, key), f"Missing public JSON: {key}"

        # Verify briefing JSON
        assert s3.object_exists(bucket, "public/api/v1/gameweek_briefing.json")

        # Verify player history JSON
        assert s3.object_exists(bucket, "public/api/v1/player_history.json")

        # Verify row counts are reasonable
        assert result["row_counts"]["player_dashboard"] > 0
        assert result["row_counts"]["fixture_ticker"] > 0
