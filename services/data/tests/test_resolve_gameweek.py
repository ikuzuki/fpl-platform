"""Unit tests for the gameweek resolution handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fpl_data.collectors.gameweek_resolver import GameweekInfo, resolve_gameweek
from fpl_data.handlers.resolve_gameweek import latest_processed_gameweek, main


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
        patch(
            "fpl_data.handlers.resolve_gameweek.latest_processed_gameweek",
            return_value=0,
        ),
    ):
        result = await main()

    resolver.assert_awaited_once_with(season="2031-32")
    assert result["season"] == "2031-32"


@pytest.mark.asyncio
async def test_handler_honours_explicit_season_for_backfill() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(5, 5, "2024-25"))

    with (
        patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver),
        patch("fpl_data.handlers.resolve_gameweek.latest_processed_gameweek", return_value=0),
    ):
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


# --- derived processed-state (daily schedule idempotency) -------------------


def _s3_with_keys(keys: list[str]) -> MagicMock:
    client = MagicMock()
    client.list_objects.return_value = keys
    return client


def test_latest_processed_gameweek_takes_the_max_from_marker_keys() -> None:
    keys = [
        "curated/player_dashboard/season=2026-27/gameweek=01/player_dashboard.parquet",
        "curated/player_dashboard/season=2026-27/gameweek=13/player_dashboard.parquet",
        "curated/player_dashboard/season=2026-27/gameweek=09/player_dashboard.parquet",
    ]
    assert latest_processed_gameweek(_s3_with_keys(keys), "bucket", "2026-27") == 13


def test_latest_processed_gameweek_is_zero_before_any_run() -> None:
    assert latest_processed_gameweek(_s3_with_keys([]), "bucket", "2026-27") == 0


def test_latest_processed_gameweek_reads_the_curated_marker_not_the_clean_parquet() -> None:
    """A run that dies during enrichment leaves clean data behind but is not processed.

    Keying off the clean parquet would strand that gameweek as permanently done.
    """
    client = _s3_with_keys([])
    latest_processed_gameweek(client, "bucket", "2026-27")
    prefix = client.list_objects.call_args.args[1]
    assert prefix == "curated/player_dashboard/season=2026-27/"


@pytest.mark.asyncio
async def test_handler_skips_when_derived_state_says_gameweek_is_done() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(4, 4, "2026-27"))

    with (
        patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver),
        patch("fpl_data.handlers.resolve_gameweek.latest_processed_gameweek", return_value=4),
    ):
        result = await main(season="2026-27")

    assert result["should_run"] is False
    assert result["reason"] == "GW4 already processed"


@pytest.mark.asyncio
async def test_handler_runs_when_derived_state_is_behind_the_finished_gameweek() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(5, 5, "2026-27"))

    with (
        patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver),
        patch("fpl_data.handlers.resolve_gameweek.latest_processed_gameweek", return_value=4),
    ):
        result = await main(season="2026-27")

    assert result["should_run"] is True
    assert result["gameweek"] == 5


@pytest.mark.asyncio
async def test_handler_retries_the_same_gameweek_after_a_failed_run() -> None:
    """A failed run writes no marker, so the next day resolves the same gameweek."""
    resolver = AsyncMock(return_value=GameweekInfo(6, 6, "2026-27"))

    with (
        patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver),
        patch("fpl_data.handlers.resolve_gameweek.latest_processed_gameweek", return_value=5),
    ):
        first = await main(season="2026-27")
        second = await main(season="2026-27")

    assert first["gameweek"] == second["gameweek"] == 6
    assert first["should_run"] is second["should_run"] is True


@pytest.mark.asyncio
async def test_handler_does_not_touch_s3_when_last_processed_gw_is_explicit() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(7, 7, "2026-27"))
    lookup = MagicMock(return_value=99)

    with (
        patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver),
        patch("fpl_data.handlers.resolve_gameweek.latest_processed_gameweek", lookup),
    ):
        result = await main(season="2026-27", last_processed_gw=0)

    lookup.assert_not_called()
    assert result["should_run"] is True


@pytest.mark.asyncio
async def test_handler_force_overrides_derived_state() -> None:
    resolver = AsyncMock(return_value=GameweekInfo(8, 8, "2026-27"))

    with (
        patch("fpl_data.handlers.resolve_gameweek.resolve_gameweek", resolver),
        patch("fpl_data.handlers.resolve_gameweek.latest_processed_gameweek", return_value=8),
    ):
        result = await main(season="2026-27", force=True)

    assert result["should_run"] is True
