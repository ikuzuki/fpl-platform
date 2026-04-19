"""Unit tests for agent tool implementations."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from fpl_agent.tools.player_tools import ToolError, make_tools

pytestmark = pytest.mark.unit


def _mock_neon(
    fetch_one: Any = None,
    fetch: Any = None,
) -> MagicMock:
    neon = MagicMock()
    neon.fetch_one = AsyncMock(return_value=fetch_one)
    neon.fetch = AsyncMock(return_value=fetch)
    return neon


def _fake_row(**overrides: Any) -> dict[str, Any]:
    base = {
        "player_id": 1,
        "season": "2025-26",
        "gameweek": 30,
        "web_name": "Salah",
        "team_name": "Liverpool",
        "position": "MID",
        "price": 13.5,
        "total_points": 180,
        "form": 7.5,
        "goals_scored": 18,
        "assists": 10,
        "minutes": 2500,
        "summary": "In strong form.",
        "form_trend": "improving",
        "injury_risk_score": 2,
        "fixture_difficulty": 2.8,
        "embedding": [0.1] * 384,
        "updated_at": "2026-04-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_make_tools_returns_all_five_tool_names() -> None:
    tools = make_tools(_mock_neon())
    assert set(tools.keys()) == {
        "query_player",
        "search_similar_players",
        "query_players_by_criteria",
        "get_fixture_outlook",
        "get_injury_signals",
    }


@pytest.mark.asyncio
async def test_query_player_returns_row_without_embedding() -> None:
    neon = _mock_neon(fetch_one=_fake_row())
    tools = make_tools(neon)

    result = await tools["query_player"](name="Salah")

    assert result["web_name"] == "Salah"
    assert "embedding" not in result  # stripped to keep payload small


@pytest.mark.asyncio
async def test_query_player_raises_tool_error_when_missing() -> None:
    tools = make_tools(_mock_neon(fetch_one=None))
    with pytest.raises(ToolError, match="No player found"):
        await tools["query_player"](name="Nobody")


@pytest.mark.asyncio
async def test_search_similar_players_returns_target_and_neighbours() -> None:
    target = _fake_row(web_name="Salah", player_id=1)
    neighbours = [
        _fake_row(web_name="Palmer", player_id=2),
        _fake_row(web_name="Saka", player_id=3),
    ]
    neon = _mock_neon(fetch_one=target, fetch=neighbours)
    tools = make_tools(neon)

    result = await tools["search_similar_players"](player_name="Salah", k=2)

    assert result["target"] == "Salah"
    assert [p["web_name"] for p in result["similar"]] == ["Palmer", "Saka"]
    assert all("embedding" not in p for p in result["similar"])


@pytest.mark.asyncio
async def test_search_similar_players_raises_when_target_missing() -> None:
    tools = make_tools(_mock_neon(fetch_one=None))
    with pytest.raises(ToolError, match="No player found"):
        await tools["search_similar_players"](player_name="Unknown")


@pytest.mark.asyncio
async def test_query_players_by_criteria_builds_filtered_query() -> None:
    neon = _mock_neon(fetch=[_fake_row(), _fake_row(web_name="Palmer")])
    tools = make_tools(neon)

    result = await tools["query_players_by_criteria"](position="MID", max_price=10.0, limit=5)

    assert result["count"] == 2
    neon.fetch.assert_awaited_once()
    query = neon.fetch.await_args.args[0]
    assert "position = $1" in query
    assert "price <= $2" in query
    # The three positional args are: position, max_price, limit.
    assert neon.fetch.await_args.args[1:] == ("MID", 10.0, 5)


@pytest.mark.asyncio
async def test_query_players_by_criteria_no_filters() -> None:
    neon = _mock_neon(fetch=[])
    tools = make_tools(neon)

    await tools["query_players_by_criteria"]()

    query = neon.fetch.await_args.args[0]
    assert "WHERE" not in query  # all filters optional


@pytest.mark.asyncio
async def test_get_fixture_outlook_returns_difficulty_with_caveat_note() -> None:
    neon = _mock_neon(fetch_one=_fake_row(fixture_difficulty=3.1))
    tools = make_tools(neon)

    result = await tools["get_fixture_outlook"](player_name="Salah")

    assert result["difficulty"] == 3.1
    assert "per-GW breakdown not yet available" in result["note"]


@pytest.mark.asyncio
async def test_get_injury_signals_returns_expected_fields() -> None:
    neon = _mock_neon(fetch_one=_fake_row(injury_risk_score=5, form_trend="declining"))
    tools = make_tools(neon)

    result = await tools["get_injury_signals"](player_name="Salah")

    assert result["injury_risk_score"] == 5
    assert result["form_trend"] == "declining"
    assert "summary" in result


# Squad loading is intentionally not a tool — it's an HTTP-layer concern
# (see fpl_agent.squad_loader and the GET /team route). Coverage for that
# path lives in tests/test_squad_loader.py.
