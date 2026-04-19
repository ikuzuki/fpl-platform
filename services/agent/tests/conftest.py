"""Test fixtures for fpl_agent service."""

from __future__ import annotations

import os


def pytest_configure() -> None:
    """Stub the env vars the lifespan's secret resolver needs.

    The agent's cold-start ``lifespan`` calls
    ``resolve_secret_to_env("dev", "anthropic-api-key", "ANTHROPIC_API_KEY")``
    which hits Secrets Manager unless ``ANTHROPIC_API_KEY`` is already set.
    Tests mock the Anthropic client via dependency overrides and never make
    real API calls, so any placeholder keeps the resolver's AWS path from
    running in CI / local pytest.
    """
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key-unused")
