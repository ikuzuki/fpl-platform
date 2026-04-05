"""Abstract base class for FPL LLM enrichers with async batch processing."""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

import anthropic
from langfuse import observe

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


class FPLEnricher(ABC):
    """Base enricher that sends batched items to Claude and validates outputs.

    Subclasses must implement:
        _get_system_prompt() — return the system prompt string
        _validate_output(output) — validate a single LLM output dict

    Class variables:
        BATCH_SIZE — number of items per LLM call (override per enricher)
        MODEL — Anthropic model to use (default: claude-haiku-4-5-20251001)
    """

    BATCH_SIZE: int = 10
    MODEL: str = "claude-haiku-4-5-20251001"

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
        return results

    async def _call_llm_controlled(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Acquire semaphore, then wait for rate limiter, then call LLM."""
        async with self.semaphore:
            await self.rate_limiter.acquire()
            return await self._call_llm(batch)

    @observe(name="enricher_batch_call")
    async def _call_llm(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Send a batch of items to the Anthropic API and parse the JSON response."""
        user_content = "\n".join(f"I{i + 1}: {json.dumps(item)}" for i, item in enumerate(batch))

        system_prompt = self._get_system_prompt().format(batch_size=len(batch))

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

        raw_text = response.content[0].text.strip() if response.content else ""

        if not raw_text:
            logger.error(
                "[ANTHROPIC] %s: empty response (stop_reason=%s, content_blocks=%d)",
                self.__class__.__name__,
                response.stop_reason,
                len(response.content),
            )
            raise ValueError("LLM returned empty response")

        # Strip markdown code fences if the LLM wraps the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]  # remove opening ```json
            raw_text = raw_text.rsplit("```", 1)[0]  # remove closing ```
            raw_text = raw_text.strip()

        try:
            parsed: list[dict[str, Any]] = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error(
                "[ANTHROPIC] %s: invalid JSON (first 200 chars): %s",
                self.__class__.__name__,
                raw_text[:200],
            )
            raise

        if len(parsed) != len(batch):
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
