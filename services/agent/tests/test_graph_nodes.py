"""Unit tests for agent graph nodes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from fpl_agent.graph import nodes
from fpl_agent.graph.config import MAX_ITERATIONS
from fpl_agent.graph.nodes import (
    planner_node,
    recommender_node,
    reflector_node,
    route_after_reflector,
    tool_executor_node,
)
from fpl_agent.models.state import AgentState, ToolCall, initial_state
from fpl_agent.tools.player_tools import ToolError

pytestmark = pytest.mark.unit


# ----------------------------------------------------------------------------
# Anthropic client mocking helpers
# ----------------------------------------------------------------------------
def _tool_use_response(tool_name: str, input_payload: dict[str, Any]) -> MagicMock:
    """Build a fake Anthropic response with one tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = input_payload

    response = MagicMock()
    response.content = [block]
    response.usage = MagicMock(input_tokens=100, output_tokens=50)
    return response


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


def _valid_scout_report_payload() -> dict[str, Any]:
    return {
        "question": "Is Salah worth it?",
        "analysis": "Salah has 180 points at 13.5, form 7.5.",
        "players": [
            {
                "player_name": "Salah",
                "position": "MID",
                "price": 13.5,
                "form": 7.5,
                "fixture_outlook": "green",
                "verdict": "Premium pick with green fixtures.",
                "confidence": 0.85,
            }
        ],
        "comparison": None,
        "recommendation": "Keep Salah.",
        "caveats": ["Fixture difficulty is aggregate only."],
        "data_sources": ["query_player"],
    }


# ============================================================================
# planner_node
# ============================================================================
@pytest.mark.asyncio
async def test_planner_returns_valid_plan() -> None:
    payload = {"plan": [{"name": "query_player", "args": {"name": "Salah"}}]}
    response = _tool_use_response("record_plan", payload)
    client = _mock_client(response)
    state = initial_state("Is Salah worth it?")

    update = await planner_node(state, client=client)

    assert "plan" in update
    assert len(update["plan"]) == 1
    assert update["plan"][0].name == "query_player"
    assert update["tool_calls_made"] == ["query_player"]


@pytest.mark.asyncio
async def test_planner_rejects_unknown_tool_and_clears_stale_plan() -> None:
    payload = {"plan": [{"name": "search_for_goats", "args": {}}]}
    response = _tool_use_response("record_plan", payload)
    client = _mock_client(response)
    # Simulate a second iteration where iter 1's plan is still in state.
    state: AgentState = {
        **initial_state("Nonsense"),
        "plan": [ToolCall(name="query_player", args={"name": "Salah"})],
    }

    update = await planner_node(state, client=client)

    assert "error" in update
    assert "planner failed" in update["error"]
    # Critical: plan must be cleared, else the executor re-runs iter N-1's plan.
    assert update["plan"] == []
    assert update["tool_calls_made"] == []


@pytest.mark.asyncio
async def test_planner_forces_tool_choice() -> None:
    payload = {"plan": []}
    response = _tool_use_response("record_plan", payload)
    client = _mock_client(response)

    await planner_node(initial_state("q"), client=client)

    call_kwargs = client.messages.create.await_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "record_plan"}


@pytest.mark.asyncio
async def test_planner_logs_token_usage(caplog: pytest.LogCaptureFixture) -> None:
    payload = {"plan": [{"name": "query_player", "args": {"name": "Salah"}}]}
    response = _tool_use_response("record_plan", payload)
    client = _mock_client(response)

    with caplog.at_level(logging.INFO, logger="fpl_agent.graph.nodes"):
        await planner_node(initial_state("q"), client=client)

    messages = "\n".join(r.message for r in caplog.records)
    assert "input_tokens=100" in messages
    assert "output_tokens=50" in messages


