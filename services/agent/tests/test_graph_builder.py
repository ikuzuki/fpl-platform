"""Unit tests for the agent graph builder."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from fpl_agent.graph.builder import build_agent_graph
from fpl_agent.models.state import initial_state

pytestmark = pytest.mark.unit


def _tool_use_response(tool_name: str, input_payload: dict[str, Any]) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = input_payload
    response = MagicMock()
    response.content = [block]
    response.usage = MagicMock(input_tokens=50, output_tokens=25)
    return response


def _valid_report() -> dict[str, Any]:
    return {
        "question": "Is Salah worth it?",
        "analysis": "Salah is a premium pick; 180 points, 13.5m.",
        "players": [],
        "comparison": None,
        "recommendation": "Keep Salah.",
        "caveats": [],
        "data_sources": ["query_player"],
    }


def test_graph_compiles_with_client_and_tools() -> None:
    client = MagicMock()
    tools: dict[str, Any] = {}
    graph = build_agent_graph(client=client, tools=tools)
    assert graph is not None


def test_graph_has_expected_nodes() -> None:
    graph = build_agent_graph(client=MagicMock(), tools={})
    node_ids = set(graph.get_graph().nodes.keys())
    assert {"planner", "tool_executor", "reflector", "recommender"}.issubset(node_ids)


@pytest.mark.asyncio
async def test_graph_invoke_end_to_end_with_mocks() -> None:
    """Drive the whole graph with mocked LLM + one mocked tool.

    This exercises the real builder + real nodes — only the Anthropic client
    and the tool registry are mocked. Proves the conditional edge wires up
    correctly and that state flows through all four nodes.
    """
    # Script the LLM responses in the order they'll be called:
    #   1. planner  → plan with one tool call
    #   2. reflector → sufficient=True (so we skip the loop)
    #   3. recommender → valid scout report
    planner_response = _tool_use_response(
        "record_plan",
        {"plan": [{"name": "query_player", "args": {"name": "Salah"}}]},
    )
    reflector_response = _tool_use_response(
        "record_reflection",
        {"sufficient": True, "missing": None, "reasoning": "Got everything."},
    )
    recommender_response = _tool_use_response("record_scout_report", _valid_report())

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(
        side_effect=[planner_response, reflector_response, recommender_response]
    )

    async def fake_query_player(**_: Any) -> dict[str, Any]:
        return {"web_name": "Salah", "total_points": 180}

    tools = {"query_player": fake_query_player}
    graph = build_agent_graph(client=client, tools=tools)

    final_state = await graph.ainvoke(initial_state("Is Salah worth it?"))

    assert final_state["final_response"].recommendation == "Keep Salah."
    assert final_state["gathered_data"]["query_player(name=Salah)"]["web_name"] == "Salah"
    assert "query_player" in final_state["tool_calls_made"]
    # 3 LLM calls: planner, reflector, recommender
    assert client.messages.create.await_count == 3


@pytest.mark.asyncio
async def test_graph_loops_when_reflector_says_continue() -> None:
    """Verify the conditional edge loops back when the reflector is not satisfied."""
    plan_call_1 = _tool_use_response(
        "record_plan",
        {"plan": [{"name": "query_player", "args": {"name": "Salah"}}]},
    )
    reflect_continue = _tool_use_response(
        "record_reflection",
        {"sufficient": False, "missing": "fixture", "reasoning": "Need more."},
    )
    plan_call_2 = _tool_use_response(
        "record_plan",
        {"plan": [{"name": "get_fixture_outlook", "args": {"player_name": "Salah"}}]},
    )
    reflect_done = _tool_use_response(
        "record_reflection",
        {"sufficient": True, "missing": None, "reasoning": "Enough."},
    )
    recommend = _tool_use_response("record_scout_report", _valid_report())

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(
        side_effect=[plan_call_1, reflect_continue, plan_call_2, reflect_done, recommend]
    )

    async def fake_query_player(**_: Any) -> dict[str, Any]:
        return {"web_name": "Salah"}

    async def fake_fixture(**_: Any) -> dict[str, Any]:
        return {"difficulty": 2.5}

    tools = {"query_player": fake_query_player, "get_fixture_outlook": fake_fixture}
    graph = build_agent_graph(client=client, tools=tools)

    final_state = await graph.ainvoke(initial_state("Salah fixture outlook?"))

    assert final_state["iteration_count"] == 2
    assert set(final_state["gathered_data"].keys()) == {
        "query_player(name=Salah)",
        "get_fixture_outlook(player_name=Salah)",
    }
    assert final_state["tool_calls_made"] == ["query_player", "get_fixture_outlook"]
    # 5 LLM calls: planner x2, reflector x2, recommender x1
    assert client.messages.create.await_count == 5
