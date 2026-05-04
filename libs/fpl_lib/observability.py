"""Langfuse observability helpers for LLM-using services.

Centralises the three pieces that every service wiring Langfuse needs:

* :func:`init_langfuse` — populate Langfuse env vars from Secrets Manager so
  ``@observe`` decorators light up at runtime. Safe to call multiple times.
* :func:`record_llm_usage` — push model + token counts to the Langfuse UI so
  cost/latency dashboards work. Without this, ``@observe(as_type="generation")``
  produces a generation span with no usage data.
* :func:`flush` — drain the background queue before the Lambda execution
  environment freezes.

The module also re-exports :class:`Langfuse`, :func:`observe`, and
:func:`propagate_attributes` so service code only imports from
``fpl_lib.observability``. That keeps the choice of tracing provider
swappable from one file.

Design note: these are module-level functions, not methods on a client class,
because Langfuse's own ``Langfuse`` class is already a process-wide singleton.
There is no per-call state for us to encapsulate — wrapping a singleton in
another singleton would add indirection without functionality.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langfuse import Langfuse, observe, propagate_attributes

from fpl_lib.secrets import DEFAULT_REGION, DEFAULT_SECRET_PREFIX, resolve_secret_to_env

logger = logging.getLogger(__name__)

# Module-scope Langfuse client — re-constructing ``Langfuse()`` on every call
# is the Lambda anti-pattern Langfuse maintainers explicitly flag in
# https://github.com/orgs/langfuse/discussions/7669 (v3/v4 SDK rebuilds the
# OTEL tracer provider on each instantiation). A single client built once per
# cold-start reuses the pipeline across all invocations in the warm container.
#
# We defer construction until the first call site asks for the client so that
# import-time (e.g. in unit tests) does not trigger Langfuse's OTEL setup —
# tests monkeypatch ``LANGFUSE_TRACING_ENABLED=false`` and expect zero network
# activity during module import. ``_get_client`` returns ``None`` when tracing
# is disabled so callers can short-circuit without inspecting env themselves.
_client: Langfuse | None = None


def _tracing_enabled() -> bool:
    """Mirror Langfuse's own env-var convention so callers can gate work."""
    return os.environ.get("LANGFUSE_TRACING_ENABLED", "true").lower() not in {
        "false",
        "0",
        "no",
    }


def _get_client() -> Langfuse | None:
    """Return the process-wide Langfuse client, or ``None`` if tracing is off.

    The first call lazily constructs the client. All OTEL pipeline setup
    happens here, once, on the first traced request of a cold-start.
    """
    global _client
    if not _tracing_enabled():
        return None
    if _client is None:
        try:
            _client = Langfuse()
        except Exception:  # noqa: BLE001
            logger.debug("Langfuse client construction failed", exc_info=True)
            return None
    return _client


def init_langfuse(
    environment: str = "dev",
    region: str = DEFAULT_REGION,
    secret_prefix: str = DEFAULT_SECRET_PREFIX,
) -> bool:
    """Populate ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` from SSM Parameter Store.

    Returns ``True`` if keys are now available in the environment (either
    fetched this call or already set), ``False`` if parameters could not be
    loaded. A ``False`` return means ``@observe`` decorators continue to
    no-op — the service will run, just without tracing. This is deliberate:
    observability must never block the request path, which is why we
    wrap the shared resolver in try/except here rather than letting the
    exception propagate the way required-secret callers do.

    Idempotent: a second call with the env vars already set is a cheap
    string check. Safe to call on every Lambda invocation.
    """
    try:
        resolve_secret_to_env(
            environment,
            "langfuse-public-key",
            "LANGFUSE_PUBLIC_KEY",
            region=region,
            secret_prefix=secret_prefix,
        )
        resolve_secret_to_env(
            environment,
            "langfuse-secret-key",
            "LANGFUSE_SECRET_KEY",
            region=region,
            secret_prefix=secret_prefix,
        )
    except Exception as exc:  # noqa: BLE001 — any AWS failure is non-fatal
        logger.warning("Langfuse init failed, tracing disabled: %s", exc)
        return False
    return True


def record_llm_usage(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    stop_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Push model + token usage to the currently-active generation span.

    Call this inside an ``@observe(as_type="generation")`` function after an
    Anthropic response. Langfuse uses the ``model`` string to look up
    published rates and compute cost automatically — no local rate table
    needed.

    Swallows all exceptions. If Langfuse isn't initialised, or if the call
    site isn't inside a generation span, the failure is logged at DEBUG and
    the caller proceeds. Observability must not break the code path it
    observes.
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.update_current_generation(
            model=model,
            usage_details={"input": int(input_tokens), "output": int(output_tokens)},
            metadata={"stop_reason": stop_reason, **(metadata or {})},
        )
    except Exception:  # noqa: BLE001
        logger.debug("Langfuse update_current_generation failed", exc_info=True)


def flush() -> None:
    """Drain pending Langfuse events before the Lambda environment freezes.

    Langfuse batches events on a background thread. In a long-running
    server that thread eventually flushes; in Lambda the execution
    environment can freeze immediately after the response returns, stranding
    events in the queue. Call this at the end of every request handler.

    Bounded by the OTLP exporter timeout — we set
    ``OTEL_BSP_EXPORT_TIMEOUT=5000`` and ``OTEL_EXPORTER_OTLP_TIMEOUT=3000``
    in the Lambda env so a slow or unreachable Langfuse endpoint adds at most
    ~5s to the response, never the 60s default. On cold starts where Langfuse
    is unreachable, that ~5s is the tradeoff we accept for real traces. Worth
    re-evaluating via an ADOT Lambda Extension if trace drop-rate becomes
    visible in the Langfuse UI; see ADR-0005.
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:  # noqa: BLE001
        logger.debug("Langfuse flush failed", exc_info=True)


__all__ = [
    "Langfuse",
    "flush",
    "init_langfuse",
    "observe",
    "propagate_attributes",
    "record_llm_usage",
]