# ============================================================================
# tool_executor_node
# ============================================================================
@pytest.mark.asyncio
async def test_tool_executor_runs_tools_concurrently() -> None:
    # Two events: each tool awaits the other's "started" before returning.
    # If the executor serialises, the second tool's started event is never
    # set (first is still awaiting it) and the whole test deadlocks until
    # its gather timeout. If the executor runs in parallel, both start,
    # both see the other's event, both return immediately.
    started_a = asyncio.Event()
    started_b = asyncio.Event()

    async def tool_a(**_: Any) -> dict[str, Any]:
        started_a.set()
        await asyncio.wait_for(started_b.wait(), timeout=1.0)
        return {"a": True}

    async def tool_b(**_: Any) -> dict[str, Any]:
        started_b.set()
        await asyncio.wait_for(started_a.wait(), timeout=1.0)
        return {"b": True}

    tools = {"query_player": tool_a, "get_fixture_outlook": tool_b}
    plan = [
        ToolCall(name="query_player", args={"name": "Salah"}),
        ToolCall(name="get_fixture_outlook", args={"player_name": "Salah"}),
    ]
    state: AgentState = {**initial_state("q"), "plan": plan}

    update = await tool_executor_node(state, tools=tools)

    # If both tools returned, concurrency is proven (they rendezvoused on events).
    assert set(update["gathered_data"].keys()) == {
        "query_player(name=Salah)",
        "get_fixture_outlook(player_name=Salah)",
    }


@pytest.mark.asyncio
async def test_tool_executor_records_errors_without_cancelling_siblings() -> None:
    async def broken(**_: Any) -> dict[str, Any]:
        raise ToolError("boom")

    async def ok(**_: Any) -> dict[str, Any]:
        return {"ok": True}

    tools = {"query_player": broken, "get_fixture_outlook": ok}
    plan = [
        ToolCall(name="query_player", args={"name": "X"}),
        ToolCall(name="get_fixture_outlook", args={"player_name": "X"}),
    ]
    state: AgentState = {**initial_state("q"), "plan": plan}

    update = await tool_executor_node(state, tools=tools)

    assert update["gathered_data"]["query_player(name=X)"] == {"error": "boom"}
    assert update["gathered_data"]["get_fixture_outlook(player_name=X)"] == {"ok": True}


@pytest.mark.asyncio
async def test_tool_executor_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nodes, "TOOL_TIMEOUT_SECONDS", 0.05)

    async def too_slow(**_: Any) -> dict[str, Any]:
        await asyncio.sleep(0.5)
        return {"ok": True}

    tools = {"query_player": too_slow}
    plan = [ToolCall(name="query_player", args={"name": "X"})]
    state: AgentState = {**initial_state("q"), "plan": plan}

    update = await tool_executor_node(state, tools=tools)

    assert "timed out" in update["gathered_data"]["query_player(name=X)"]["error"]


@pytest.mark.asyncio
async def test_tool_executor_handles_empty_plan() -> None:
    update = await tool_executor_node(initial_state("q"), tools={})
    assert update == {"gathered_data": {}}


# ============================================================================
# reflector_node
# ============================================================================
@pytest.mark.asyncio
async def test_reflector_says_done_when_sufficient() -> None:
    payload = {"sufficient": True, "missing": None, "reasoning": "Enough data."}
    response = _tool_use_response("record_reflection", payload)
    client = _mock_client(response)

    update = await reflector_node(initial_state("q"), client=client)

    assert update["should_continue"] is False
    assert update["iteration_count"] == 1


@pytest.mark.asyncio
async def test_reflector_says_continue_when_insufficient() -> None:
    payload = {"sufficient": False, "missing": "Salah form", "reasoning": "Need more."}
    response = _tool_use_response("record_reflection", payload)
    client = _mock_client(response)

    update = await reflector_node(initial_state("q"), client=client)

    assert update["should_continue"] is True


@pytest.mark.asyncio
async def test_reflector_hard_caps_at_max_iterations_without_calling_llm() -> None:
    client = _mock_client(_tool_use_response("record_reflection", {}))
    state: AgentState = {**initial_state("q"), "iteration_count": MAX_ITERATIONS - 1}

    update = await reflector_node(state, client=client)

    assert update["should_continue"] is False
    assert update["iteration_count"] == MAX_ITERATIONS
    client.messages.create.assert_not_awaited()  # LLM skipped at the cap


