"""Unit tests for player data transformation."""

import logging
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fpl_data.transformers.player_transformer import (
    COLUMN_MAP,
    deduplicate,
    flatten_player_data,
    join_understat,
)


def _make_raw_bootstrap(players: list[dict] | None = None) -> dict:
    """Create a minimal raw bootstrap response."""
    if players is None:
        players = [
            {
                "id": 1,
                "web_name": "Salah",
                "first_name": "Mohamed",
                "second_name": "Salah",
                "team": 14,
                "element_type": 3,
                "now_cost": 130,
                "total_points": 180,
                "minutes": 2800,
                "goals_scored": 20,
                "assists": 12,
                "clean_sheets": 10,
                "goals_conceded": 25,
                "yellow_cards": 1,
                "red_cards": 0,
                "bonus": 30,
                "bps": 800,
                "starts": 30,
                "expected_goals": "18.5",
                "expected_assists": "10.2",
                "expected_goal_involvements": "28.7",
                "form": "8.5",
                "points_per_game": "6.0",
                "selected_by_percent": "45.2",
                "status": "a",
                "news": "",
                "chance_of_playing_next_round": 100,
                "transfers_in_event": 50000,
                "transfers_out_event": 10000,
                "influence": "1200.0",
                "creativity": "900.0",
                "threat": "1100.0",
                "ict_index": "320.0",
            },
            {
                "id": 2,
                "web_name": "Haaland",
                "first_name": "Erling",
                "second_name": "Haaland",
                "team": 11,
                "element_type": 4,
                "now_cost": 145,
                "total_points": 200,
                "minutes": 2500,
                "goals_scored": 25,
                "assists": 5,
                "clean_sheets": 8,
                "goals_conceded": 30,
                "yellow_cards": 3,
                "red_cards": 0,
                "bonus": 35,
                "bps": 900,
                "starts": 28,
                "expected_goals": "22.1",
                "expected_assists": "3.5",
                "expected_goal_involvements": "25.6",
                "form": "9.0",
                "points_per_game": "7.1",
                "selected_by_percent": "55.0",
                "status": "a",
                "news": "",
                "chance_of_playing_next_round": 100,
                "transfers_in_event": 80000,
                "transfers_out_event": 5000,
                "influence": "1000.0",
                "creativity": "500.0",
                "threat": "1500.0",
                "ict_index": "300.0",
            },
        ]
    return {"elements": players, "teams": [], "events": []}


@pytest.mark.unit
def test_flatten_player_data_correct_columns() -> None:
    raw = _make_raw_bootstrap()
    df = flatten_player_data(raw, "2025-26")

    expected_cols = set(COLUMN_MAP.values()) | {"season", "collected_at"}
    assert set(df.columns) == expected_cols
    assert len(df) == 2


@pytest.mark.unit
def test_flatten_player_data_type_casting() -> None:
    raw = _make_raw_bootstrap()
    df = flatten_player_data(raw, "2025-26")

    # Int columns
    assert df["id"].dtype == "Int64"
    assert df["total_points"].dtype == "Int64"
    assert df["minutes"].dtype == "Int64"

    # Float columns (raw API returns these as strings)
    assert df["expected_goals"].dtype == "Float64"
    assert df["form"].dtype == "Float64"
    assert df["ict_index"].dtype == "Float64"


@pytest.mark.unit
def test_flatten_player_data_adds_season_and_collected_at() -> None:
    raw = _make_raw_bootstrap()
    df = flatten_player_data(raw, "2025-26")

    assert all(df["season"] == "2025-26")
    assert all(df["collected_at"].str.contains("T"))  # ISO format


@pytest.mark.unit
def test_flatten_player_data_empty_elements() -> None:
    raw = {"elements": [], "teams": [], "events": []}
    df = flatten_player_data(raw, "2025-26")

    assert df.empty


@pytest.mark.unit
def test_deduplicate_removes_duplicates() -> None:
    df = pd.DataFrame({"id": [1, 2, 1], "web_name": ["Salah", "Haaland", "Salah-dupe"]})
    result = deduplicate(df, ["id"])

    assert len(result) == 2
    # Keeps last occurrence
    assert result[result["id"] == 1]["web_name"].iloc[0] == "Salah-dupe"


