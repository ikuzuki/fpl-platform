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

from fpl_agent.models.responses import UserSquad

# Tool names are constrained to the 5 implemented tools. Using ``Literal``
# here means the planner's output is validated by Pydantic the moment it
# comes back — no chance of the planner hallucinating "search_players".
#
# Squad loading is deliberately *not* a tool — it's an HTTP-layer concern.
# The dashboard calls ``GET /team`` and echoes the resulting ``UserSquad``
# back on every chat turn; the agent reads it from ``state["user_squad"]``.
# Letting the agent dispatch a cross-service Lambda invoke at planning time
# would require it to invent a ``team_id`` it has no source of truth for.
ToolName = Literal[
    "query_player",
    "search_similar_players",
    "query_players_by_criteria",
    "get_fixture_outlook",
    "get_injury_signals",
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

    ``user_squad`` is *input context* — seeded from the API request when the
    dashboard pre-loaded a squad via ``GET /team``. It deliberately lives on
    its own field rather than inside ``gathered_data`` so the quality-score
    ``tool_success_rate`` reflects only real tool calls, and so the planner
    + executor can read it from a single, typed source.
    """

    question: str
    user_squad: UserSquad | None
    plan: list[ToolCall]
    gathered_data: Annotated[dict[str, Any], merge_dicts]
    tool_calls_made: Annotated[list[str], operator.add]
    llm_usage: Annotated[list[dict[str, Any]], operator.add]
    iteration_count: int
    should_continue: bool
    final_response: Any  # ScoutReport; typed ``Any`` to avoid a circular import
    error: str | None


def initial_state(question: str, squad: UserSquad | None = None) -> AgentState:
    """Build a fresh state with all fields populated to their zero values.

    LangGraph tolerates missing keys, but passing a complete dict makes
    debugging easier — you can diff the starting state against the final
    state and see exactly what each node contributed.

    Args:
        question: The user's chat question.
        squad: Optional pre-loaded user squad. When provided, the planner sees
            it in the prompt and the executor short-circuits ``fetch_user_squad``.
    """
    return {
        "question": question,
        "user_squad": squad,
        "plan": [],
        "gathered_data": {},
        "tool_calls_made": [],
        "llm_usage": [],
        "iteration_count": 0,
        "should_continue": False,
        "final_response": None,
        "error": None,
    }
