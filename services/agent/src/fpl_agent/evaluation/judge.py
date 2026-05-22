"""Haiku-backed judge for the eval framework.

Reads the agent's :class:`ScoutReport`, the original question, the (optional)
:class:`UserSquad`, and the case's rubric bullets, and asks Claude Haiku to
score each bullet 1–5. Returns a :class:`JudgeVerdict`.

Why Haiku, not Sonnet:

* The judge task is structured marking against an explicit rubric — the kind
  of pattern Haiku handles competently at 1/3 the cost.
* A full eval run is 29 cases × one judge call ≈ ~$0.10 on Haiku. The same
  on Sonnet would push past $1 per run without a meaningful quality bump,
  given the rubric carries most of the semantics.

The judge follows the same patterns as the production graph nodes:

* Tool-use with a forced ``tool_choice`` to get structured output. The
  ``input_schema`` is derived from :class:`JudgeVerdict` so Pydantic remains
  the single source of truth — schema changes propagate automatically.
* Pydantic validation on the parsed result. Malformed verdicts surface as
  :class:`JudgeError` for the evaluator to record.
* ``@observe`` for Langfuse tracing + :func:`record_llm_usage` for token
  counts. Every eval run shows up in Langfuse with the same telemetry shape
  as a real agent invocation.

Prompt caching is not enabled at the call level — matches the existing
graph nodes' pattern. Opt-in (``cache_control``) is a cross-codebase
concern; deferring until the cost actually bites.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib.resources import files
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import ValidationError

from fpl_agent.evaluation.eval_cases import EvalCase
from fpl_agent.evaluation.evaluator import JudgeFn
from fpl_agent.evaluation.models import JudgeVerdict
from fpl_agent.models.responses import ScoutReport, UserSquad
from fpl_lib.observability import observe, record_llm_usage

logger = logging.getLogger(__name__)

# Haiku — same tier as PLANNER_MODEL and REFLECTOR_MODEL. Cheap, fast,
# competent at structured rubric scoring.
JUDGE_MODEL = "claude-haiku-4-5"

# 2048 tokens comfortably fits up to ~6 BulletScore entries with reasoning
# plus the overall + holistic comment. Bump if rubrics grow.
JUDGE_MAX_TOKENS = 2048


class JudgeError(RuntimeError):
    """Raised when the judge fails to produce a usable verdict.

    Distinguished from generic exceptions so the evaluator's catch-all
    handler can identify judge-specific failures in summary diagnostics.
    """


# ---------------------------------------------------------------------------
# Tool-use schema
# ---------------------------------------------------------------------------
# Derived from the Pydantic model rather than hand-written — same pattern as
# the production graph nodes. Any change to JudgeVerdict's fields propagates
# to the model's output constraints without a separate schema edit.

_JUDGE_TOOL = {
    "name": "record_judge_verdict",
    "description": "Record the per-bullet scores and overall verdict for this case.",
    "input_schema": JudgeVerdict.model_json_schema(),
}


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _load_judge_prompt() -> str:
    """Read ``prompts/v1/judge.md`` via importlib.resources.

    Matches :func:`fpl_agent.graph.nodes._load_prompt`'s loader so the prompt
    resolves identically whether installed as a wheel, editable, or run from
    source. ``setuptools.package-data`` in ``pyproject.toml`` ships the .md
    into the wheel.
    """
    return (files("fpl_agent.evaluation.prompts.v1") / "judge.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Prompt-rendering helpers
# ---------------------------------------------------------------------------


def _render_squad_for_judge(squad: UserSquad | None) -> str:
    """Compact UserSquad summary for the judge prompt.

    The judge needs the squad to verify squad-anchored rubric bullets (e.g.
    "Captain pick is one of the user's actual starters"). A compact text
    form beats raw JSON — easier for Haiku to scan, smaller token count.
    """
    if squad is None:
        return "No squad loaded. Squad-anchored rubric bullets don't apply to this case."

    starters = [p for p in squad.picks if p.position <= 11]
    bench = [p for p in squad.picks if p.position > 11]
    captain = next((p for p in squad.picks if p.is_captain), None)
    vice = next((p for p in squad.picks if p.is_vice_captain), None)

    return (
        f"Loaded for GW{squad.gameweek} (team_id={squad.team_id}):\n"
        f"- Starters ({len(starters)}): {[p.web_name for p in starters]}\n"
        f"- Bench ({len(bench)}): {[p.web_name for p in bench]}\n"
        f"- Captain: {captain.web_name if captain else '(none)'}\n"
        f"- Vice-captain: {vice.web_name if vice else '(none)'}\n"
        f"- Bank: £{squad.bank:.1f}m | Total value: £{squad.total_value:.1f}m | "
        f"Chip: {squad.active_chip or 'none'}"
    )


def _format_rubric(bullets: tuple[str, ...]) -> str:
    """Number the rubric bullets so the judge can match BulletScores 1-to-1."""
    return "\n".join(f"{i}. {bullet}" for i, bullet in enumerate(bullets, start=1))


# ---------------------------------------------------------------------------
# Judge call
# ---------------------------------------------------------------------------


def _extract_tool_input(response: Any, expected_name: str) -> dict[str, Any]:
    """Pull the first ``tool_use`` content block matching ``expected_name``.

    Mirrors :func:`fpl_agent.graph.nodes._extract_tool_input` — keeping the
    helper local rather than reaching into ``graph.nodes`` avoids coupling
    the eval framework to the production graph internals.
    """
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == expected_name:
            return dict(block.input)
    raise JudgeError(f"Anthropic response did not contain a '{expected_name}' tool_use block")


@observe(name="eval.judge", as_type="generation")
async def judge_case(
    case: EvalCase,
    report: ScoutReport,
    client: AsyncAnthropic,
    user_squad: UserSquad | None = None,
    *,
    model: str = JUDGE_MODEL,
) -> JudgeVerdict:
    """Score one case's agent response against its rubric.

    Raises:
        JudgeError: if the API call fails, the response is malformed, the
            verdict doesn't validate against :class:`JudgeVerdict`, or the
            bullet count doesn't match the rubric. The caller (typically
            :class:`AgentEvaluator`) catches this and records the failure
            without poisoning the hard-check pass rate.
    """
    prompt = _load_judge_prompt().format(
        question=case.question,
        user_squad_block=_render_squad_for_judge(user_squad),
        scout_report_json=report.model_dump_json(indent=2),
        rubric_bullets=_format_rubric(case.judge_rubric),
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=JUDGE_MAX_TOKENS,
            tools=[_JUDGE_TOOL],
            tool_choice={"type": "tool", "name": "record_judge_verdict"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — Anthropic SDK exceptions vary
        raise JudgeError(f"Anthropic call failed for case {case.id}: {exc}") from exc

    # Log token usage to CloudWatch + Langfuse before parsing — even a
    # malformed response cost real money, and the eval baseline doc needs
    # accurate per-run cost figures.
    usage = getattr(response, "usage", None)
    stop_reason = getattr(response, "stop_reason", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
    logger.info(
        "llm_usage node=eval.judge case=%s model=%s stop_reason=%s input_tokens=%s output_tokens=%s",
        case.id,
        model,
        stop_reason,
        input_tokens,
        output_tokens,
    )
    if stop_reason == "max_tokens":
        logger.warning("judge hit max_tokens on case %s — verdict likely truncated", case.id)
    record_llm_usage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        stop_reason=stop_reason,
        metadata={"node": "eval.judge", "case_id": case.id},
    )

    try:
        raw = _extract_tool_input(response, "record_judge_verdict")
        verdict = JudgeVerdict.model_validate(raw)
    except (ValidationError, JudgeError) as exc:
        raise JudgeError(f"Judge produced invalid verdict for case {case.id}: {exc}") from exc

    # Hard contract: one BulletScore per rubric bullet, in order. If the
    # model drifted, the verdict isn't trustworthy — fail loud rather than
    # silently partial-grading.
    expected = len(case.judge_rubric)
    actual = len(verdict.bullet_scores)
    if actual != expected:
        raise JudgeError(
            f"Judge returned {actual} bullet scores for case {case.id}, expected "
            f"{expected}. Verdict cannot be aligned with the rubric."
        )

    # Sanity-check the model's `overall` against the bullet mean. Drift
    # beyond 0.5 suggests the model's holistic score disagrees with its
    # own per-bullet scores — log but don't fail, since the bullet scores
    # are the authoritative signal.
    bullet_mean = sum(b.score for b in verdict.bullet_scores) / actual
    if abs(verdict.overall - bullet_mean) > 0.5:
        logger.warning(
            "Judge overall=%.2f drifts from bullet mean=%.2f on case %s",
            verdict.overall,
            bullet_mean,
            case.id,
        )

    return verdict


# ---------------------------------------------------------------------------
# Factory — produces a JudgeFn for AgentEvaluator
# ---------------------------------------------------------------------------


def make_judge(client: AsyncAnthropic, *, model: str = JUDGE_MODEL) -> JudgeFn:
    """Return a :data:`JudgeFn` closure capturing the client + model.

    The evaluator's ``judge`` parameter expects the
    ``(case, report, user_squad) -> JudgeVerdict`` shape; this factory
    binds the Anthropic client into a closure of that shape, so callers
    don't need to wire client/model in three places.
    """

    async def _judge(
        case: EvalCase,
        report: ScoutReport,
        user_squad: UserSquad | None,
    ) -> JudgeVerdict:
        return await judge_case(case, report, client, user_squad, model=model)

    return _judge


__all__ = [
    "JUDGE_MAX_TOKENS",
    "JUDGE_MODEL",
    "JudgeError",
    "judge_case",
    "make_judge",
]
