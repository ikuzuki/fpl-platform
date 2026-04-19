"""Node functions that make up the scout report agent graph.

Four nodes run in sequence (with a conditional loop between reflector and
planner):

* :func:`planner_node` — Haiku. Decides which tools to call.
* :func:`tool_executor_node` — no LLM. Runs the plan concurrently.
* :func:`reflector_node` — Haiku. Decides whether to loop or proceed.
* :func:`recommender_node` — Sonnet. Produces the final ScoutReport.

**Structured output.** Every LLM call uses Anthropic tool-use as the
structured-output mechanism (see walkthrough doc). Each node declares a
fake tool with ``input_schema`` derived from a Pydantic model, forces the
model to invoke it via ``tool_choice``, and reads
``response.content[<tool_use>].input`` as a dict. Server-side schema
enforcement eliminates JSON syntax failures.

**Dependencies.** Nodes receive their Anthropic client (and, for
``tool_executor``, the tool registry) via keyword arguments. The graph
builder in :mod:`fpl_agent.graph.builder` wraps each node with
``functools.partial`` so LangGraph sees a one-arg callable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from importlib.resources import files
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import TypeAdapter, ValidationError

from fpl_agent.graph.config import (
    MAX_ITERATIONS,
    PLANNER_MAX_TOKENS,
    PLANNER_MODEL,
    RECOMMENDER_MAX_TOKENS,
    RECOMMENDER_MODEL,
    REFLECTOR_MAX_TOKENS,
    REFLECTOR_MODEL,
    TOOL_TIMEOUT_SECONDS,
)
from fpl_agent.models.responses import ReflectionResult, ScoutReport, UserSquad
from fpl_agent.models.state import AgentState, ToolCall
from fpl_agent.tools.player_tools import ToolError, ToolFn
from fpl_lib.observability import observe, record_llm_usage

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _load_prompt(name: str) -> str:
    """Read a versioned prompt template.

    Uses ``importlib.resources`` so the lookup works identically whether the
    package is installed as a wheel (Lambda), installed editable (dev), or
    running from source (tests). ``Path(__file__).parent`` would silently
    break under ``pip install`` because setuptools excludes non-Python files
    by default; the wheel's ``package-data`` declaration plus this loader
    keep both paths honest.

    Cached because prompts don't change between calls within a Lambda's life.
    """
    return (files("fpl_agent.graph.prompts.v1") / f"{name}.md").read_text(encoding="utf-8")


# ----------------------------------------------------------------------------
# Tool-use schemas for structured output
# ----------------------------------------------------------------------------
# Each node forces the model to call one of these fake tools. The
# ``input_schema`` is generated from the corresponding Pydantic model so the
# schema is the single source of truth — changing a response field is a
# one-line Pydantic edit. ``extra='forbid'`` on the models emits
# ``additionalProperties: false`` in the schemas, so Anthropic's server-side
# decoder rejects any unknown fields at sampling time.

_PLAN_LIST_SCHEMA = TypeAdapter(list[ToolCall]).json_schema()

_PLAN_TOOL = {
    "name": "record_plan",
    "description": "Record the ordered list of tool calls to run this iteration.",
    "input_schema": {
        "type": "object",
        "properties": {"plan": _PLAN_LIST_SCHEMA},
        "required": ["plan"],
        "additionalProperties": False,
    },
}

_REFLECTION_TOOL = {
    "name": "record_reflection",
    "description": "Record whether the gathered data is sufficient to answer the question.",
    "input_schema": ReflectionResult.model_json_schema(),
}

_SCOUT_REPORT_TOOL = {
    "name": "record_scout_report",
    "description": "Record the final scout report answering the user's question.",
    "input_schema": ScoutReport.model_json_schema(),
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _extract_tool_input(response: Any, expected_name: str) -> dict[str, Any]:
    """Pull the first ``tool_use`` content block matching ``expected_name``.

    Anthropic guarantees a ``tool_use`` block is present when ``tool_choice``
    forces a specific tool. We still defensively check — a malformed response
    should surface as a :class:`ToolError` rather than an ``AttributeError``
    halfway through parsing.
    """
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == expected_name:
            return dict(block.input)
    raise ToolError(f"Anthropic response did not contain a '{expected_name}' tool_use block")


def _record_usage(
    node: str,
    model: str,
    response: Any,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log usage, push to Langfuse, and return a dict for the ``llm_usage`` state field.

    Three consumers of the same token counts:

    * CloudWatch logs (here) — for grep-driven debugging when Langfuse is
      unreachable.
    * Langfuse (via :func:`record_llm_usage`) — so the UI shows cost and
      latency per generation span.
    * ``state["llm_usage"]`` (returned dict) — consumed by
      ``middleware/budget.py`` to enforce the monthly cap.

    Logging ``stop_reason`` is worth doing because ``"max_tokens"`` means
    the tool_use block was truncated; downstream Pydantic then raises with
    an unhelpful "missing field X" error. Having stop_reason in the log
    tells future-you to raise ``*_MAX_TOKENS`` instead of hunting phantom
    data bugs.
    """
    usage = getattr(response, "usage", None)
    stop_reason = getattr(response, "stop_reason", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
    logger.info(
        "llm_usage node=%s model=%s stop_reason=%s input_tokens=%s output_tokens=%s",
        node,
        model,
        stop_reason,
        input_tokens,
        output_tokens,
    )
    if stop_reason == "max_tokens":
        logger.warning(
            "node %s hit max_tokens — output likely truncated, Pydantic validation may fail",
            node,
        )
    record_llm_usage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        stop_reason=stop_reason,
        metadata={"node": node, **(extra_metadata or {})},
    )
    return {
        "node": node,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _result_key(tc: ToolCall) -> str:
    """Build a unique, human-readable key for a tool result.

    Keyed by name + arg values so ``[query_player(Salah), query_player(Palmer)]``
    produce two distinct entries in ``gathered_data`` instead of the second
    overwriting the first. The format is the LLM-facing label the recommender
    prompt references — readable for traces, stable for the model.

    Args are flattened to ``name=value`` pairs. Long arg combinations fall back
    to a hash suffix to keep keys bounded.
    """
    if not tc.args:
        return tc.name
    arg_summary = ",".join(f"{k}={v}" for k, v in sorted(tc.args.items()))
    if len(arg_summary) > 80:
        return f"{tc.name}#{abs(hash(arg_summary)) % 10000}"
    return f"{tc.name}({arg_summary})"


def _summarise_squad(squad: UserSquad | None) -> str:
    """One-line squad block for the planner prompt.

    The planner only needs to know whether a squad is loaded so it can decide
    whether to ground tool calls in 'my team' context. The recommender gets a
    richer block via :func:`_render_squad_for_recommender`.
    """
    if squad is None:
        return (
            "No user squad provided with this request. Answer generically — "
            "do not reference 'my team' specifics."
        )
    captain = next((p for p in squad.picks if p.is_captain), None)
    captain_name = captain.web_name if captain else "(none)"
    return (
        f"Loaded for GW{squad.gameweek}: {len(squad.picks)} players, "
        f"captain={captain_name}, bank=£{squad.bank:.1f}m, "
        f"value=£{squad.total_value:.1f}m, chip={squad.active_chip or 'none'}."
    )


def _render_squad_for_recommender(squad: UserSquad | None) -> str:
    """Full squad payload for the recommender prompt.

    Dumps the picks as JSON so the LLM can quote any field (web_name, price,
    bench/captain status, position) when answering 'my team' questions. The
    planner gets the one-line summary from :func:`_summarise_squad`; the
    recommender needs the per-pick detail to be useful.
    """
    if squad is None:
        return "No user squad provided — give generic advice rather than personalised picks."
    return squad.model_dump_json()


def _error_report(state: AgentState) -> ScoutReport:
    """Construct a minimal ScoutReport for the error short-circuit path.

    Called by :func:`recommender_node` when ``state["error"]`` is set — saves
    a Sonnet call (and avoids feeding Sonnet partial/broken data, which
    tends to produce a second layer of Pydantic failures).
    """
    err = state.get("error") or "unknown error"
    return ScoutReport(
        question=state.get("question", ""),
        analysis="The agent could not produce a full report for this question.",
        players=[],
        comparison=None,
        recommendation=f"Please retry. Upstream error: {err}",
        caveats=[f"Agent failed upstream: {err}"],
        data_sources=[],
    )


# ----------------------------------------------------------------------------
# planner
# ----------------------------------------------------------------------------
@observe(name="node.planner", as_type="generation")
async def planner_node(
    state: AgentState,
    *,
    client: AsyncAnthropic,
) -> dict[str, Any]:
    """Decide which tools to call this iteration."""
    prompt = _load_prompt("planner").format(
        question=state["question"],
        gathered_data_json=json.dumps(state.get("gathered_data", {}), default=str),
        user_squad_block=_summarise_squad(state.get("user_squad")),
    )

    response = await client.messages.create(
        model=PLANNER_MODEL,
        max_tokens=PLANNER_MAX_TOKENS,
        tools=[_PLAN_TOOL],
        tool_choice={"type": "tool", "name": "record_plan"},
        messages=[{"role": "user", "content": prompt}],
    )
    usage = _record_usage(
        "planner",
        PLANNER_MODEL,
        response,
        extra_metadata={
            "iteration": state.get("iteration_count", 0),
            "question_length": len(state.get("question", "")),
        },
    )

    try:
        raw = _extract_tool_input(response, "record_plan")
        plan = TypeAdapter(list[ToolCall]).validate_python(raw["plan"])
    except (ValidationError, ToolError, KeyError) as exc:
        logger.exception("planner failed to produce a valid plan")
        # Explicitly clear `plan` so the executor doesn't re-run the previous
        # iteration's plan (default reducer is overwrite, but an un-returned
        # key means "don't change it"). `tool_calls_made` uses operator.add,
        # so returning [] is a no-op append — safe either way.
        return {
            "error": f"planner failed: {exc}",
            "plan": [],
            "tool_calls_made": [],
            "llm_usage": [usage],
        }

    return {
        "plan": plan,
        "tool_calls_made": [tc.name for tc in plan],
        "llm_usage": [usage],
    }


# ----------------------------------------------------------------------------
# tool executor
# ----------------------------------------------------------------------------
@observe(name="node.tool_executor")
async def tool_executor_node(
    state: AgentState,
    *,
    tools: dict[str, ToolFn],
) -> dict[str, Any]:
    """Run every :class:`ToolCall` in the current plan concurrently.

    Uses :func:`asyncio.gather` so one slow tool does not block the others.
    Each tool's exceptions are caught inside :func:`_run` and surfaced as an
    ``{"error": ...}`` dict in ``gathered_data`` — siblings are unaffected.

    Results are keyed by ``_result_key(tool_call)`` so duplicate tool calls
    with different args (e.g. ``query_player("Salah")`` and
    ``query_player("Palmer")`` in the same plan) produce distinct entries.
    """
    plan: list[ToolCall] = state.get("plan", [])
    if not plan:
        return {"gathered_data": {}}

    async def _run(tc: ToolCall) -> tuple[str, Any]:
        key = _result_key(tc)
        if tc.name not in tools:
            return key, {"error": f"unknown tool '{tc.name}'"}
        try:
            result = await asyncio.wait_for(
                tools[tc.name](**tc.args),
                timeout=TOOL_TIMEOUT_SECONDS,
            )
            return key, result
        except TimeoutError:
            return key, {"error": f"tool '{tc.name}' timed out"}
        except ToolError as exc:
            return key, {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface unexpected failures into state
            logger.exception("tool %s raised unexpectedly", tc.name)
            return key, {"error": f"unexpected failure: {exc}"}

    results = await asyncio.gather(*(_run(tc) for tc in plan))
    gathered: dict[str, Any] = {key: value for key, value in results}
    return {"gathered_data": gathered}


# ----------------------------------------------------------------------------
# reflector
# ----------------------------------------------------------------------------
@observe(name="node.reflector", as_type="generation")
async def reflector_node(
    state: AgentState,
    *,
    client: AsyncAnthropic,
) -> dict[str, Any]:
    """Decide whether to loop back to the planner or proceed to the recommender.

    Hard-caps the loop at :data:`MAX_ITERATIONS` before calling the LLM —
    once we're at the cap, further reflection is wasted cost since the
    conditional edge will be forced to ``done`` regardless.
    """
    next_iteration = state.get("iteration_count", 0) + 1

    if next_iteration >= MAX_ITERATIONS:
        logger.info("reflector: hit MAX_ITERATIONS=%s, forcing completion", MAX_ITERATIONS)
        return {"should_continue": False, "iteration_count": next_iteration}

    prompt = _load_prompt("reflector").format(
        question=state["question"],
        gathered_data_json=json.dumps(state.get("gathered_data", {}), default=str),
        iteration_count=state.get("iteration_count", 0),
        max_iterations=MAX_ITERATIONS,
    )

    response = await client.messages.create(
        model=REFLECTOR_MODEL,
        max_tokens=REFLECTOR_MAX_TOKENS,
        tools=[_REFLECTION_TOOL],
        tool_choice={"type": "tool", "name": "record_reflection"},
        messages=[{"role": "user", "content": prompt}],
    )
    usage = _record_usage(
        "reflector",
        REFLECTOR_MODEL,
        response,
        extra_metadata={"iteration": state.get("iteration_count", 0)},
    )

    try:
        raw = _extract_tool_input(response, "record_reflection")
        result = ReflectionResult.model_validate(raw)
    except (ValidationError, ToolError) as exc:
        # If the reflector output itself is malformed, proceed to the
        # recommender with whatever we have. Safer than looping blind.
        logger.warning("reflector failed to validate (%s); proceeding to recommender", exc)
        return {
            "should_continue": False,
            "iteration_count": next_iteration,
            "llm_usage": [usage],
        }

    return {
        "should_continue": not result.sufficient,
        "iteration_count": next_iteration,
        "llm_usage": [usage],
    }


# ----------------------------------------------------------------------------
# recommender
# ----------------------------------------------------------------------------
@observe(name="node.recommender", as_type="generation")
async def recommender_node(
    state: AgentState,
    *,
    client: AsyncAnthropic,
) -> dict[str, Any]:
    """Synthesise the gathered data into a structured :class:`ScoutReport`.

    Short-circuits when ``state["error"]`` is set — feeding Sonnet broken or
    empty ``gathered_data`` tends to produce a second Pydantic failure and
    wastes the most expensive call in the graph. Instead, return a minimal
    error report so the API handler has a valid :class:`ScoutReport` to
    render.
    """
    if state.get("error"):
        logger.info("recommender: short-circuiting due to state.error=%r", state["error"])
        return {"final_response": _error_report(state)}

    prompt = _load_prompt("recommender").format(
        question=state["question"],
        gathered_data_json=json.dumps(state.get("gathered_data", {}), default=str),
        user_squad_block=_render_squad_for_recommender(state.get("user_squad")),
    )

    response = await client.messages.create(
        model=RECOMMENDER_MODEL,
        max_tokens=RECOMMENDER_MAX_TOKENS,
        tools=[_SCOUT_REPORT_TOOL],
        tool_choice={"type": "tool", "name": "record_scout_report"},
        messages=[{"role": "user", "content": prompt}],
    )
    usage = _record_usage(
        "recommender",
        RECOMMENDER_MODEL,
        response,
        extra_metadata={"iteration": state.get("iteration_count", 0)},
    )

    try:
        raw = _extract_tool_input(response, "record_scout_report")
        report = ScoutReport.model_validate(raw)
    except (ValidationError, ToolError) as exc:
        logger.exception("recommender produced an invalid ScoutReport")
        return {"error": f"recommender failed: {exc}", "llm_usage": [usage]}

    return {"final_response": report, "llm_usage": [usage]}


# ----------------------------------------------------------------------------
# Conditional edge routing
# ----------------------------------------------------------------------------
def route_after_reflector(state: AgentState) -> str:
    """Map reflector state to the next node's label used by the builder."""
    if state.get("error"):
        return "done"  # short-circuit on any prior error
    return "continue" if state.get("should_continue") else "done"
