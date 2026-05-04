"""Unit tests for the shared Langfuse observability module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

import fpl_lib.observability as observability
from fpl_lib.observability import (
    flush,
    init_langfuse,
    record_llm_usage,
)


@pytest.fixture(autouse=True)
def _clear_langfuse_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip Langfuse env vars so each test starts from a clean slate.

    Also resets the module-scope cached client so tests never leak a patched
    ``Langfuse`` instance into subsequent tests. Default tracing state is
    ``on`` so existing ``flush`` / ``record_llm_usage`` tests exercise the
    live path; the disabled-path tests opt in via ``setenv``.
    """
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    observability._client = None
    yield
    observability._client = None


# ---------------------------------------------------------------------------
# init_langfuse
# ---------------------------------------------------------------------------
class TestInitLangfuse:
    @pytest.mark.unit
    def test_fetches_both_parameters_from_ssm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_client = MagicMock()
        mock_client.get_parameter.side_effect = [
            {"Parameter": {"Value": "pk-test"}},
            {"Parameter": {"Value": "sk-test"}},
        ]
        with patch("fpl_lib.secrets.boto3.client", return_value=mock_client):
            result = init_langfuse(environment="dev")

        assert result is True
        assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-test"
        assert os.environ["LANGFUSE_SECRET_KEY"] == "sk-test"
        assert mock_client.get_parameter.call_count == 2

    @pytest.mark.unit
    def test_is_idempotent_when_env_already_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "existing-pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "existing-sk")

        with patch("fpl_lib.secrets.boto3.client") as mock_boto:
            result = init_langfuse()

        assert result is True
        # SSM must not be called when env is already populated.
        mock_boto.assert_not_called()

    @pytest.mark.unit
    def test_returns_false_and_does_not_raise_when_ssm_fails(self) -> None:
        mock_client = MagicMock()
        mock_client.get_parameter.side_effect = RuntimeError("AWS blew up")

        with patch("fpl_lib.secrets.boto3.client", return_value=mock_client):
            result = init_langfuse(environment="dev")

        assert result is False
        # Caller should survive — tracing is optional.
        assert "LANGFUSE_PUBLIC_KEY" not in os.environ

    @pytest.mark.unit
    def test_respects_secret_prefix_and_environment(self) -> None:
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "x"}}
        with patch("fpl_lib.secrets.boto3.client", return_value=mock_client):
            init_langfuse(environment="prod", secret_prefix="/custom")

        names = [
            call.kwargs["Name"]
            for call in mock_client.get_parameter.call_args_list
            if call.kwargs.get("Name")
        ]
        assert "/custom/prod/langfuse-public-key" in names
        assert "/custom/prod/langfuse-secret-key" in names


# ---------------------------------------------------------------------------
# record_llm_usage
# ---------------------------------------------------------------------------
class TestRecordLlmUsage:
    @pytest.mark.unit
    def test_forwards_model_and_tokens_to_langfuse(self) -> None:
        mock_langfuse_cls = MagicMock()
        mock_instance = MagicMock()
        mock_langfuse_cls.return_value = mock_instance

        with patch("fpl_lib.observability.Langfuse", mock_langfuse_cls):
            record_llm_usage(
                model="claude-haiku-4-5",
                input_tokens=120,
                output_tokens=45,
                stop_reason="end_turn",
                metadata={"iteration": 1},
            )

        mock_instance.update_current_generation.assert_called_once_with(
            model="claude-haiku-4-5",
            usage_details={"input": 120, "output": 45},
            metadata={"stop_reason": "end_turn", "iteration": 1},
        )

    @pytest.mark.unit
    def test_swallows_exceptions_from_langfuse(self) -> None:
        mock_langfuse_cls = MagicMock(side_effect=RuntimeError("no trace context"))
        with patch("fpl_lib.observability.Langfuse", mock_langfuse_cls):
            # Must not raise. If it did, a broken Langfuse client would break the agent.
            record_llm_usage(model="x", input_tokens=0, output_tokens=0)

    @pytest.mark.unit
    def test_handles_missing_metadata_arg(self) -> None:
        mock_langfuse_cls = MagicMock()
        mock_instance = MagicMock()
        mock_langfuse_cls.return_value = mock_instance

        with patch("fpl_lib.observability.Langfuse", mock_langfuse_cls):
            record_llm_usage(model="m", input_tokens=10, output_tokens=20)

        call_kwargs = mock_instance.update_current_generation.call_args.kwargs
        assert call_kwargs["metadata"] == {"stop_reason": None}


# ---------------------------------------------------------------------------
# flush
# ---------------------------------------------------------------------------
class TestFlush:
    @pytest.mark.unit
    def test_calls_langfuse_flush(self) -> None:
        mock_instance = MagicMock()
        with patch("fpl_lib.observability.Langfuse", return_value=mock_instance):
            flush()
        mock_instance.flush.assert_called_once()

    @pytest.mark.unit
    def test_swallows_exceptions(self) -> None:
        with patch("fpl_lib.observability.Langfuse", side_effect=RuntimeError("broken")):
            # Must not raise — flush failures must never interrupt the response path.
            flush()


# ---------------------------------------------------------------------------
# Module-scope client + tracing toggle
# ---------------------------------------------------------------------------
class TestClientLifecycle:
    @pytest.mark.unit
    def test_client_is_constructed_once_across_calls(self) -> None:
        """Langfuse maintainers flag per-call `Langfuse()` as a Lambda anti-pattern.

        The module-scope cache must reuse the same client across every
        ``flush`` / ``record_llm_usage`` invocation in a warm container.
        """
        mock_langfuse_cls = MagicMock()
        mock_instance = MagicMock()
        mock_langfuse_cls.return_value = mock_instance

        with patch("fpl_lib.observability.Langfuse", mock_langfuse_cls):
            flush()
            flush()
            record_llm_usage(model="m", input_tokens=1, output_tokens=1)

        assert mock_langfuse_cls.call_count == 1

    @pytest.mark.unit
    def test_flush_short_circuits_when_tracing_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "false")
        mock_langfuse_cls = MagicMock()

        with patch("fpl_lib.observability.Langfuse", mock_langfuse_cls):
            flush()

        # Langfuse is not constructed at all — the kill-switch must prevent
        # any OTEL pipeline initialisation.
        mock_langfuse_cls.assert_not_called()

    @pytest.mark.unit
    def test_record_llm_usage_short_circuits_when_tracing_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "0")
        mock_langfuse_cls = MagicMock()

        with patch("fpl_lib.observability.Langfuse", mock_langfuse_cls):
            record_llm_usage(model="m", input_tokens=1, output_tokens=1)

        mock_langfuse_cls.assert_not_called()

    @pytest.mark.unit
    def test_client_construction_failure_is_swallowed(self) -> None:
        """A broken Langfuse init must never break the request path."""
        with patch("fpl_lib.observability.Langfuse", side_effect=RuntimeError("config")):
            # Neither call should raise; both should no-op.
            flush()
            record_llm_usage(model="m", input_tokens=1, output_tokens=1)
