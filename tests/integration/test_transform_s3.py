"""Integration tests for the transform handler with moto S3."""

import asyncio

import pytest

from fpl_lib.clients.s3 import S3Client

TEST_SEASON = "2025-26"
TEST_GAMEWEEK = 31


@pytest.mark.integration
class TestTransformS3:
    """Test transform handler reads raw JSON and writes clean Parquet via S3."""

    def test_transform_reads_raw_writes_clean(self, seed_raw_data: str) -> None:
        """Transform reads bootstrap + understat from raw/ and writes clean Parquet."""
        from fpl_data.handlers.transform import main

        result = asyncio.run(
            main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=seed_raw_data,
                force=True,
            )
        )

        assert result["status"] == "valid"
        assert result["records_valid"] == 5

        # Verify Parquet was written and is readable
        s3 = S3Client()
        key = f"clean/players/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/players.parquet"
        assert s3.object_exists(seed_raw_data, key)

        table = s3.read_parquet(seed_raw_data, key)
        assert table.num_rows == 5

        # Verify key columns exist
        col_names = set(table.column_names)
        assert "id" in col_names
        assert "web_name" in col_names
        assert "understat_xg" in col_names
        assert "season" in col_names

    def test_transform_idempotency(self, seed_raw_data: str) -> None:
        """Second run without force=True returns skip status."""
        from fpl_data.handlers.transform import main

        # First run
        asyncio.run(
            main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=seed_raw_data,
                force=True,
            )
        )

        # Second run without force — should skip
        result = asyncio.run(
            main(
                season=TEST_SEASON,
                gameweek=TEST_GAMEWEEK,
                output_bucket=seed_raw_data,
                force=False,
            )
        )

        assert result["status"] == "valid"
        assert result["records_valid"] == 0
        assert "Skipped" in result["warnings"][0]
