"""LangGraph state definition for the scout report agent.

LangGraph state flows through the graph as a TypedDict. Each node returns a
partial dict; LangGraph merges it into the running state via per-field
reducers. See [ADR-0009](../../../../../docs/adr/0009-scout-report-agent-architecture.md).

Reducers declared here:
- ``tool_calls_made`` uses ``operator.add`` so each iteration's calls append.
- ``gathered_data`` uses :func:`merge_dicts` so later-iteration keys add to
  earlier ones rather than replacing them.
- Everything else uses the default overwrite reducer.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field

# Tool names are constrained to the 6 implemented tools. Using ``Literal``
# here means the planner's output is validated by Pydantic the moment it
# comes back — no chance of the planner hallucinating "search_players".
ToolName = Literal[
    "query_player",
    "search_similar_players",
    "query_players_by_criteria",
    "get_fixture_outlook",
    "get_injury_signals",
    "fetch_user_squad",
]


class ToolCall(BaseModel):
    """A single tool invocation requested by the planner."""

    name: ToolName
    args: dict[str, Any] = Field(default_factory=dict)


def merge_dicts(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Reducer that merges ``new`` into ``old`` (later keys win on conflict).

    Used for ``gathered_data`` so tool results from iteration 2 are added
    to iteration 1's results rather than replacing the whole dict.
    """
    return {**old, **new}


class AgentState(TypedDict, total=False):
    """State passed between nodes in the agent graph.

    ``total=False`` so partial state dicts are valid during graph execution —
    nodes only need to populate the fields they actually change.
    """

    question: str
    user_squad: dict[str, Any] | None
    plan: list[ToolCall]
    gathered_data: Annotated[dict[str, Any], merge_dicts]
    tool_calls_made: Annotated[list[str], operator.add]
    iteration_count: int
    should_continue: bool
    final_response: Any  # ScoutReport; typed ``Any`` to avoid a circular import
    error: str | None


def initial_state(question: str) -> AgentState:
    """Build a fresh state with all fields populated to their zero values.

    LangGraph tolerates missing keys, but passing a complete dict makes
    debugging easier — you can diff the starting state against the final
    state and see exactly what each node contributed.
    """
    return {
        "question": question,
        "user_squad": None,
        "plan": [],
        "gathered_data": {},
        "tool_calls_made": [],
        "iteration_count": 0,
        "should_continue": False,
        "final_response": None,
        "error": None,
    }
