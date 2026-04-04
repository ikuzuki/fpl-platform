"""Unit tests for the FPLEnricher abstract base class."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from fpl_enrich.enrichers.base import FPLEnricher

# --- Concrete test enricher ------------------------------------------------


class _StubEnricher(FPLEnricher):
    """Minimal concrete enricher for testing the base class."""

    BATCH_SIZE = 2

    def _get_system_prompt(self) -> str:
        return "You are a test enricher."

    def _validate_output(self, output: dict[str, Any]) -> dict[str, Any] | None:
        if "summary" in output and isinstance(output["summary"], str):
            return output
        return None


# --- Fixtures ---------------------------------------------------------------


def _make_anthropic_response(results: list[dict[str, Any]]) -> MagicMock:
    """Build a mock Anthropic messages.create() response."""
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(results))]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    return response


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def enricher(mock_client: MagicMock) -> _StubEnricher:
    return _StubEnricher(anthropic_client=mock_client)


# --- Tests ------------------------------------------------------------------


@pytest.mark.unit
class TestChunkHelper:
    def test_even_split(self) -> None:
        items = [1, 2, 3, 4]
        chunks = list(FPLEnricher._chunk(items, 2))
        assert chunks == [[1, 2], [3, 4]]

    def test_uneven_split(self) -> None:
        items = [1, 2, 3, 4, 5]
        chunks = list(FPLEnricher._chunk(items, 2))
        assert chunks == [[1, 2], [3, 4], [5]]

    def test_empty_list(self) -> None:
        assert list(FPLEnricher._chunk([], 3)) == []

    def test_single_chunk(self) -> None:
        items = [1, 2]
        chunks = list(FPLEnricher._chunk(items, 5))
        assert chunks == [[1, 2]]


@pytest.mark.unit
class TestCallLLM:
    def test_parses_json_response(self, enricher: _StubEnricher, mock_client: MagicMock) -> None:
        expected = [{"summary": "Good form"}, {"summary": "Poor form"}]
        mock_client.messages.create.return_value = _make_anthropic_response(expected)

        result = enricher._call_llm([{"name": "A"}, {"name": "B"}])

        assert result == expected
        mock_client.messages.create.assert_called_once()

    def test_tracks_token_usage(self, enricher: _StubEnricher, mock_client: MagicMock) -> None:
        mock_client.messages.create.return_value = _make_anthropic_response([{"summary": "x"}])

        enricher._call_llm([{"name": "A"}])

        assert enricher.total_input_tokens == 100
        assert enricher.total_output_tokens == 50

    def test_raises_on_count_mismatch(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.return_value = _make_anthropic_response(
            [{"summary": "only one"}]
        )

        with pytest.raises(ValueError, match="Output count mismatch"):
            enricher._call_llm([{"name": "A"}, {"name": "B"}])

    def test_formats_numbered_items(self, enricher: _StubEnricher, mock_client: MagicMock) -> None:
        mock_client.messages.create.return_value = _make_anthropic_response([{"summary": "x"}])

        enricher._call_llm([{"name": "A"}])

        call_args = mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert user_msg.startswith("I1: ")


@pytest.mark.unit
class TestApply:
    def test_batches_correctly(self, enricher: _StubEnricher, mock_client: MagicMock) -> None:
        """With BATCH_SIZE=2 and 3 items, should make 2 LLM calls."""
        mock_client.messages.create.side_effect = [
            _make_anthropic_response([{"summary": "a"}, {"summary": "b"}]),
            _make_anthropic_response([{"summary": "c"}]),
        ]

        results = enricher.apply([{"name": "A"}, {"name": "B"}, {"name": "C"}])

        assert len(results) == 3
        assert all(r is not None for r in results)
        assert mock_client.messages.create.call_count == 2

    def test_returns_none_for_invalid(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.return_value = _make_anthropic_response(
            [{"summary": "valid"}, {"no_summary": True}]
        )

        results = enricher.apply([{"name": "A"}, {"name": "B"}])

        assert results[0] == {"summary": "valid"}
        assert results[1] is None

    def test_counts_valid_and_invalid(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.return_value = _make_anthropic_response(
            [{"summary": "ok"}, {"bad": True}]
        )

        enricher.apply([{"name": "A"}, {"name": "B"}])

        assert enricher.valid_count == 1
        assert enricher.invalid_count == 1

    def test_empty_input(self, enricher: _StubEnricher, mock_client: MagicMock) -> None:
        results = enricher.apply([])

        assert results == []
        mock_client.messages.create.assert_not_called()

    def test_accumulates_tokens_across_batches(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.side_effect = [
            _make_anthropic_response([{"summary": "a"}, {"summary": "b"}]),
            _make_anthropic_response([{"summary": "c"}]),
        ]

        enricher.apply([{"name": "A"}, {"name": "B"}, {"name": "C"}])

        assert enricher.total_input_tokens == 200
        assert enricher.total_output_tokens == 100


@pytest.mark.unit
class TestLogSummary:
    def test_logs_correct_counts(
        self, enricher: _StubEnricher, caplog: pytest.LogCaptureFixture
    ) -> None:
        enricher.valid_count = 8
        enricher.invalid_count = 2
        enricher.total_input_tokens = 500
        enricher.total_output_tokens = 250

        import logging

        with caplog.at_level(logging.INFO):
            enricher._log_summary()

        assert "8 valid" in caplog.text
        assert "2 invalid" in caplog.text
        assert "500 in" in caplog.text


@pytest.mark.unit
class TestPromptLoader:
    def test_load_existing_prompt(self) -> None:
        from fpl_enrich.utils.prompt_loader import load_prompt

        text = load_prompt("player_summary", "v1")
        assert "form_trend" in text
        assert "confidence" in text

    def test_load_nonexistent_prompt_raises(self) -> None:
        from fpl_enrich.utils.prompt_loader import load_prompt

        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_enricher", "v1")

    def test_all_v1_prompts_exist(self) -> None:
        from fpl_enrich.utils.prompt_loader import load_prompt

        for name in ["player_summary", "injury_signal", "sentiment", "fixture_outlook"]:
            text = load_prompt(name, "v1")
            assert len(text) > 50, f"{name} prompt is too short"
