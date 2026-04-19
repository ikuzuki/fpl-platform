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
from typing import Any

from langfuse import Langfuse, observe, propagate_attributes

from fpl_lib.secrets import DEFAULT_REGION, DEFAULT_SECRET_PREFIX, resolve_secret_to_env

logger = logging.getLogger(__name__)


def init_langfuse(
    environment: str = "dev",
    region: str = DEFAULT_REGION,
    secret_prefix: str = DEFAULT_SECRET_PREFIX,
) -> bool:
    """Populate ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` from Secrets Manager.

    Returns ``True`` if keys are now available in the environment (either
    fetched this call or already set), ``False`` if secrets could not be
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
    try:
        Langfuse().update_current_generation(
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
    """
    try:
        Langfuse().flush()
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
