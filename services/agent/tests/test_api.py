"""Integration tests for the FastAPI agent app.

The full app is loaded (lifespan runs), but the ``Depends`` hooks that
pull in the compiled graph, budget tracker, and rate limiter are all
overridden with test doubles via ``app.dependency_overrides``. No real
Neon / DynamoDB / Anthropic calls.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from fpl_agent.api import (
    app,
    check_budget,
    check_rate_limit,
    get_budget,
    get_graph,
)
from fpl_agent.models.responses import ScoutReport

pytestmark = pytest.mark.unit


def _scout_report_fixture() -> ScoutReport:
    return ScoutReport(
        question="Is Salah worth it?",
        analysis="Salah is a premium pick.",
        players=[],
        comparison=None,
        recommendation="Keep Salah.",
        caveats=[],
        data_sources=["query_player"],
    )


class _FakeBudget:
    """Stand-in for ``BudgetTracker`` that records what it was asked to write."""

    def __init__(self) -> None:
        self.monthly_limit_usd = 5.0
        self.recorded: list[dict[str, Any]] = []

    async def check_available(self) -> tuple[bool, float]:
        return True, 0.0

    async def record_batch(self, entries: list[dict[str, Any]]) -> float:
        self.recorded.extend(entries)
        return 0.0


def _mock_graph_for_happy_path() -> MagicMock:
    """Graph whose ainvoke + astream return a well-formed end-state."""
    final_state = {
        "question": "Is Salah worth it?",
        "final_response": _scout_report_fixture(),
        "iteration_count": 1,
        "tool_calls_made": ["query_player"],
        "llm_usage": [
            {
                "node": "planner",
                "model": "claude-haiku-4-5",
                "input_tokens": 100,
                "output_tokens": 50,
            },
            {
                "node": "recommender",
                "model": "claude-sonnet-4-6",
                "input_tokens": 200,
                "output_tokens": 120,
            },
        ],
        "gathered_data": {},
        "plan": [],
        "should_continue": False,
        "error": None,
    }

    async def fake_astream(_input, stream_mode: str = "updates"):
        # Emit one update per node, like LangGraph would.
        yield {
            "planner": {
                "llm_usage": [final_state["llm_usage"][0]],
                "tool_calls_made": ["query_player"],
            }
        }
        yield {"tool_executor": {"gathered_data": {}}}
        yield {"reflector": {"should_continue": False, "iteration_count": 1}}
        yield {
            "recommender": {
                "final_response": final_state["final_response"],
                "llm_usage": [final_state["llm_usage"][1]],
            }
        }

    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=final_state)
    graph.astream = fake_astream
    return graph


@pytest.fixture
def fake_budget() -> _FakeBudget:
    return _FakeBudget()


@pytest.fixture
def client(fake_budget: _FakeBudget):
    """TestClient with all runtime deps overridden."""
    graph = _mock_graph_for_happy_path()
    app.dependency_overrides[get_graph] = lambda: graph
    app.dependency_overrides[get_budget] = lambda: fake_budget
    app.dependency_overrides[check_budget] = lambda: fake_budget
    app.dependency_overrides[check_rate_limit] = lambda: None
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_sync_returns_agent_response(client: TestClient, fake_budget: _FakeBudget) -> None:
    resp = client.post("/chat/sync", json={"question": "Is Salah worth it?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["report"]["recommendation"] == "Keep Salah."
    assert body["iterations_used"] == 1
    assert body["tool_calls_made"] == ["query_player"]
    # Budget recorded the full llm_usage list from the final state.
    assert len(fake_budget.recorded) == 2


def test_chat_sync_rejects_empty_question(client: TestClient) -> None:
    resp = client.post("/chat/sync", json={"question": ""})
    assert resp.status_code == 422


def test_chat_sync_rejects_unknown_field(client: TestClient) -> None:
    resp = client.post("/chat/sync", json={"question": "hi", "nope": 1})
    assert resp.status_code == 422


def test_chat_sse_stream_emits_steps_then_result(
    client: TestClient, fake_budget: _FakeBudget
) -> None:
    with client.stream("POST", "/chat", json={"question": "Is Salah worth it?"}) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = []
        current = {}
        for raw in resp.iter_lines():
            # iter_lines yields str on httpx; blank line delimits an event.
            if raw == "":
                if current:
                    events.append(current)
                    current = {}
                continue
            if raw.startswith("event:"):
                current["event"] = raw.removeprefix("event:").strip()
            elif raw.startswith("data:"):
                current["data"] = raw.removeprefix("data:").strip()
        if current:
            events.append(current)

    step_events = [e for e in events if e.get("event") == "step"]
    result_events = [e for e in events if e.get("event") == "result"]
    assert len(step_events) >= 1, f"expected step events, got {events!r}"
    assert len(result_events) == 1, f"expected 1 result event, got {events!r}"

    result_payload = json.loads(result_events[0]["data"])
    assert result_payload["report"]["recommendation"] == "Keep Salah."
    # Post-stream budget record happened (both usage entries).
    assert len(fake_budget.recorded) == 2


def test_budget_exceeded_returns_429(fake_budget: _FakeBudget) -> None:
    """Override check_budget to the real failure path."""

    async def blocked() -> None:
        raise HTTPException(
            status_code=429,
            detail={"error": "monthly_budget_exceeded", "spend_usd": 5.0, "limit_usd": 5.0},
        )

    graph = _mock_graph_for_happy_path()
    app.dependency_overrides[get_graph] = lambda: graph
    app.dependency_overrides[check_budget] = blocked
    app.dependency_overrides[check_rate_limit] = lambda: None
    try:
        with TestClient(app) as tc:
            resp = tc.post("/chat/sync", json={"question": "hi"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["error"] == "monthly_budget_exceeded"


def test_rate_limit_returns_429_with_retry_after(fake_budget: _FakeBudget) -> None:
    async def blocked() -> None:
        raise HTTPException(
            status_code=429,
            detail="rate_limit_exceeded",
            headers={"Retry-After": "42"},
        )

    graph = _mock_graph_for_happy_path()
    app.dependency_overrides[get_graph] = lambda: graph
    app.dependency_overrides[check_budget] = lambda: fake_budget
    app.dependency_overrides[check_rate_limit] = blocked
    try:
        with TestClient(app) as tc:
            resp = tc.post("/chat/sync", json={"question": "hi"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 429
    assert resp.headers.get("retry-after") == "42"


def test_chat_stream_error_event_on_graph_failure(fake_budget: _FakeBudget) -> None:
    """If the graph raises mid-stream, SSE should emit an ``error`` event."""

    async def failing_astream(_input, stream_mode: str = "updates"):
        yield {"planner": {"llm_usage": []}}
        raise RuntimeError("boom")

    graph = MagicMock()
    graph.astream = failing_astream

    app.dependency_overrides[get_graph] = lambda: graph
    app.dependency_overrides[check_budget] = lambda: fake_budget
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        with (
            TestClient(app) as tc,
            tc.stream("POST", "/chat", json={"question": "hi"}) as resp,
        ):
            lines = list(resp.iter_lines())
        events = "\n".join(lines)
    finally:
        app.dependency_overrides.clear()

    assert "event: error" in events
    assert "boom" in events


def test_budget_endpoint_returns_snapshot(client: TestClient) -> None:
    resp = client.get("/budget")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"spend_usd", "limit_usd", "remaining_usd"}
    assert body["limit_usd"] == 5.0


# ---------------------------------------------------------------------------
# Quality scores + flush — observability wiring
# ---------------------------------------------------------------------------
def test_emit_quality_scores_reports_valid_report() -> None:
    from fpl_agent.api import _emit_quality_scores

    final_state: dict[str, Any] = {
        "final_response": _scout_report_fixture(),
        "iteration_count": 2,
        "gathered_data": {
            "query_player(name=Salah)": {"web_name": "Salah"},
            "get_fixture_outlook(player=Salah)": {"error": "timeout"},
            "get_injury_signals(player=Salah)": {"summary": "fit"},
        },
        "error": None,
    }

    with _patch_langfuse() as langfuse_mock:
        _emit_quality_scores(final_state)

    call_map = {
        c.kwargs["name"]: c.kwargs["value"]
        for c in langfuse_mock.score_current_trace.call_args_list
    }
    assert call_map == {
        "output_valid": 1.0,
        "iterations_used": 2.0,
        "tool_success_rate": pytest.approx(0.6667, abs=1e-3),
    }


def test_emit_quality_scores_marks_output_invalid_on_error_state() -> None:
    from fpl_agent.api import _emit_quality_scores

    final_state: dict[str, Any] = {
        "final_response": None,
        "iteration_count": 3,
        "gathered_data": {},
        "error": "planner failed",
    }

    with _patch_langfuse() as langfuse_mock:
        _emit_quality_scores(final_state)

    call_map = {
        c.kwargs["name"]: c.kwargs["value"]
        for c in langfuse_mock.score_current_trace.call_args_list
    }
    assert call_map["output_valid"] == 0.0
    # No tools ran — vacuously 1.0 (no failures recorded).
    assert call_map["tool_success_rate"] == 1.0


def test_emit_quality_scores_swallows_langfuse_failures() -> None:
    """A broken Langfuse must not propagate — we'd rather lose a trace than a response."""
    from fpl_agent.api import _emit_quality_scores

    with _patch_langfuse(side_effect=RuntimeError("langfuse down")):
        # Must not raise.
        _emit_quality_scores({"final_response": _scout_report_fixture()})


