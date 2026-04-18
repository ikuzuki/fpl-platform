"""Assemble the scout report agent's :class:`StateGraph`.

The graph has four nodes and one conditional edge:

.. code-block:: text

    START → planner → tool_executor → reflector ──continue──┐
                        ↑                                    │
                        └────────────────────────────────────┘
                                     │
                                     └──done──→ recommender → END

Dependencies (Anthropic client, tool registry) are injected into the nodes
via :func:`functools.partial` so LangGraph sees a one-arg callable per node.
This keeps the nodes themselves free of module-level state, which makes
them trivial to unit-test — the test harness constructs mocks and passes
them in directly.
"""

from __future__ import annotations

from functools import partial

from anthropic import AsyncAnthropic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from fpl_agent.graph.nodes import (
    planner_node,
    recommender_node,
    reflector_node,
    route_after_reflector,
    tool_executor_node,
)
from fpl_agent.models.state import AgentState
from fpl_agent.tools.player_tools import ToolFn


def build_agent_graph(
    *,
    client: AsyncAnthropic,
    tools: dict[str, ToolFn],
) -> CompiledStateGraph:
    """Build and compile the scout report agent graph.

    Args:
        client: Shared async Anthropic client (one per Lambda cold start).
        tools: Tool registry from :func:`fpl_agent.tools.make_tools`.
    """
    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("planner", partial(planner_node, client=client))
    graph.add_node("tool_executor", partial(tool_executor_node, tools=tools))
    graph.add_node("reflector", partial(reflector_node, client=client))
    graph.add_node("recommender", partial(recommender_node, client=client))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "tool_executor")
    graph.add_edge("tool_executor", "reflector")
    graph.add_conditional_edges(
        "reflector",
        route_after_reflector,
        {"continue": "planner", "done": "recommender"},
    )
    graph.add_edge("recommender", END)

    return graph.compile()
