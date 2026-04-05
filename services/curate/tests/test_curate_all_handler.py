"""Unit tests for the curate_all handler."""

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pyarrow as pa
import pytest

from fpl_curate.config import CurateSettings
from fpl_curate.handlers.curate_all import main


@pytest.fixture()
def mock_s3_client() -> MagicMock:
    """Mock S3Client with pre-loaded test data."""
    client = MagicMock()
    client.object_exists.return_value = False
    return client


@pytest.fixture()
def mock_settings() -> CurateSettings:
    """CurateSettings with defaults (no .env needed)."""
    return CurateSettings(
        ENV="dev",
        AWS_REGION="eu-west-2",
        DATA_LAKE_BUCKET="fpl-data-lake-dev",
    )


@pytest.fixture()
def sample_bootstrap() -> dict[str, Any]:
    return {
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS"},
            {"id": 13, "name": "Man City", "short_name": "MCI"},
            {"id": 14, "name": "Man Utd", "short_name": "MUN"},
        ]
    }


@pytest.fixture()
def sample_fixtures() -> list[dict[str, Any]]:
    return [
        {"event": 32, "team_h": 1, "team_a": 14, "team_h_difficulty": 2, "team_a_difficulty": 4,
         "kickoff_time": "2026-04-12T15:00:00Z"},
        {"event": 33, "team_h": 13, "team_a": 1, "team_h_difficulty": 4, "team_a_difficulty": 5,
         "kickoff_time": "2026-04-19T17:30:00Z"},
    ]


@pytest.mark.unit
class TestCurateAllHandler:
    @pytest.mark.asyncio
    async def test_skips_when_exists(
        self, mock_s3_client: MagicMock, mock_settings: CurateSettings,
    ) -> None:
        mock_s3_client.object_exists.return_value = True

        with (
            patch("fpl_curate.handlers.curate_all.S3Client", return_value=mock_s3_client),
            patch("fpl_curate.handlers.curate_all.get_curate_settings", return_value=mock_settings),
        ):
            result = await main(season="2025-26", gameweek=31)

        assert result["status"] == "success"
        assert result["datasets_written"] == []
        mock_s3_client.write_parquet.assert_not_called()

    @pytest.mark.asyncio
    async def test_writes_four_datasets(
        self,
        mock_s3_client: MagicMock,
        mock_settings: CurateSettings,
        sample_enriched_df: pd.DataFrame,
        sample_bootstrap: dict[str, Any],
        sample_fixtures: list[dict[str, Any]],
    ) -> None:
        table = pa.Table.from_pandas(sample_enriched_df)
        mock_s3_client.read_parquet.return_value = table
        mock_s3_client.list_objects.side_effect = [
            ["raw/fpl-api/season=2025-26/fixtures/2026-04-05.json"],
            ["raw/fpl-api/season=2025-26/bootstrap/2026-04-05.json"],
        ]
        mock_s3_client.read_json.side_effect = [sample_fixtures, sample_bootstrap]

        with (
            patch("fpl_curate.handlers.curate_all.S3Client", return_value=mock_s3_client),
            patch("fpl_curate.handlers.curate_all.get_curate_settings", return_value=mock_settings),
        ):
            result = await main(season="2025-26", gameweek=31, force=True)

        assert result["status"] == "success"
        assert set(result["datasets_written"]) == {
            "player_dashboard", "fixture_ticker", "transfer_picks", "team_strength",
        }
        assert mock_s3_client.write_parquet.call_count == 4

    @pytest.mark.asyncio
    async def test_fails_when_no_fixtures(
        self, mock_s3_client: MagicMock, mock_settings: CurateSettings,
    ) -> None:
        mock_s3_client.read_parquet.return_value = pa.table({"id": [1]})
        mock_s3_client.list_objects.side_effect = [
            [],  # No fixtures
        ]

        with (
            patch("fpl_curate.handlers.curate_all.S3Client", return_value=mock_s3_client),
            patch("fpl_curate.handlers.curate_all.get_curate_settings", return_value=mock_settings),
        ):
            result = await main(season="2025-26", gameweek=31, force=True)

        assert result["status"] == "failed"
