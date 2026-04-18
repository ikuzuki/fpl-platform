"""Pydantic v2 response models — the structured output the agent produces.

These models are used two ways:

1. **Validation** — after the recommender LLM call, its JSON output is
   parsed into :class:`ScoutReport`. Invalid outputs short-circuit the graph.
2. **Tool-use schema** — ``ScoutReport.model_json_schema()`` is passed to
   Anthropic as the ``input_schema`` of a forced tool call, so the model is
   server-side-constrained to produce matching JSON. No prompt needs to ship
   the schema; Pydantic is the single source of truth.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FixtureOutlook = Literal["green", "amber", "red"]


class PlayerAnalysis(BaseModel):
    """Per-player verdict that appears inside a ScoutReport."""

    player_name: str
    position: str = Field(description="GKP / DEF / MID / FWD")
    price: float = Field(description="Current FPL price in £m")
    form: float = Field(description="FPL form value (points per match, recent window)")
    fixture_outlook: FixtureOutlook = Field(
        description="green = favourable fixtures, amber = mixed, red = difficult"
    )
    verdict: str = Field(description="1-2 sentence analytical verdict")
    confidence: float = Field(ge=0.0, le=1.0)


class ComparisonResult(BaseModel):
    """Head-to-head comparison when the question asks to compare players."""

    players: list[PlayerAnalysis]
    winner: str | None = Field(
        default=None,
        description="Name of the preferred player, or None if it's genuinely too close to call",
    )
    reasoning: str


class ScoutReport(BaseModel):
    """The agent's final structured answer to a user's question."""

    question: str
    analysis: str = Field(description="The core analytical narrative (3-6 sentences)")
    players: list[PlayerAnalysis] = Field(default_factory=list)
    comparison: ComparisonResult | None = None
    recommendation: str = Field(description="Concrete, actionable takeaway for the user")
    caveats: list[str] = Field(
        default_factory=list,
        description="Limitations, missing data, or assumptions worth flagging",
    )
    data_sources: list[str] = Field(
        default_factory=list,
        description="Tool names the recommender drew on, e.g. 'query_player', 'search_similar_players'",
    )


class ReflectionResult(BaseModel):
    """Output of the reflector node — gates the loop-back edge."""

    sufficient: bool = Field(description="True if gathered data is enough to answer the question")
    missing: str | None = Field(
        default=None,
        description="If not sufficient, a short description of what the planner should fetch next",
    )
    reasoning: str


class AgentResponse(BaseModel):
    """Thin envelope returned by the API handler — wraps the ScoutReport
    with execution metadata the frontend can surface for transparency."""

    report: ScoutReport
    iterations_used: int
    tool_calls_made: list[str]