def test_chat_sync_flushes_langfuse(client: TestClient) -> None:
    """Observability must drain on every request or Lambda freeze strands events."""
    from unittest.mock import patch

    with patch("fpl_agent.api.langfuse_flush") as mock_flush:
        resp = client.post("/chat/sync", json={"question": "Is Salah worth it?"})

    assert resp.status_code == 200
    assert mock_flush.call_count >= 1


def test_chat_stream_flushes_langfuse(client: TestClient) -> None:
    from unittest.mock import patch

    with (
        patch("fpl_agent.api.langfuse_flush") as mock_flush,
        client.stream("POST", "/chat", json={"question": "hi"}) as resp,
    ):
        # Drain the generator so the ``finally`` runs.
        list(resp.iter_lines())

    assert mock_flush.call_count >= 1


# ---------------------------------------------------------------------------
# Langfuse patching helper
# ---------------------------------------------------------------------------
from contextlib import contextmanager  # noqa: E402 — kept local to tests
from unittest.mock import patch as _patch  # noqa: E402


@contextmanager
def _patch_langfuse(side_effect: Exception | None = None):
    """Swap ``fpl_agent.api.Langfuse`` for a MagicMock yielding a spy instance."""
    mock_instance = MagicMock()
    if side_effect is not None:
        mock_cls = MagicMock(side_effect=side_effect)
    else:
        mock_cls = MagicMock(return_value=mock_instance)
    with _patch("fpl_agent.api.Langfuse", mock_cls):
        yield mock_instance
