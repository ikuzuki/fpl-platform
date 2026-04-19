"""FastAPI wrapper for the FPL scout report agent.

**Lifecycle.** Shared, expensive objects (Anthropic client, Neon pool,
compiled graph, budget tracker, rate limiter) are built once in the
``lifespan`` context manager at Lambda cold-start and reused across warm
invocations. Teardown closes the Neon pool cleanly.

**Budget policy.** "Never overspend" — :class:`BudgetTracker` is checked
*before* the graph runs. If this month's accumulated spend is already at
or over the configured limit, the request is rejected with 429 and no
LLM calls are made. Post-run, the actual token usage tallied up from
``state["llm_usage"]`` is written back to the counter.

**Streaming.** ``POST /chat`` returns a Server-Sent Events stream so the
browser can render intermediate ``step`` events while the agent reasons.
``POST /chat/sync`` is the blocking JSON fallback for clients that don't
do SSE (curl smoke tests, scheduled jobs). Both routes share the same
auth/budget/rate-limit dependencies.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from anthropic import AsyncAnthropic
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pgvector.asyncpg import register_vector
from sse_starlette.sse import EventSourceResponse

from fpl_agent.graph.builder import build_agent_graph
from fpl_agent.middleware.budget import BudgetTracker
from fpl_agent.middleware.rate_limit import RateLimiter
from fpl_agent.models.requests import ChatRequest
from fpl_agent.models.responses import AgentResponse, ScoutReport
from fpl_agent.models.state import initial_state
from fpl_agent.tools.player_tools import make_tools
from fpl_lib.clients.neon import NeonClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read once at import time so unit tests can monkeypatch)
# ---------------------------------------------------------------------------
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
BUDGET_TABLE = os.environ.get("AGENT_USAGE_TABLE", f"fpl-agent-usage-{ENVIRONMENT}")
MONTHLY_BUDGET_USD = float(os.environ.get("AGENT_MONTHLY_BUDGET_USD", "5.0"))
NEON_DATABASE_URL_ENV = "NEON_DATABASE_URL"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared resources on cold-start, clean up on shutdown.

    The Neon pool is the only resource that needs explicit teardown —
    boto3 clients and the in-memory rate limiter are fine to drop.
    """
    database_url = os.environ.get(NEON_DATABASE_URL_ENV)
    anthropic_client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
    neon: NeonClient | None = None

    if database_url:
        neon = NeonClient(database_url, init=register_vector)
        await neon.connect()
        tools = make_tools(neon)
    else:
        # Allows the health endpoint + unit tests to run without Neon.
        # The chat endpoints will 503 if called without Neon configured.
        logger.warning("%s not set — chat endpoints will return 503", NEON_DATABASE_URL_ENV)
        tools = {}

    graph = build_agent_graph(client=anthropic_client, tools=tools) if tools else None

    app.state.anthropic = anthropic_client
    app.state.neon = neon
    app.state.graph = graph
    app.state.budget = BudgetTracker(BUDGET_TABLE, monthly_limit_usd=MONTHLY_BUDGET_USD)
    app.state.rate_limiter = RateLimiter()

    try:
        yield
    finally:
        if neon is not None:
            await neon.close()


app = FastAPI(title="FPL Agent API", version="0.2.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
def get_graph(request: Request) -> Any:
    """Return the compiled graph, or 503 if Neon isn't configured."""
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status_code=503, detail="agent not configured (NEON_DATABASE_URL missing)"
        )
    return graph


def get_budget(request: Request) -> BudgetTracker:
    return request.app.state.budget


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


async def check_budget(budget: BudgetTracker = Depends(get_budget)) -> BudgetTracker:
    """Dependency that blocks the request when the monthly cap is exceeded.

    Returns the tracker so downstream handlers can call :meth:`record_batch`
    without re-resolving the dependency.
    """
    available, spend = await budget.check_available()
    if not available:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "monthly_budget_exceeded",
                "spend_usd": round(spend, 4),
                "limit_usd": budget.monthly_limit_usd,
            },
        )
    return budget