@pytest.mark.asyncio
async def test_reflector_increments_iteration_count() -> None:
    payload = {"sufficient": True, "missing": None, "reasoning": ""}
    client = _mock_client(_tool_use_response("record_reflection", payload))
    state: AgentState = {**initial_state("q"), "iteration_count": 1}

    update = await reflector_node(state, client=client)

    assert update["iteration_count"] == 2


# ============================================================================
# recommender_node
# ============================================================================
@pytest.mark.asyncio
async def test_recommender_produces_valid_scout_report() -> None:
    response = _tool_use_response("record_scout_report", _valid_scout_report_payload())
    client = _mock_client(response)

    update = await recommender_node(initial_state("Is Salah worth it?"), client=client)

    report = update["final_response"]
    assert report.question == "Is Salah worth it?"
    assert report.players[0].player_name == "Salah"


@pytest.mark.asyncio
async def test_recommender_semantic_failure_short_circuits_via_error() -> None:
    # Missing required `recommendation` field — Pydantic will raise
    broken_payload = {
        "question": "q",
        "analysis": "x",
        "players": [],
        "comparison": None,
        "caveats": [],
        "data_sources": [],
    }
    response = _tool_use_response("record_scout_report", broken_payload)
    client = _mock_client(response)

    update = await recommender_node(initial_state("q"), client=client)

    assert "final_response" not in update
    assert "recommender failed" in update["error"]


# ============================================================================
# route_after_reflector
# ============================================================================
def test_route_after_reflector_continue() -> None:
    assert route_after_reflector({"should_continue": True}) == "continue"


def test_route_after_reflector_done() -> None:
    assert route_after_reflector({"should_continue": False}) == "done"


def test_route_after_reflector_short_circuits_on_error() -> None:
    assert route_after_reflector({"should_continue": True, "error": "boom"}) == "done"


# ============================================================================
# tool_executor: duplicate tool calls in one plan produce distinct entries
# ============================================================================
@pytest.mark.asyncio
async def test_tool_executor_keys_duplicate_calls_by_args() -> None:
    """A plan with two ``query_player`` calls for different names must produce
    two entries in ``gathered_data`` — comparison questions are a first-class
    use case per ADR-0009."""

    async def fake_query(name: str) -> dict[str, Any]:
        return {"name_echo": name}

    plan = [
        ToolCall(name="query_player", args={"name": "Salah"}),
        ToolCall(name="query_player", args={"name": "Palmer"}),
    ]
    state: AgentState = {**initial_state("compare"), "plan": plan}

    update = await tool_executor_node(state, tools={"query_player": fake_query})

    assert set(update["gathered_data"].keys()) == {
        "query_player(name=Salah)",
        "query_player(name=Palmer)",
    }
    assert update["gathered_data"]["query_player(name=Salah)"]["name_echo"] == "Salah"
    assert update["gathered_data"]["query_player(name=Palmer)"]["name_echo"] == "Palmer"


@pytest.mark.asyncio
async def test_tool_executor_no_args_key_is_just_name() -> None:
    async def fake(**_: Any) -> dict[str, Any]:
        return {"ok": True}

    plan = [ToolCall(name="query_players_by_criteria", args={})]
    state: AgentState = {**initial_state("q"), "plan": plan}

    update = await tool_executor_node(state, tools={"query_players_by_criteria": fake})

    assert set(update["gathered_data"].keys()) == {"query_players_by_criteria"}


# ============================================================================
# recommender: short-circuits on state["error"]
# ============================================================================
@pytest.mark.asyncio
async def test_recommender_short_circuits_when_state_has_error() -> None:
    client = _mock_client(_tool_use_response("record_scout_report", _valid_scout_report_payload()))
    state: AgentState = {**initial_state("Is Salah worth it?"), "error": "planner failed: boom"}

    update = await recommender_node(state, client=client)

    # No LLM call — saves Sonnet cost on every failure path
    client.messages.create.assert_not_awaited()
    report = update["final_response"]
    assert report.question == "Is Salah worth it?"
    assert "boom" in report.recommendation
    assert report.caveats  # error is flagged for the UI


