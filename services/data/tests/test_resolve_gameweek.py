"""Unit tests for the gameweek resolution handler."""

from unittest.mock import AsyncMock, patch

import pytest

from fpl_data.collectors.gameweek_resolver import GameweekInfo, resolve_gameweek
from fpl_data.handlers.resolve_gameweek import main


@pytest.fixture
def bootstrap_response() -> dict:
    return {
        "events": [
            {"id": 1, "finished": True, "is_current": False},
            {"id": 2, "finished": True, "is_current": True},
            {"id": 3, "finished": False, "is_current": False},
        ]
    }


@pytest.mark.asyncio
async def test_resolve_gameweek_reads_current_and_latest_finished(
    bootstrap_response: dict,
) -> None:
    with patch(
        "fpl_data.collectors.gameweek_resolver.fpl_fetch",
        AsyncMock(return_value=bootstrap_response),
    ):
        info = await resolve_gameweek(season="2026-27")

    assert info.current_gw == 2
    assert info.latest_finished_gw == 2
    assert info.season == "2026-27"


@pytest.mark.asyncio
async def test_resolve_gameweek_falls_back_to_latest_finished_when_none_current() -> None:
    response = {"events": [{"id": 38, "finished": True, "is_current": False}]}

    with patch(
        "fpl_data.collectors.gameweek_resolver.fpl_fetch",
        AsyncMock(return_value=response),
    ):
        info = await resolve_gameweek(season="2026-27")

    assert info.current_gw == 38


@pytest.mark.asyncio
async def test_resolve_gameweek_raises_on_empty_events() -> None:
    with (
        patch(
            "fpl_data.collectors.gameweek_resolver.fpl_fetch",
            AsyncMock(return_value={"events": []}),
        ),
        pytest.raises(ValueError, match="No events found"),
    ):
        await resolve_gameweek(season="2026-27")


@pytest.mark.asyncio
async def test_handler_derives_season_from_current_date_when_not_supplied() -> None:
    """The scheduled pipeline omits season, so the handler must not pin a stale one."""
    resolver = AsyncMock(return_value=GameweekInfo(2, 2, "2031-32"))

    with (
        patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver),
        patch(
            "fpl_data.handlers.resolve_gameweek.current_season",
            return_value="2031-32",
        ),
    ):
        result = await main()

    resolver.assert_awaited_once_with(season="2031-32")
    assert result["season"] == "2031-32"


@pytest.mark.asyncio
async def test_handler_honours_explicit_season_for_backfill() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(5, 5, "2024-25"))

    with patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver):
        result = await main(season="2024-25")

    resolver.assert_awaited_once_with(season="2024-25")
    assert result["season"] == "2024-25"


@pytest.mark.asyncio
async def test_handler_skips_when_gameweek_already_processed() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(3, 3, "2026-27"))

    with patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver):
        result = await main(season="2026-27", last_processed_gw=3)

    assert result["should_run"] is False


@pytest.mark.asyncio
async def test_handler_runs_when_forced_despite_already_processed() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(3, 3, "2026-27"))

    with patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver):
        result = await main(season="2026-27", last_processed_gw=3, force=True)

    assert result["should_run"] is True


@pytest.mark.asyncio
async def test_handler_does_not_run_before_the_first_gameweek_finishes() -> None:
    """Pre-season the API reports no finished gameweeks; the pipeline must no-op."""
    resolver = AsyncMock(return_value=GameweekInfo(0, 0, "2026-27"))

    with patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver):
        result = await main(season="2026-27")

    assert result["should_run"] is False
    assert result["gameweek"] == 0
