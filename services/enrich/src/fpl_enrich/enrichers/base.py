"""Abstract base class for FPL LLM enrichers with async batch processing."""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any, ClassVar

import anthropic
from langfuse import Langfuse, observe
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket rate limiter for API calls.

    Enforces a maximum number of requests per minute across all coroutines
    sharing the same instance. Each call to acquire() waits until a slot
    is available.
    """

    def __init__(self, requests_per_minute: int) -> None:
        self.rpm = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0

    async def acquire(self) -> None:
        """Wait until the next request slot is available."""
        async with self._lock:
            now = time.monotonic()
            wait = self._last_request_time + self.interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = time.monotonic()


# Defaults for Tier 1 rate limits.
# - Semaphore caps in-flight requests (avoids "concurrent connections" 429).
# - Rate limiter caps request rate (avoids RPM and output TPM 429).
DEFAULT_MAX_CONCURRENT = 2
DEFAULT_RATE_LIMIT_RPM = 15

# Name of the fake tool each enricher forces the LLM to call. Structured
# output flows through ``response.content[<block>].input["results"]``.
_RESULTS_TOOL_NAME = "record_enrichments"


class FPLEnricher(ABC):
    """Base enricher that sends batched items to Claude and validates outputs.

    Subclasses must set:
        OUTPUT_MODEL — Pydantic model describing one output item
        BATCH_SIZE — number of items per LLM call (override per enricher)
        MODEL — Anthropic model to use

    And implement:
        _get_system_prompt() — return the system prompt string
        _validate_output(output) — validate a single LLM output dict
    """

    BATCH_SIZE: int = 10
    MODEL: str = "claude-haiku-4-5-20251001"
    OUTPUT_MODEL: ClassVar[type[BaseModel]]

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        prompt_version: str = "v1",
        rate_limiter: RateLimiter | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self.client = anthropic_client
        self.prompt_version = prompt_version
        self.rate_limiter = rate_limiter or RateLimiter(DEFAULT_RATE_LIMIT_RPM)
        self.semaphore = semaphore or asyncio.Semaphore(DEFAULT_MAX_CONCURRENT)
        self.valid_count = 0
        self.invalid_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def apply(self, items: list[dict[str, Any]]) -> list[dict[str, Any] | None]:
        """Process all items through the LLM in rate-limited concurrent batches.

        Returns a list aligned with input — None for items that failed validation.
        """
        self.valid_count = 0
        self.invalid_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        batches = list(self._chunk(items, self.BATCH_SIZE))
        logger.info(
            "%s: processing %d items in %d batches (max_concurrent=%d, rate_limit=%d RPM)",
            self.__class__.__name__,
            len(items),
            len(batches),
            self.semaphore._value,
            self.rate_limiter.rpm,
        )

        # Run all batches concurrently — semaphore limits in-flight,
        # rate limiter spaces out new requests
        tasks = [self._call_llm_controlled(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[dict[str, Any] | None] = []
        for i, batch_result in enumerate(batch_results):
            if isinstance(batch_result, Exception):
                logger.error(
                    "%s: batch %d failed: %s",
                    self.__class__.__name__,
                    i,
                    batch_result,
                )
                results.extend([None] * len(batches[i]))
                self.invalid_count += len(batches[i])
                continue

            for output in batch_result:
                validated = self._validate_output(output)
                if validated is not None:
                    results.append(validated)
                    self.valid_count += 1
                else:
                    results.append(None)
                    self.invalid_count += 1

        self._log_summary()

        # Score the parent trace with overall validation pass rate
        total = self.valid_count + self.invalid_count
        if total > 0:
            Langfuse().score_current_trace(
                name="validation_pass_rate",
                value=round(self.valid_count / total, 4),
                comment=f"{self.__class__.__name__}: {self.valid_count}/{total} passed",
            )

        return results

    async def _call_llm_controlled(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Acquire semaphore, then wait for rate limiter, then call LLM."""
        async with self.semaphore:
            await self.rate_limiter.acquire()
            return await self._call_llm(batch)

    # Override in subclasses to restrict which fields are sent to the LLM.
    # None means send everything. Reduces input tokens and cost.
    RELEVANT_FIELDS: list[str] | None = None

    def _prepare_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Filter item to only the fields this enricher needs."""
        if self.RELEVANT_FIELDS is None:
            return item
        return {k: v for k, v in item.items() if k in self.RELEVANT_FIELDS}

    def _build_results_tool(self, batch_size: int) -> dict[str, Any]:
        """Build the Anthropic tool schema that wraps ``OUTPUT_MODEL`` as a list.

        We force the LLM to "call" this tool; Anthropic's decoder constrains
        sampling to JSON that matches the schema, so malformed / missing / typo-ed
        fields can't reach our parser. ``minItems``/``maxItems`` pin the output
        count to the batch size — replaces the old count-mismatch ``ValueError``.
        """
        item_schema = self.OUTPUT_MODEL.model_json_schema()
        return {
            "name": _RESULTS_TOOL_NAME,
            "description": (
                "Record the enrichment result for each input item. The `results` "
                "array MUST contain exactly one object per input item, in the "
                "same order as the numbered items in the user message."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": item_schema,
                        "minItems": batch_size,
                        "maxItems": batch_size,
                    },
                },
                "required": ["results"],
                "additionalProperties": False,
            },
        }

    @observe(name="enricher_batch_call")
    async def _call_llm(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Send a batch to Claude via forced tool-use and return structured results.

        The tool schema is derived from ``OUTPUT_MODEL`` so the Pydantic definition
        is the single source of truth. Anthropic enforces the schema server-side,
        which eliminates the JSON-parsing failure modes the old text path had
        (markdown fences, truncated JSON, missing fields).
        """
        langfuse = Langfuse()
        langfuse.update_current_span(
            metadata={
                "enricher": self.__class__.__name__,
                "prompt_version": self.prompt_version,
                "model": self.MODEL,
                "batch_size": len(batch),
            },
        )
        prepared = [self._prepare_item(item) for item in batch]
        user_content = "\n".join(f"I{i + 1}: {json.dumps(item)}" for i, item in enumerate(prepared))

        system_prompt = self._get_system_prompt().format(batch_size=len(batch))
        tool = self._build_results_tool(len(batch))

        logger.info(
            "[ANTHROPIC] %s: calling %s | batch_size=%d | prompt_version=%s",
            self.__class__.__name__,
            self.MODEL,
            len(batch),
            self.prompt_version,
        )

        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=[tool],
            tool_choice={"type": "tool", "name": _RESULTS_TOOL_NAME},
            messages=[{"role": "user", "content": user_content}],
        )

        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens

        logger.info(
            "[ANTHROPIC] %s: response | input_tokens=%d | output_tokens=%d | stop_reason=%s",
            self.__class__.__name__,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.stop_reason,
        )

        if response.stop_reason == "max_tokens":
            logger.warning(
                "[ANTHROPIC] %s: stop_reason=max_tokens — tool output likely truncated",
                self.__class__.__name__,
            )

        tool_block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if tool_block is None:
            logger.error(
                "[ANTHROPIC] %s: no tool_use block in response (stop_reason=%s, blocks=%d)",
                self.__class__.__name__,
                response.stop_reason,
                len(response.content),
            )
            raise ValueError("LLM did not emit the expected tool_use block")

        parsed: list[dict[str, Any]] = list(tool_block.input.get("results", []))

        # Schema enforces len == batch_size; keep a defensive check so an
        # Anthropic edge case surfaces as a clear error rather than a
        # silent off-by-one downstream.
        count_valid = len(parsed) == len(batch)
        langfuse.score_current_span(
            name="output_count_valid",
            value=1.0 if count_valid else 0.0,
            comment=f"expected={len(batch)}, got={len(parsed)}",
        )

        if not count_valid:
            raise ValueError(f"Output count mismatch: expected {len(batch)}, got {len(parsed)}")

        return parsed

    @staticmethod
    def _chunk(items: list[Any], size: int) -> Iterator[list[Any]]:
        """Split items into chunks of the given size."""
        for i in range(0, len(items), size):
            yield items[i : i + size]

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return the system prompt for this enricher."""

    @abstractmethod
    def _validate_output(self, output: dict[str, Any]) -> dict[str, Any] | None:
        """Validate a single LLM output. Return the dict if valid, None otherwise."""

    def _log_summary(self) -> None:
        """Log processing summary with valid/invalid counts and token usage."""
        total = self.valid_count + self.invalid_count
        logger.info(
            "%s: processed %d items — %d valid, %d invalid (tokens: %d in, %d out)",
            self.__class__.__name__,
            total,
            self.valid_count,
            self.invalid_count,
            self.total_input_tokens,
            self.total_output_tokens,
        )