def check_rate_limit(
    request: Request,
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """Dependency that enforces per-session limits with a client-IP fallback."""
    key = x_session_id or (request.client.host if request.client else "anon")
    allowed, retry_after = limiter.allow(key)
    if not allowed:
        headers = {"Retry-After": str(retry_after)} if retry_after else {}
        raise HTTPException(
            status_code=429,
            detail="rate_limit_exceeded",
            headers=headers,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check — used by API Gateway and CloudFront probes."""
    return {"status": "ok"}


@app.get("/budget")
async def budget_status(budget: BudgetTracker = Depends(get_budget)) -> dict[str, Any]:
    """Current-month spend snapshot. Useful for dashboards and smoke tests."""
    _, spend = await budget.check_available()
    return {
        "spend_usd": round(spend, 6),
        "limit_usd": budget.monthly_limit_usd,
        "remaining_usd": round(max(0.0, budget.monthly_limit_usd - spend), 6),
    }


def _agent_response(final_state: dict[str, Any]) -> AgentResponse:
    """Build the API envelope from a graph's final state."""
    report = final_state.get("final_response")
    if not isinstance(report, ScoutReport):
        # Belt-and-braces — builder already short-circuits to _error_report,
        # but a never-reached node would leave this None.
        report = ScoutReport(
            question=final_state.get("question", ""),
            analysis="Agent did not produce a report.",
            recommendation="Please retry.",
            caveats=[final_state.get("error") or "unknown error"],
        )
    return AgentResponse(
        report=report,
        iterations_used=int(final_state.get("iteration_count", 0)),
        tool_calls_made=list(final_state.get("tool_calls_made", [])),
    )


async def _run_graph(graph: Any, question: str) -> dict[str, Any]:
    return await graph.ainvoke(initial_state(question))


def _sse(event_type: str, data: dict[str, Any] | str) -> dict[str, str]:
    """Format a dict for ``sse_starlette.EventSourceResponse``.

    ``EventSourceResponse`` yields dicts with ``event``/``data`` keys. The
    data payload is always JSON-encoded so clients can parse it uniformly.
    """
    payload = data if isinstance(data, str) else json.dumps(data)
    return {"event": event_type, "data": payload}


@app.post("/chat/sync")
async def chat_sync(
    req: ChatRequest,
    budget: BudgetTracker = Depends(check_budget),
    _rl: None = Depends(check_rate_limit),
    graph: Any = Depends(get_graph),
) -> JSONResponse:
    """Blocking JSON endpoint — runs the agent end-to-end and returns the report."""
    try:
        final_state = await _run_graph(graph, req.question)
    except Exception as exc:  # noqa: BLE001 — surface any agent failure as 500
        logger.exception("agent run failed")
        raise HTTPException(status_code=500, detail=f"agent_failure: {exc}") from exc

    await budget.record_batch(final_state.get("llm_usage", []))
    return JSONResponse(_agent_response(final_state).model_dump(mode="json"))


@app.post("/chat")
async def chat_stream(
    req: ChatRequest,
    budget: BudgetTracker = Depends(check_budget),
    _rl: None = Depends(check_rate_limit),
    graph: Any = Depends(get_graph),
) -> EventSourceResponse:
    """SSE endpoint.

    Streams ``step`` events as each node finishes, followed by a terminal
    ``result`` event (or ``error`` if the graph blew up). LangGraph's
    ``astream(..., stream_mode="updates")`` yields one dict per node
    completion, shaped ``{node_name: partial_state_return}``, which maps
    1:1 onto an SSE step event without needing to re-derive which node
    just ran.
    """

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        final_state: dict[str, Any] = dict(initial_state(req.question))
        try:
            async for update in graph.astream(initial_state(req.question), stream_mode="updates"):
                # update is {node_name: partial_dict}; typically one key per tick.
                for node_name, partial in update.items():
                    # Re-apply the partial to our shadow state so we have the
                    # final state ready when the stream ends. This is the same
                    # work LangGraph does internally — doing it here avoids a
                    # second ``ainvoke`` call.
                    _merge_partial(final_state, partial)
                    yield _sse("step", {"node": node_name})
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent stream failed")
            yield _sse("error", {"message": str(exc)})
            return

        try:
            await budget.record_batch(final_state.get("llm_usage", []))
        except Exception:  # noqa: BLE001 — budget write failures must not kill the response
            logger.exception("failed to record usage after graph run")

        yield _sse("result", _agent_response(final_state).model_dump(mode="json"))

    return EventSourceResponse(event_generator())


def _merge_partial(state: dict[str, Any], partial: dict[str, Any]) -> None:
    """Mirror LangGraph's reducers for the fields we care about downstream.

    Only the two accumulating fields (``llm_usage``, ``tool_calls_made``)
    need their own append; everything else is fine to overwrite for the
    purpose of building the final response envelope.
    """
    for key, value in (partial or {}).items():
        if key in ("llm_usage", "tool_calls_made") and isinstance(value, list):
            state.setdefault(key, []).extend(value)
        elif key == "gathered_data" and isinstance(value, dict):
            state.setdefault(key, {}).update(value)
        else:
            state[key] = value
