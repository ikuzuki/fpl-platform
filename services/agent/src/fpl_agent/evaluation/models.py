"""Result types for the eval framework.

These are kept separate from :mod:`fpl_agent.evaluation.evaluator` so the
CLI (and downstream baseline-doc generator) can deserialise eval JSON
without pulling in Anthropic, LangGraph, or pandas.

Two grading layers feed into :class:`EvalResult`:

* **Hard checks** (deterministic, no LLM). Each check produces a
  :class:`HardCheckResult` with a human-readable reason and optional
  structured details. ``EvalResult.passed`` is the conjunction of every
  hard check on the case.
* **Judge verdict** (Haiku, task #3). One :class:`BulletScore` per rubric
  bullet plus an overall mean. Always populated when the judge is wired in;
  ``None`` while task #2 ships hard-checks-only.

:class:`EvalSummary` is the file-level aggregate the CLI writes out and the
baseline doc reads back. It carries the snapshot version + eval-cases
version so a saved JSON tells you which fixture and which case set it was
produced against — critical when you're comparing runs across snapshot
regenerations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from fpl_agent.models.responses import ScoutReport

_STRICT_CONFIG = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Hard-check layer
# ---------------------------------------------------------------------------


class HardCheckResult(BaseModel):
    """Outcome of one deterministic check on a case's agent response."""

    model_config = _STRICT_CONFIG

    check_name: str = Field(
        description="Identifier matching the case field driving the check, e.g. "
        "'expected_tools', 'must_mention_players', 'must_set_comparison'.",
    )
    passed: bool
    reason: str = Field(
        description="Human-readable diagnosis. On failure, names what was expected vs. "
        "what was found. On pass, a one-line confirmation."
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured information for failure analysis — e.g. "
        "{'expected': [...], 'called': [...], 'missing': [...]}.",
    )


# ---------------------------------------------------------------------------
# Judge layer
# ---------------------------------------------------------------------------


class BulletScore(BaseModel):
    """Haiku's score on one rubric bullet for a single case."""

    model_config = _STRICT_CONFIG

    bullet: str = Field(description="Verbatim rubric bullet text the judge scored.")
    score: int = Field(ge=1, le=5, description="Per-bullet score 1 (fails badly) to 5 (clearly meets).")
    reasoning: str = Field(description="Why the judge picked this score — one or two sentences.")


class JudgeVerdict(BaseModel):
    """Aggregate of a Haiku judging pass across all rubric bullets for a case."""

    model_config = _STRICT_CONFIG

    bullet_scores: list[BulletScore]
    overall: float = Field(
        ge=1.0,
        le=5.0,
        description="Arithmetic mean of bullet scores. Stored to avoid recomputing during "
        "aggregation and to keep the field stable across schema changes.",
    )
    reasoning: str = Field(
        description="Holistic comment on the response — what the judge prioritised and any "
        "tensions across the rubric bullets."
    )


# ---------------------------------------------------------------------------
# Per-case result
# ---------------------------------------------------------------------------


class EvalResult(BaseModel):
    """Everything captured from running one :class:`EvalCase` through the agent."""

    model_config = _STRICT_CONFIG

    case_id: str
    passed: bool = Field(description="True iff every hard check passed. Independent of judge score.")
    hard_checks: list[HardCheckResult]
    judge: JudgeVerdict | None = Field(
        default=None,
        description="None when the judge isn't wired in (task #2) or when it errored. "
        "When present, supplements the binary pass/fail with a soft quality signal.",
    )
    agent_report: ScoutReport | None = Field(
        default=None,
        description="The agent's final ScoutReport. None only when the graph itself raised "
        "before producing a recommender output — see `error`.",
    )
    tool_calls_made: list[str] = Field(default_factory=list)
    iterations_used: int = 0
    error: str | None = Field(
        default=None,
        description="Captured if the graph raised. The case is marked failed and execution "
        "continues to the next case — one broken case doesn't kill the run.",
    )
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Run-level aggregate
# ---------------------------------------------------------------------------


class CategoryStats(BaseModel):
    """Aggregate stats sliced by a single dimension (category or difficulty)."""

    model_config = _STRICT_CONFIG

    count: int
    passed: int
    pass_rate: float = Field(ge=0.0, le=1.0)
    mean_judge_score: float | None = Field(
        default=None,
        description="Average overall judge score across cases in this slice. None when no "
        "case in the slice has a judge verdict.",
    )


class EvalSummary(BaseModel):
    """File-level aggregate written by :mod:`scripts.run_evals` and read by the baseline doc.

    Includes version pins so a saved summary is self-describing — a reviewer
    can tell which fixture and which case set produced the numbers without
    needing to run anything.
    """

    model_config = _STRICT_CONFIG

    results: list[EvalResult]
    total: int
    hard_check_passed: int
    hard_check_pass_rate: float = Field(ge=0.0, le=1.0)
    mean_judge_score: float | None = Field(
        default=None,
        description="Mean of `judge.overall` across all cases with a verdict. None pre-task-#3.",
    )
    by_category: dict[str, CategoryStats] = Field(default_factory=dict)
    by_difficulty: dict[str, CategoryStats] = Field(default_factory=dict)
    snapshot_version: str = Field(
        description="Snapshot identity — typically the parquet filename stem (e.g. 'player_db_v1')."
    )
    eval_cases_version: str = Field(
        description="EVAL_CASES_VERSION from eval_cases.py — bumped when the case set changes."
    )
