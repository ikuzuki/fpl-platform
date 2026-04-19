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

from pydantic import BaseModel, ConfigDict, Field

FixtureOutlook = Literal["green", "amber", "red"]


# ``extra='forbid'`` makes every generated JSON Schema include
# ``additionalProperties: false``. Anthropic's tool-use decoder respects
# that, so the LLM cannot emit unknown fields — any schema drift becomes a
# Pydantic ValidationError at the node boundary instead of a silent typo
# that survives to the client.
_STRICT_CONFIG = ConfigDict(extra="forbid")


class PlayerAnalysis(BaseModel):
    """Per-player verdict that appears inside a ScoutReport."""

    model_config = _STRICT_CONFIG

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

    model_config = _STRICT_CONFIG

    players: list[PlayerAnalysis]
    winner: str | None = Field(
        default=None,
        description="Name of the preferred player, or None if it's genuinely too close to call",
    )
    reasoning: str


class ScoutReport(BaseModel):
    """The agent's final structured answer to a user's question."""

    model_config = _STRICT_CONFIG

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

    model_config = _STRICT_CONFIG

    sufficient: bool = Field(description="True if gathered data is enough to answer the question")
    missing: str | None = Field(
        default=None,
        description="If not sufficient, a short description of what the planner should fetch next",
    )
    reasoning: str


class AgentResponse(BaseModel):
    """Thin envelope returned by the API handler — wraps the ScoutReport
    with execution metadata the frontend can surface for transparency."""

    model_config = _STRICT_CONFIG

    report: ScoutReport
    iterations_used: int
    tool_calls_made: list[str]


# ---------------------------------------------------------------------------
# User squad — enriched picks served by GET /team and echoed back by POST /chat
# ---------------------------------------------------------------------------
# The team-fetcher Lambda returns FPL's raw shape: `picks` carry `element` IDs
# only, no names. The dashboard needs names for the squad card and the agent's
# recommender already speaks names, not IDs. So `/team` joins the FPL response
# against Neon `player_embeddings` and serves the enriched form below.
#
# Money fields (price, bank, total_value) are in pounds millions — the FPL API
# uses tenths-of-millions on the wire, but storing the friendlier float here
# means the frontend renders without a divisor and the recommender prompt
# reads naturally ("£8.5m" not "85").


class SquadPick(BaseModel):
    """One of the 15 entries in a manager's squad for a gameweek."""

    model_config = _STRICT_CONFIG

    element_id: int = Field(description="FPL player ID (the bootstrap-static `element`)")
    web_name: str
    team_name: str
    position: int = Field(description="1-15 squad slot; 1-11 are starters, 12-15 bench")
    element_type: int = Field(description="FPL position code: 1=GK, 2=DEF, 3=MID, 4=FWD")
    multiplier: int = Field(description="0=bench, 1=starting, 2=captain, 3=triple captain")
    is_captain: bool
    is_vice_captain: bool
    price: float = Field(description="Player price in £m at the time of the snapshot")


class UserSquad(BaseModel):
    """A user's enriched FPL squad for one gameweek, ready for both UI + agent."""

    model_config = _STRICT_CONFIG

    team_id: int
    gameweek: int
    picks: list[SquadPick]
    bank: float = Field(description="Cash in the bank in £m")
    total_value: float = Field(description="Squad market value in £m (excluding bank)")
    active_chip: str | None = Field(
        default=None,
        description="Active chip code (`wildcard`, `freehit`, `bboost`, `3xc`) or null",
    )
    overall_rank: int | None = None
    total_points: int
