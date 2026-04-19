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
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pgvector.asyncpg import register_vector
from sse_starlette.sse import EventSourceResponse

from fpl_agent.graph.builder import build_agent_graph
from fpl_agent.middleware.budget import BudgetTracker
from fpl_agent.middleware.rate_limit import RateLimiter
from fpl_agent.models.requests import ChatRequest
from fpl_agent.models.responses import AgentResponse, ScoutReport, UserSquad
from fpl_agent.models.state import initial_state
from fpl_agent.squad_loader import SquadFetchError, SquadNotFoundError, load_user_squad
from fpl_agent.tools.player_tools import make_tools
from fpl_lib.clients.neon import NeonClient
from fpl_lib.observability import (
    Langfuse,
    init_langfuse,
    observe,
    propagate_attributes,
)
from fpl_lib.observability import (
    flush as langfuse_flush,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read once at import time so unit tests can monkeypatch)
# ---------------------------------------------------------------------------
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
BUDGET_TABLE = os.environ.get("AGENT_USAGE_TABLE", f"fpl-agent-usage-{ENVIRONMENT}")
MONTHLY_BUDGET_USD = float(os.environ.get("AGENT_MONTHLY_BUDGET_USD", "5.0"))
NEON_DATABASE_URL_ENV = "NEON_DATABASE_URL"
TEAM_FETCHER_FUNCTION_NAME_ENV = "TEAM_FETCHER_FUNCTION_NAME"

