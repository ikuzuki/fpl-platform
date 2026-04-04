"""Unit tests for Understat collector."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fpl_data.collectors.understat_collector import (
    UnderstatCollector,
    _season_to_understat_year,
)

SAMPLE_PLAYERS_RESPONSE = {
    "success": True,
    "players": [
        {
            "id": "1250",
            "player_name": "Mohamed Salah",
            "games": "38",
            "time": "3392",
            "goals": "29",
            "xG": "27.71",
            "assists": "18",
            "xA": "15.86",
            "shots": "130",
            "key_passes": "89",
            "yellow_cards": "1",
            "red_cards": "0",
            "position": "F M",
            "team_title": "Liverpool",
            "npg": "20",
            "npxG": "20.86",
            "xGChain": "48.54",
            "xGBuildup": "16.21",
        },
        {
            "id": "8260",
            "player_name": "Erling Haaland",
            "games": "34",
            "time": "2890",
            "goals": "27",
            "xG": "24.50",
            "assists": "5",
            "xA": "3.20",
            "shots": "110",
            "key_passes": "25",
            "yellow_cards": "3",
            "red_cards": "0",
            "position": "F",
            "team_title": "Manchester City",
            "npg": "22",
            "npxG": "20.10",
            "xGChain": "30.20",
            "xGBuildup": "5.40",
        },
    ],
}


@pytest.fixture
def mock_s3_client() -> MagicMock:
    client = MagicMock()
    client.list_objects.return_value = []
    client.put_json.return_value = None
    return client


@pytest.fixture
def collector(mock_s3_client: MagicMock) -> UnderstatCollector:
    return UnderstatCollector(s3_client=mock_s3_client, output_bucket="test-bucket")


# --- season conversion ---


@pytest.mark.unit
def test_season_to_understat_year() -> None:
    assert _season_to_understat_year("2025-26") == "2025"
    assert _season_to_understat_year("2024-25") == "2024"


# --- collect_league_stats tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_league_stats_success(
    collector: UnderstatCollector,
    mock_s3_client: MagicMock,
) -> None:
    with patch.object(
        collector,
        "_fetch_player_stats",
        new_callable=AsyncMock,
        return_value=SAMPLE_PLAYERS_RESPONSE["players"],
    ):
        result = await collector.collect_league_stats("2024-25")

    assert result.status == "success"
    assert result.records_collected == 2
    assert "raw/understat/season=2024-25/league_stats/" in result.output_path
    mock_s3_client.put_json.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_league_stats_skips_if_exists(
    collector: UnderstatCollector,
    mock_s3_client: MagicMock,
) -> None:
    mock_s3_client.list_objects.return_value = ["existing.json"]

    with patch.object(
        collector, "_fetch_player_stats", new_callable=AsyncMock
    ) as mock_fetch:
        result = await collector.collect_league_stats("2024-25")

    mock_fetch.assert_not_called()
    assert result.records_collected == 0


# --- collect_player_stats tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_player_stats_success(
    collector: UnderstatCollector,
    mock_s3_client: MagicMock,
) -> None:
    with patch.object(
        collector,
        "_fetch_player_stats",
        new_callable=AsyncMock,
        return_value=SAMPLE_PLAYERS_RESPONSE["players"],
    ), patch("asyncio.sleep", new_callable=AsyncMock):
        result = await collector.collect_player_stats(1250, "2024-25")

    assert result.status == "success"
    assert result.records_collected == 1
    assert "players/1250/" in result.output_path
    # Verify only the matched player was written, not the full list
    written_data = mock_s3_client.put_json.call_args[0][2]
    assert written_data["player_name"] == "Mohamed Salah"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_player_stats_not_found(
    collector: UnderstatCollector,
    mock_s3_client: MagicMock,
) -> None:
    with patch.object(
        collector,
        "_fetch_player_stats",
        new_callable=AsyncMock,
        return_value=SAMPLE_PLAYERS_RESPONSE["players"],
    ), patch("asyncio.sleep", new_callable=AsyncMock):
        result = await collector.collect_player_stats(9999, "2024-25")

    assert result.status == "partial"
    assert result.records_collected == 0
    mock_s3_client.put_json.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_player_stats_rate_limits(
    collector: UnderstatCollector,
) -> None:
    with patch.object(
        collector,
        "_fetch_player_stats",
        new_callable=AsyncMock,
        return_value=SAMPLE_PLAYERS_RESPONSE["players"],
    ), patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await collector.collect_player_stats(1250, "2024-25")

    mock_sleep.assert_called_once_with(1.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_player_stats_skips_if_exists(
    collector: UnderstatCollector,
    mock_s3_client: MagicMock,
) -> None:
    mock_s3_client.list_objects.return_value = ["existing.json"]

    with patch.object(
        collector, "_fetch_player_stats", new_callable=AsyncMock
    ) as mock_fetch:
        result = await collector.collect_player_stats(1250, "2024-25")

    mock_fetch.assert_not_called()
    assert result.records_collected == 0


# --- _fetch_player_stats tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_player_stats_success(
    collector: UnderstatCollector,
) -> None:
    mock_response = httpx.Response(
        200,
        json=SAMPLE_PLAYERS_RESPONSE,
        request=httpx.Request("POST", "https://understat.com/main/getPlayersStats/"),
    )
    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await collector._fetch_player_stats("EPL", "2024")

    assert len(result) == 2
    assert result[0]["player_name"] == "Mohamed Salah"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_player_stats_api_failure(
    collector: UnderstatCollector,
) -> None:
    mock_response = httpx.Response(
        200,
        json={"success": False},
        request=httpx.Request("POST", "https://understat.com/main/getPlayersStats/"),
    )
    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ),
        pytest.raises(ValueError, match="success=false"),
    ):
        await collector._fetch_player_stats("EPL", "2024")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_player_stats_http_error(
    collector: UnderstatCollector,
) -> None:
    mock_response = httpx.Response(
        500,
        request=httpx.Request("POST", "https://understat.com/main/getPlayersStats/"),
    )
    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await collector._fetch_player_stats("EPL", "2024")
