"""Unit tests for the shared Secrets Manager resolver."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from fpl_lib.secrets import resolve_secret_to_env


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with no target var set so idempotency short-circuits
    don't mask bugs."""
    monkeypatch.delenv("MY_SECRET", raising=False)


@pytest.mark.unit
def test_fetches_from_conventional_path() -> None:
    """Secret id is ``{prefix}/{env}/{name}`` — the convention the IAM policy scopes to."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "the-value"}

    with patch("fpl_lib.secrets.boto3.client", return_value=mock_client):
        resolve_secret_to_env("dev", "anthropic-api-key", "MY_SECRET")

    assert os.environ["MY_SECRET"] == "the-value"
    mock_client.get_secret_value.assert_called_once_with(
        SecretId="/fpl-platform/dev/anthropic-api-key"
    )


@pytest.mark.unit
def test_is_noop_when_target_var_already_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local dev sets the plain var directly; resolver must not clobber or call AWS."""
    monkeypatch.setenv("MY_SECRET", "local-override")

    with patch("fpl_lib.secrets.boto3.client") as mock_client:
        resolve_secret_to_env("dev", "anthropic-api-key", "MY_SECRET")

    assert os.environ["MY_SECRET"] == "local-override"
    mock_client.assert_not_called()


@pytest.mark.unit
def test_propagates_secrets_manager_exceptions() -> None:
    """The helper raises on AWS failure — callers that tolerate missing secrets
    (Langfuse, Neon on health-only boot) wrap in try/except themselves."""
    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = RuntimeError("access denied")

    with (
        patch("fpl_lib.secrets.boto3.client", return_value=mock_client),
        pytest.raises(RuntimeError, match="access denied"),
    ):
        resolve_secret_to_env("dev", "anthropic-api-key", "MY_SECRET")

    assert "MY_SECRET" not in os.environ


@pytest.mark.unit
def test_honours_custom_prefix_and_region() -> None:
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "x"}

    with patch("fpl_lib.secrets.boto3.client", return_value=mock_client) as mock_ctor:
        resolve_secret_to_env(
            "prod",
            "neon-database-url",
            "MY_SECRET",
            region="us-east-1",
            secret_prefix="/other",
        )

    mock_ctor.assert_called_once_with("secretsmanager", region_name="us-east-1")
    mock_client.get_secret_value.assert_called_once_with(SecretId="/other/prod/neon-database-url")
