"""Unit tests for the FPLEnricher abstract base class."""

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ConfigDict, Field

from fpl_enrich.enrichers.base import FPLEnricher

# --- Concrete test enricher ------------------------------------------------


class _StubOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)


class _StubEnricher(FPLEnricher):
    """Minimal concrete enricher for testing the base class."""

    BATCH_SIZE = 2
    OUTPUT_MODEL = _StubOutput

    def _get_system_prompt(self) -> str:
        return "You are a test enricher."

    def _validate_output(self, output: dict[str, Any]) -> dict[str, Any] | None:
        if "summary" in output and isinstance(output["summary"], str):
            return output
        return None


# --- Fixtures ---------------------------------------------------------------


def _make_tool_use_response(results: list[dict[str, Any]]) -> MagicMock:
    """Build a mock Anthropic messages.create() response carrying a tool_use block.

    The real enricher forces ``tool_choice`` to ``record_enrichments`` and reads
    ``response.content[<tool_use block>].input["results"]`` — mirror that shape
    here so the code path under test matches production.
    """
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "record_enrichments"
    tool_block.input = {"results": results}

    response = MagicMock()
    response.content = [tool_block]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    response.stop_reason = "tool_use"
    return response


@pytest.fixture()
def mock_client() -> MagicMock:
    client = MagicMock()
    client.messages.create = AsyncMock()
    return client


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
    @pytest.mark.asyncio
    async def test_parses_tool_use_response(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        expected = [{"summary": "Good form"}, {"summary": "Poor form"}]
        mock_client.messages.create.return_value = _make_tool_use_response(expected)

        result = await enricher._call_llm([{"name": "A"}, {"name": "B"}])

        assert result == expected
        mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_forces_tool_choice(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        """The enricher must force ``tool_choice`` so Anthropic constrains
        sampling to the structured-output schema."""
        mock_client.messages.create.return_value = _make_tool_use_response(
            [{"summary": "x"}, {"summary": "y"}]
        )

        await enricher._call_llm([{"name": "A"}, {"name": "B"}])

        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["tool_choice"] == {"type": "tool", "name": "record_enrichments"}
        tools = kwargs["tools"]
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == "record_enrichments"
        # Schema pins the output count to the batch size — replaces the old
        # prompt-level "return one per input" instruction.
        results_schema = tool["input_schema"]["properties"]["results"]
        assert results_schema["minItems"] == 2
        assert results_schema["maxItems"] == 2
        assert tool["input_schema"]["additionalProperties"] is False

    @pytest.mark.asyncio
    async def test_tool_schema_derives_from_output_model(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        """Schema on the wire must come from ``OUTPUT_MODEL`` — not a
        hand-written copy."""
        mock_client.messages.create.return_value = _make_tool_use_response(
            [{"summary": "x"}, {"summary": "y"}]
        )

        await enricher._call_llm([{"name": "A"}, {"name": "B"}])

        tools = mock_client.messages.create.call_args.kwargs["tools"]
        item_schema = tools[0]["input_schema"]["properties"]["results"]["items"]
        assert item_schema == _StubOutput.model_json_schema()

    @pytest.mark.asyncio
    async def test_tracks_token_usage(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.return_value = _make_tool_use_response([{"summary": "x"}])

        await enricher._call_llm([{"name": "A"}])

        assert enricher.total_input_tokens == 100
        assert enricher.total_output_tokens == 50

    @pytest.mark.asyncio
    async def test_raises_on_count_mismatch(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        """Defensive Python-side check — schema normally prevents this but we
        still want a loud error if Anthropic somehow returns the wrong count."""
        mock_client.messages.create.return_value = _make_tool_use_response(
            [{"summary": "only one"}]
        )

        with pytest.raises(ValueError, match="Output count mismatch"):
            await enricher._call_llm([{"name": "A"}, {"name": "B"}])

    @pytest.mark.asyncio
    async def test_raises_when_no_tool_use_block(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        """If Anthropic returns plain text with no tool_use block (shouldn't
        happen with forced tool_choice, but guard against SDK edge cases)."""
        response = MagicMock()
        response.content = [MagicMock(type="text", text="oops")]
        response.usage.input_tokens = 10
        response.usage.output_tokens = 5
        response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = response

        with pytest.raises(ValueError, match="tool_use block"):
            await enricher._call_llm([{"name": "A"}])

    @pytest.mark.asyncio
    async def test_formats_numbered_items(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.return_value = _make_tool_use_response([{"summary": "x"}])

        await enricher._call_llm([{"name": "A"}])

        call_args = mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert user_msg.startswith("I1: ")


@pytest.mark.unit
class TestApply:
    @pytest.mark.asyncio
    async def test_batches_correctly(self, enricher: _StubEnricher, mock_client: MagicMock) -> None:
        """With BATCH_SIZE=2 and 3 items, should make 2 LLM calls."""
        mock_client.messages.create.side_effect = [
            _make_tool_use_response([{"summary": "a"}, {"summary": "b"}]),
            _make_tool_use_response([{"summary": "c"}]),
        ]

        results = await enricher.apply([{"name": "A"}, {"name": "B"}, {"name": "C"}])

        assert len(results) == 3
        assert all(r is not None for r in results)
        assert mock_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.return_value = _make_tool_use_response(
            [{"summary": "valid"}, {"no_summary": True}]
        )

        results = await enricher.apply([{"name": "A"}, {"name": "B"}])

        assert results[0] == {"summary": "valid"}
        assert results[1] is None

    @pytest.mark.asyncio
    async def test_counts_valid_and_invalid(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.return_value = _make_tool_use_response(
            [{"summary": "ok"}, {"bad": True}]
        )

        await enricher.apply([{"name": "A"}, {"name": "B"}])

        assert enricher.valid_count == 1
        assert enricher.invalid_count == 1

    @pytest.mark.asyncio
    async def test_empty_input(self, enricher: _StubEnricher, mock_client: MagicMock) -> None:
        results = await enricher.apply([])

        assert results == []
        mock_client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_accumulates_tokens_across_batches(
        self, enricher: _StubEnricher, mock_client: MagicMock
    ) -> None:
        mock_client.messages.create.side_effect = [
            _make_tool_use_response([{"summary": "a"}, {"summary": "b"}]),
            _make_tool_use_response([{"summary": "c"}]),
        ]

        await enricher.apply([{"name": "A"}, {"name": "B"}, {"name": "C"}])

        assert enricher.total_input_tokens == 200
        assert enricher.total_output_tokens == 100

    @pytest.mark.asyncio
    async def test_rate_limiter_spaces_requests(self, mock_client: MagicMock) -> None:
        """Verify the rate limiter spaces out API calls."""
        from fpl_enrich.enrichers.base import RateLimiter

        # 600 RPM = 10/sec = 0.1s interval — fast enough for tests
        rate_limiter = RateLimiter(requests_per_minute=600)
        enricher = _StubEnricher(anthropic_client=mock_client, rate_limiter=rate_limiter)

        call_times: list[float] = []

        async def _tracking_create(**kwargs: Any) -> MagicMock:
            call_times.append(time.monotonic())
            return _make_tool_use_response([{"summary": "x"}])

        mock_client.messages.create = _tracking_create

        # 4 items with BATCH_SIZE=2 → 2 batches
        await enricher.apply([{"name": f"{i}"} for i in range(4)])

        assert len(call_times) == 2
        # Calls should be spaced by at least the interval (~0.1s)
        if len(call_times) >= 2:
            gap = call_times[1] - call_times[0]
            assert gap >= 0.09  # allow small timing tolerance


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
