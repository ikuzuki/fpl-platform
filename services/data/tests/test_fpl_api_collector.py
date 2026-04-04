"""Unit tests for FPL API collector."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fpl_data.collectors.fpl_api_collector import FPL_BASE_URL, FPLAPICollector


@pytest.fixture
def mock_s3_client() -> MagicMock:
    client = MagicMock()
    client.list_objects.return_value = []
    client.put_json.return_value = None
    return client


@pytest.fixture
def collector(mock_s3_client: MagicMock) -> FPLAPICollector:
    return FPLAPICollector(s3_client=mock_s3_client, output_bucket="test-bucket")


@pytest.fixture
def bootstrap_response() -> dict:
    return {
        "elements": [
            {"id": 1, "web_name": "Salah", "team": 14},
            {"id": 2, "web_name": "Haaland", "team": 11},
            {"id": 3, "web_name": "Saka", "team": 1},
        ],
        "teams": [{"id": 1, "name": "Arsenal"}],
        "events": [{"id": 1, "name": "Gameweek 1"}],
    }


@pytest.fixture
def fixtures_response() -> list:
    return [
        {"id": 1, "event": 1, "team_h": 1, "team_a": 2},
        {"id": 2, "event": 1, "team_h": 3, "team_a": 4},
    ]


@pytest.fixture
def gameweek_live_response() -> dict:
    return {
        "elements": [
            {"id": 1, "stats": {"total_points": 10}},
            {"id": 2, "stats": {"total_points": 6}},
        ]
    }


@pytest.fixture
def player_history_response() -> dict:
    return {
        "history": [
            {"round": 1, "total_points": 8},
            {"round": 2, "total_points": 12},
        ],
        "fixtures": [{"id": 100, "event": 3}],
    }


def _mock_response(data: dict | list, status_code: int = 200) -> httpx.Response:
    """Create a mock httpx.Response."""
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code=status_code, json=data, request=request)
    return response


# --- collect_bootstrap tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_bootstrap_success(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
    bootstrap_response: dict,
) -> None:
    with patch.object(collector, "_fetch", new_callable=AsyncMock, return_value=bootstrap_response):
        result = await collector.collect_bootstrap("2025-26")

    assert result.status == "success"
    assert result.records_collected == 3
    assert "raw/fpl-api/season=2025-26/bootstrap/" in result.output_path
    mock_s3_client.put_json.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_bootstrap_skips_if_exists(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
) -> None:
    mock_s3_client.list_objects.return_value = [
        "raw/fpl-api/season=2025-26/bootstrap/existing.json"
    ]

    with patch.object(collector, "_fetch", new_callable=AsyncMock) as mock_fetch:
        result = await collector.collect_bootstrap("2025-26")

    mock_fetch.assert_not_called()
    mock_s3_client.put_json.assert_not_called()
    assert result.records_collected == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_bootstrap_force_overwrites(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
    bootstrap_response: dict,
) -> None:
    mock_s3_client.list_objects.return_value = [
        "raw/fpl-api/season=2025-26/bootstrap/existing.json"
    ]

    with patch.object(collector, "_fetch", new_callable=AsyncMock, return_value=bootstrap_response):
        result = await collector.collect_bootstrap("2025-26", force=True)

    assert result.records_collected == 3
    mock_s3_client.put_json.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_bootstrap_raises_on_http_error(
    collector: FPLAPICollector,
) -> None:
    async def _raise_500(url: str) -> None:
        request = httpx.Request("GET", url)
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("Server error", request=request, response=response)

    with (
        patch.object(collector, "_fetch", side_effect=_raise_500),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await collector.collect_bootstrap("2025-26")


# --- collect_fixtures tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_fixtures_success(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
    fixtures_response: list,
) -> None:
    with patch.object(collector, "_fetch", new_callable=AsyncMock, return_value=fixtures_response):
        result = await collector.collect_fixtures("2025-26")

    assert result.status == "success"
    assert result.records_collected == 2
    assert "raw/fpl-api/season=2025-26/fixtures/" in result.output_path
    mock_s3_client.put_json.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_fixtures_skips_if_exists(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
) -> None:
    mock_s3_client.list_objects.return_value = ["existing.json"]

    with patch.object(collector, "_fetch", new_callable=AsyncMock) as mock_fetch:
        result = await collector.collect_fixtures("2025-26")

    mock_fetch.assert_not_called()
    assert result.records_collected == 0


# --- collect_gameweek_live tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_gameweek_live_success(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
    gameweek_live_response: dict,
) -> None:
    with patch.object(
        collector, "_fetch", new_callable=AsyncMock, return_value=gameweek_live_response
    ):
        result = await collector.collect_gameweek_live("2025-26", 5)

    assert result.status == "success"
    assert result.records_collected == 2
    assert "gameweek=05" in result.output_path
    mock_s3_client.put_json.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_gameweek_live_path_formatting(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
    gameweek_live_response: dict,
) -> None:
    with patch.object(
        collector, "_fetch", new_callable=AsyncMock, return_value=gameweek_live_response
    ):
        result = await collector.collect_gameweek_live("2025-26", 1)

    assert "season=2025-26/gameweek=01/" in result.output_path


# --- collect_player_history tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_player_history_success(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
    player_history_response: dict,
) -> None:
    with patch.object(
        collector, "_fetch", new_callable=AsyncMock, return_value=player_history_response
    ):
        result = await collector.collect_player_history(1, "2025-26")

    assert result.status == "success"
    assert result.records_collected == 2
    assert "players/1/" in result.output_path
    mock_s3_client.put_json.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_player_history_skips_if_exists(
    collector: FPLAPICollector,
    mock_s3_client: MagicMock,
) -> None:
    mock_s3_client.list_objects.return_value = ["existing.json"]

    with patch.object(collector, "_fetch", new_callable=AsyncMock) as mock_fetch:
        result = await collector.collect_player_history(1, "2025-26")

    mock_fetch.assert_not_called()
    assert result.records_collected == 0


# --- _fetch tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_calls_correct_url(
    collector: FPLAPICollector,
    bootstrap_response: dict,
) -> None:
    mock_response = _mock_response(bootstrap_response)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        data = await collector._fetch(f"{FPL_BASE_URL}/bootstrap-static/")

    assert data["elements"] == bootstrap_response["elements"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_raises_on_server_error(
    collector: FPLAPICollector,
) -> None:
    mock_response = _mock_response({}, status_code=500)
    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await collector._fetch(f"{FPL_BASE_URL}/bootstrap-static/")


# --- handler tests ---


@pytest.mark.unit
def test_handler_calls_all_default_endpoints() -> None:
    from fpl_data.handlers.fpl_api_handler import lambda_handler

    with patch("fpl_data.handlers.fpl_api_handler.main", new_callable=AsyncMock) as mock_main:
        mock_main.return_value = {"responses": []}
        lambda_handler({"season": "2025-26", "gameweek": 1}, None)

    mock_main.assert_called_once_with(season="2025-26", gameweek=1)


@pytest.mark.unit
def test_handler_passes_optional_params() -> None:
    from fpl_data.handlers.fpl_api_handler import lambda_handler

    with patch("fpl_data.handlers.fpl_api_handler.main", new_callable=AsyncMock) as mock_main:
        mock_main.return_value = {"responses": []}
        lambda_handler(
            {
                "season": "2025-26",
                "gameweek": 1,
                "endpoints": ["bootstrap"],
                "force": True,
            },
            None,
        )

    mock_main.assert_called_once_with(
        season="2025-26", gameweek=1, endpoints=["bootstrap"], force=True
    )


@pytest.mark.unit
def test_handler_returns_400_on_missing_params() -> None:
    from fpl_data.handlers.fpl_api_handler import lambda_handler

    result = lambda_handler({"season": "2025-26"}, None)
    assert result["statusCode"] == 400
    assert "gameweek" in result["body"]["error"]