@pytest.mark.unit
def test_deduplicate_no_duplicates() -> None:
    df = pd.DataFrame({"id": [1, 2, 3], "web_name": ["A", "B", "C"]})
    result = deduplicate(df, ["id"])

    assert len(result) == 3


@pytest.mark.unit
def test_new_column_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    raw = _make_raw_bootstrap()
    # Add an unexpected column
    raw["elements"][0]["brand_new_field"] = "surprise"
    raw["elements"][1]["brand_new_field"] = "surprise"

    with caplog.at_level(logging.WARNING):
        flatten_player_data(raw, "2025-26")

    assert any("brand_new_field" in msg for msg in caplog.messages)


# --- handler tests ---


@pytest.mark.unit
def test_handler_returns_400_on_missing_params() -> None:
    from fpl_data.handlers.transform import lambda_handler

    result = lambda_handler({"season": "2025-26"}, None)
    assert result["statusCode"] == 400


@pytest.mark.unit
def test_transform_skips_if_output_exists() -> None:
    import asyncio

    from fpl_data.handlers.transform import main

    mock_s3 = MagicMock()
    mock_s3.object_exists.return_value = True

    with patch("fpl_data.handlers.transform.S3Client", return_value=mock_s3):
        result = asyncio.run(main("2025-26", 1))

    assert result["status"] == "valid"
    assert "Skipped" in result["warnings"][0]
    mock_s3.write_parquet.assert_not_called()


@pytest.mark.unit
def test_transform_overwrites_with_force_flag() -> None:
    import asyncio

    from fpl_data.handlers.transform import main

    raw = _make_raw_bootstrap()
    mock_s3 = MagicMock()
    mock_s3.object_exists.return_value = True
    mock_s3.list_objects.side_effect = lambda bucket, prefix: (
        ["raw/fpl-api/season=2025-26/bootstrap/2025.json"]
        if "bootstrap" in prefix
        else []  # No Understat data
    )
    mock_s3.read_json.return_value = raw

    with patch("fpl_data.handlers.transform.S3Client", return_value=mock_s3):
        result = asyncio.run(main("2025-26", 1, force=True))

    assert result["status"] == "valid"
    assert result["records_valid"] == 2
    mock_s3.write_parquet.assert_called_once()


@pytest.mark.unit
class TestJoinUnderstat:
    def test_joins_by_full_name(self) -> None:
        raw = _make_raw_bootstrap()
        df = flatten_player_data(raw, "2025-26")
        understat = [
            {
                "player_name": "Mohamed Salah",
                "xG": "15.5",
                "xA": "8.2",
                "npxG": "12.1",
                "npg": "14",
                "shots": "80",
                "key_passes": "45",
                "xGChain": "20.0",
                "xGBuildup": "10.0",
            },
        ]
        result = join_understat(df, understat)

        assert "understat_xg" in result.columns
        salah = result[result["web_name"] == "Salah"].iloc[0]
        assert salah["understat_xg"] == pytest.approx(15.5)
        assert salah["understat_xa"] == pytest.approx(8.2)

    def test_unmatched_players_get_nan(self) -> None:
        raw = _make_raw_bootstrap()
        df = flatten_player_data(raw, "2025-26")
        understat = [
            {
                "player_name": "Unknown Player",
                "xG": "5.0",
                "xA": "2.0",
                "npxG": "4.0",
                "npg": "3",
                "shots": "20",
                "key_passes": "10",
                "xGChain": "6.0",
                "xGBuildup": "3.0",
            },
        ]
        result = join_understat(df, understat)

        assert result["understat_xg"].isna().all()

    def test_empty_understat_returns_unchanged(self) -> None:
        raw = _make_raw_bootstrap()
        df = flatten_player_data(raw, "2025-26")
        result = join_understat(df, [])

        assert "understat_xg" not in result.columns
        assert len(result) == len(df)
