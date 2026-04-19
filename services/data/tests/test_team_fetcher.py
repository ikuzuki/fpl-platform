"""Unit tests for FPL Team Fetcher."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from curl_cffi.requests import Response as CurlResponse

from fpl_data.collectors.exceptions import FPLAccessError, TeamNotFoundError
from fpl_data.collectors.team_fetcher import TeamFetcher
from fpl_data.handlers.team_fetcher import lambda_handler


@pytest.fixture
def fetcher() -> TeamFetcher:
    return TeamFetcher()


@pytest.fixture
def squad_response() -> dict:
    """Mirror the real FPL API shape captured against team_id=5767400 GW33.

    Notable fields the v1 fixture omitted: ``element_type`` on each pick
    (1=GK, 2=DEF, 3=MID, 4=FWD), and the rich ``entry_history`` block with
    ``bank`` / ``value`` (in tenths of millions on the wire) plus
    ``overall_rank``.
    """
    return {
        "picks": [
            {
                "element": 1,
                "position": 1,
                "multiplier": 2,
                "is_captain": True,
                "is_vice_captain": False,
                "element_type": 1,
            },
            {
                "element": 2,
                "position": 2,
                "multiplier": 1,
                "is_captain": False,
                "is_vice_captain": True,
                "element_type": 2,
            },
        ],
        "active_chip": None,
        "automatic_subs": [],
        "entry_history": {
            "event": 33,
            "points": 65,
            "total_points": 1200,
            "rank": 50000,
            "rank_sort": 51000,
            "overall_rank": 493581,
            "percentile_rank": 10,
            "bank": 32,
            "value": 1031,
            "event_transfers": 0,
            "event_transfers_cost": 0,
            "points_on_bench": 13,
        },
    }


def _mock_curl_response(data: dict | list, status_code: int = 200) -> MagicMock:
    """Create a mock curl_cffi Response."""
    response = MagicMock(spec=CurlResponse)
    response.status_code = status_code
    response.content = json.dumps(data).encode()
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        from curl_cffi.requests.errors import RequestsError

        response.raise_for_status.side_effect = RequestsError(
            f"HTTP {status_code}", code=status_code
        )
    return response


# --- fetch_squad tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_squad_success(fetcher: TeamFetcher, squad_response: dict) -> None:
    mock_response = _mock_curl_response(squad_response)
    with patch("fpl_data.collectors.team_fetcher.AsyncSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetcher.fetch_squad(team_id=12345, gameweek=10)

    assert "picks" in result
    assert len(result["picks"]) == 2
    assert result["active_chip"] is None


# --- error handling tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_returns_404_raises_team_not_found(fetcher: TeamFetcher) -> None:
    mock_response = _mock_curl_response({}, status_code=404)
    with patch("fpl_data.collectors.team_fetcher.AsyncSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(TeamNotFoundError) as exc_info:
            await fetcher.fetch_squad(team_id=99999, gameweek=1)

    assert exc_info.value.team_id == 99999


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_returns_403_retries_once(fetcher: TeamFetcher) -> None:
    mock_403 = _mock_curl_response({}, status_code=403)
    mock_200 = _mock_curl_response({"picks": []})

    with (
        patch("fpl_data.collectors.team_fetcher.AsyncSession") as mock_session_cls,
        patch(
            "fpl_data.collectors.team_fetcher.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        mock_session = AsyncMock()
        mock_session.get.side_effect = [mock_403, mock_200]
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetcher.fetch_squad(team_id=12345, gameweek=1)

    assert mock_session.get.call_count == 2
    mock_sleep.assert_called_once_with(2)
    assert "picks" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_returns_403_twice_raises_access_error(fetcher: TeamFetcher) -> None:
    mock_403 = _mock_curl_response({}, status_code=403)

    with (
        patch("fpl_data.collectors.team_fetcher.AsyncSession") as mock_session_cls,
        patch("fpl_data.collectors.team_fetcher.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_403
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(FPLAccessError) as exc_info:
            await fetcher.fetch_squad(team_id=12345, gameweek=1)

    assert exc_info.value.team_id == 12345


# --- rate limiting tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_enforced(fetcher: TeamFetcher) -> None:
    mock_response = _mock_curl_response({"data": "ok"})

    with (
        patch("fpl_data.collectors.team_fetcher.AsyncSession") as mock_session_cls,
        patch(
            "fpl_data.collectors.team_fetcher.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Make 6 rapid requests — the 6th should trigger rate limiting.
        for _ in range(6):
            await fetcher._fetch("https://example.com/api/test", team_id=0)

    # asyncio.sleep should have been called for rate limiting (not just the 403 retry path).
    assert mock_sleep.call_count >= 1


# --- handler tests ---


@pytest.mark.unit
def test_handler_returns_400_on_missing_team_id() -> None:
    result = lambda_handler({"gameweek": 1}, None)
    assert result["statusCode"] == 400
    assert "team_id" in result["body"]["error"]