# ============================================================================
# stop_reason logging
# ============================================================================
@pytest.mark.asyncio
async def test_log_usage_warns_on_max_tokens_truncation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = {"plan": [{"name": "query_player", "args": {"name": "Salah"}}]}
    response = _tool_use_response("record_plan", payload)
    response.stop_reason = "max_tokens"
    client = _mock_client(response)

    with caplog.at_level(logging.INFO, logger="fpl_agent.graph.nodes"):
        await planner_node(initial_state("q"), client=client)

    messages = "\n".join(r.message for r in caplog.records)
    assert "stop_reason=max_tokens" in messages
    assert any(
        "hit max_tokens" in r.message and r.levelno == logging.WARNING for r in caplog.records
    )


# ============================================================================
# user_squad: planner prompt gating + executor short-circuit
# ============================================================================
def _fake_squad():
    """A minimal valid UserSquad for tests that need one."""
    from fpl_agent.models.responses import SquadPick, UserSquad

    picks = [
        SquadPick(
            element_id=430,
            web_name="Haaland",
            team_name="Man City",
            position=1,
            element_type=4,
            multiplier=2,
            is_captain=True,
            is_vice_captain=False,
            price=14.2,
        ),
    ]
    return UserSquad(
        team_id=12345,
        gameweek=33,
        picks=picks,
        bank=2.5,
        total_value=100.5,
        active_chip=None,
        overall_rank=500_000,
        total_points=1500,
    )


@pytest.mark.asyncio
async def test_planner_prompt_includes_squad_summary_when_loaded() -> None:
    """Squad metadata flows into the planner prompt so the LLM knows not to fetch."""
    payload = {"plan": []}
    client = _mock_client(_tool_use_response("record_plan", payload))
    state: AgentState = {**initial_state("Who should I captain?", squad=_fake_squad())}

    await planner_node(state, client=client)

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "captain=Haaland" in prompt
    assert "Do **not** call `fetch_user_squad`" in prompt


@pytest.mark.asyncio
async def test_planner_prompt_says_squad_unavailable_when_absent() -> None:
    payload = {"plan": []}
    client = _mock_client(_tool_use_response("record_plan", payload))

    await planner_node(initial_state("Who should I captain?"), client=client)

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "No user squad has been loaded" in prompt


@pytest.mark.asyncio
async def test_tool_executor_short_circuits_fetch_user_squad_when_cached() -> None:
    """If state has user_squad, fetch_user_squad must NOT call the underlying tool."""
    underlying_fetcher = AsyncMock()
    tools = {"fetch_user_squad": underlying_fetcher}
    plan = [ToolCall(name="fetch_user_squad", args={"team_id": 1, "gameweek": 33})]
    state: AgentState = {
        **initial_state("q", squad=_fake_squad()),
        "plan": plan,
    }

    update = await tool_executor_node(state, tools=tools)

    underlying_fetcher.assert_not_awaited()
    # The cached squad is what gets handed to the recommender.
    key = "fetch_user_squad(gameweek=33,team_id=1)"
    assert update["gathered_data"][key]["team_id"] == 12345
    assert update["gathered_data"][key]["picks"][0]["web_name"] == "Haaland"


@pytest.mark.asyncio
async def test_tool_executor_calls_fetch_user_squad_when_no_cache() -> None:
    """Without a cached squad, the executor must invoke the underlying tool."""
    raw_squad = {"picks": [{"element": 1}], "bank": 0}
    underlying_fetcher = AsyncMock(return_value=raw_squad)
    tools = {"fetch_user_squad": underlying_fetcher}
    plan = [ToolCall(name="fetch_user_squad", args={"team_id": 1, "gameweek": 33})]
    state: AgentState = {**initial_state("q"), "plan": plan}

    update = await tool_executor_node(state, tools=tools)

    underlying_fetcher.assert_awaited_once_with(team_id=1, gameweek=33)
    key = "fetch_user_squad(gameweek=33,team_id=1)"
    assert update["gathered_data"][key] == raw_squad
