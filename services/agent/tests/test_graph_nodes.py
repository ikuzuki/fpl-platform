"""Unit tests for agent graph nodes."""

from __future__ import annotations

import asyncio
import logging
import time
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
async def test_planner_rejects_unknown_tool() -> None:
    payload = {"plan": [{"name": "search_for_goats", "args": {}}]}
    response = _tool_use_response("record_plan", payload)
    client = _mock_client(response)
    state = initial_state("Nonsense")

    update = await planner_node(state, client=client)

    # Unknown tool fails Literal validation → planner records error, no plan
    assert "error" in update
    assert "planner failed" in update["error"]


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
    async def slow_tool(**_: Any) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"ok": True}

    tools = {"query_player": slow_tool, "get_fixture_outlook": slow_tool}
    plan = [
        ToolCall(name="query_player", args={"name": "Salah"}),
        ToolCall(name="get_fixture_outlook", args={"player_name": "Salah"}),
    ]
    state: AgentState = {**initial_state("q"), "plan": plan}

    start = time.perf_counter()
    update = await tool_executor_node(state, tools=tools)
    elapsed = time.perf_counter() - start

    # Concurrent: elapsed ≈ max(sleeps) not sum. 0.05s each, so < 0.09s is a safe bound.
    assert elapsed < 0.09
    assert set(update["gathered_data"].keys()) == {"query_player", "get_fixture_outlook"}


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

    assert update["gathered_data"]["query_player"] == {"error": "boom"}
    assert update["gathered_data"]["get_fixture_outlook"] == {"ok": True}


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

    assert "timed out" in update["gathered_data"]["query_player"]["error"]


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