# Production traffic is same-origin via CloudFront — the browser hits the
# dashboard domain and proxies to /api/agent/*, so CORS mostly matters for
# local Vite dev. The CloudFront domain is added via env so we don't hardcode
# a dev-specific hostname into the image.
_extra_origins = os.environ.get("AGENT_CORS_EXTRA_ORIGINS", "")
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    *(o.strip() for o in _extra_origins.split(",") if o.strip()),
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared resources on cold-start, clean up on shutdown.

    The Neon pool is the only resource that needs explicit teardown —
    boto3 clients and the in-memory rate limiter are fine to drop.

    Langfuse is initialised here so every ``@observe`` span in the graph
    and tools picks up the keys on first use. If Secrets Manager is
    unreachable, ``init_langfuse`` logs a warning and returns — the
    service still runs, just without tracing.
    """
    init_langfuse(environment=ENVIRONMENT)

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


app = FastAPI(title="FPL Agent API", version="0.3.0", lifespan=lifespan)

# Moved from API Gateway to the application layer per ADR-0010. CORS for
# /chat endpoints that stream SSE — the browser sends a preflight before the
# POST, and the actual request must carry Access-Control-Allow-Origin on the
# response headers (applied by this middleware to both preflight and stream
# responses).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Session-Id"],
)


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


def get_neon(request: Request) -> NeonClient:
    """Return the live NeonClient, or 503 if Neon isn't configured.

    Used by ``/team`` (squad enrichment) — chat routes go through ``get_graph``
    and inherit Neon via the tool registry.
    """
    neon = getattr(request.app.state, "neon", None)
    if neon is None:
        raise HTTPException(
            status_code=503, detail="agent not configured (NEON_DATABASE_URL missing)"
        )
    return neon


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


@app.get("/team")
@observe(name="get_team")
async def get_team(
    team_id: int = Query(..., ge=1, description="FPL manager team ID"),
    gameweek: int = Query(..., ge=1, le=38, description="Gameweek number 1-38"),
    neon: NeonClient = Depends(get_neon),
    _rl: None = Depends(check_rate_limit),
) -> UserSquad:
    """Fetch and enrich a user's FPL squad.

    Two-step under the hood: invoke the team-fetcher Lambda to get raw picks
    from FPL, then join against Neon ``player_embeddings`` to attach names,
    teams, and prices. The dashboard echoes the returned :class:`UserSquad`
    back on every chat request so the agent never has to refetch.

    Not subject to ``check_budget`` — this endpoint costs no LLM tokens.
    Tracing wraps it as a generic span so squad-load failures show up next
    to chat traces in the same Langfuse timeline.
    """
    function_name = os.environ.get(TEAM_FETCHER_FUNCTION_NAME_ENV)
    if not function_name:
        raise HTTPException(
            status_code=503,
            detail=f"{TEAM_FETCHER_FUNCTION_NAME_ENV} not set — squad lookups are unavailable",
        )

    try:
        return await load_user_squad(
            team_id=team_id,
            gameweek=gameweek,
            neon=neon,
            function_name=function_name,
        )
    except SquadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SquadFetchError as exc:
        # 502 — upstream (FPL via Lambda, or Neon) failed. Distinct from 500
        # so the dashboard can render "FPL is down" instead of "agent is broken".
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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


async def _run_graph(graph: Any, question: str, squad: UserSquad | None) -> dict[str, Any]:
    return await graph.ainvoke(initial_state(question, squad))


def _chat_trace_metadata(req: ChatRequest, transport: str) -> dict[str, str]:
    """Build the metadata dict pushed into the Langfuse trace via propagate_attributes.

    Includes ``team_id`` / ``gameweek`` when the request carried a squad so the
    Langfuse UI can filter / group by team for debugging "why did the agent
    recommend X for team 12345".
    """
    meta = {"question_length": str(len(req.question)), "transport": transport}
    if req.squad is not None:
        meta["team_id"] = str(req.squad.team_id)
        meta["gameweek"] = str(req.squad.gameweek)
    return meta


def _emit_quality_scores(final_state: dict[str, Any]) -> None:
    """Attach three request-level scores to the current Langfuse trace.

    Called after the graph completes (or after a streaming run ends). The
    scores are pure functions of ``final_state`` so they can be unit-tested
    without any Langfuse fixture; the push itself is wrapped in try/except
    because observability must never interrupt the response path.

    Scores:

    * ``output_valid`` — 1.0 if a :class:`ScoutReport` was produced without
      the graph setting ``error``, else 0.0. Drives dashboards that track
      "how often the agent actually answered."
    * ``iterations_used`` — raw iteration count (lower is better). Langfuse
      UI aggregates so this is logged as-is.
    * ``tool_success_rate`` — fraction of ``gathered_data`` entries that
      aren't error dicts. 1.0 when no tools ran (vacuously — nothing failed).
    """
    try:
        report = final_state.get("final_response")
        error = final_state.get("error")
        output_valid = 1.0 if isinstance(report, ScoutReport) and not error else 0.0

        gathered = final_state.get("gathered_data", {}) or {}
        if gathered:
            failed = sum(1 for v in gathered.values() if isinstance(v, dict) and "error" in v)
            tool_success_rate = 1.0 - (failed / len(gathered))
        else:
            tool_success_rate = 1.0

        langfuse = Langfuse()
        langfuse.score_current_trace(name="output_valid", value=output_valid)
        langfuse.score_current_trace(
            name="iterations_used",
            value=float(final_state.get("iteration_count", 0)),
        )
        langfuse.score_current_trace(name="tool_success_rate", value=round(tool_success_rate, 4))
    except Exception:  # noqa: BLE001
        logger.debug("failed to emit quality scores to Langfuse", exc_info=True)


def _trace_tags() -> list[str]:
    """Tags applied to every agent trace. Kept here so changes are one edit."""
    return ["agent", ENVIRONMENT]


def _sse(event_type: str, data: dict[str, Any] | str) -> dict[str, str]:
    """Format a dict for ``sse_starlette.EventSourceResponse``.

    ``EventSourceResponse`` yields dicts with ``event``/``data`` keys. The
    data payload is always JSON-encoded so clients can parse it uniformly.
    """
    payload = data if isinstance(data, str) else json.dumps(data)
    return {"event": event_type, "data": payload}


@app.post("/chat/sync")
@observe(name="agent_chat_request")
async def chat_sync(
    req: ChatRequest,
    budget: BudgetTracker = Depends(check_budget),
    _rl: None = Depends(check_rate_limit),
    graph: Any = Depends(get_graph),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> JSONResponse:
    """Blocking JSON endpoint — runs the agent end-to-end and returns the report."""
    with propagate_attributes(
        session_id=x_session_id or "anon",
        user_id="anon",
        tags=_trace_tags(),
        metadata=_chat_trace_metadata(req, "sync"),
    ):
        try:
            final_state = await _run_graph(graph, req.question, req.squad)
        except Exception as exc:  # noqa: BLE001 — surface any agent failure as 500
            logger.exception("agent run failed")
            langfuse_flush()
            raise HTTPException(status_code=500, detail=f"agent_failure: {exc}") from exc

        _emit_quality_scores(final_state)
        await budget.record_batch(final_state.get("llm_usage", []))
        response = _agent_response(final_state).model_dump(mode="json")

    langfuse_flush()
    return JSONResponse(response)


@app.post("/chat")
@observe(name="agent_chat_request")
async def chat_stream(
    req: ChatRequest,
    budget: BudgetTracker = Depends(check_budget),
    _rl: None = Depends(check_rate_limit),
    graph: Any = Depends(get_graph),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> EventSourceResponse:
    """SSE endpoint.

    Streams ``step`` events as each node finishes, followed by a terminal
    ``result`` event (or ``error`` if the graph blew up). LangGraph's
    ``astream(..., stream_mode="updates")`` yields one dict per node
    completion, shaped ``{node_name: partial_state_return}``, which maps
    1:1 onto an SSE step event without needing to re-derive which node
    just ran.

    The ``propagate_attributes`` context must live inside the generator —
    not around ``EventSourceResponse(...)`` — because the generator runs
    async after the handler returns, and contextvars don't propagate
    across the boundary unless they're entered in the generator frame.
    Same reason ``langfuse_flush`` is in the generator's ``finally``.
    """

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        final_state: dict[str, Any] = dict(initial_state(req.question, req.squad))
        with propagate_attributes(
            session_id=x_session_id or "anon",
            user_id="anon",
            tags=_trace_tags(),
            metadata=_chat_trace_metadata(req, "sse"),
        ):
            try:
                async for update in graph.astream(
                    initial_state(req.question, req.squad), stream_mode="updates"
                ):
                    # update is {node_name: partial_dict}; typically one key per tick.
                    for node_name, partial in update.items():
                        # Re-apply the partial to our shadow state so we have
                        # the final state ready when the stream ends. This is
                        # the same work LangGraph does internally — doing it
                        # here avoids a second ``ainvoke`` call.
                        _merge_partial(final_state, partial)
                        yield _sse("step", {"node": node_name})
            except Exception as exc:  # noqa: BLE001
                logger.exception("agent stream failed")
                yield _sse("error", {"message": str(exc)})
                langfuse_flush()
                return

            _emit_quality_scores(final_state)
            try:
                await budget.record_batch(final_state.get("llm_usage", []))
            except Exception:  # noqa: BLE001 — budget write failures must not kill the response
                logger.exception("failed to record usage after graph run")

            yield _sse("result", _agent_response(final_state).model_dump(mode="json"))

        # Outside propagate_attributes — flush must happen after the last
        # event is yielded so client disconnect between steps still uploads
        # accumulated spans.
        langfuse_flush()

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
