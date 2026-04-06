"""Root conftest — applies to all test paths."""

import os


def pytest_configure() -> None:
    """Disable Langfuse during tests to prevent polluting production traces."""
    os.environ.setdefault("LANGFUSE_TRACING_ENABLED", "false")
