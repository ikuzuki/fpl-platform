"""Abstract base class for FPL LLM enrichers with batch processing."""

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


class FPLEnricher(ABC):
    """Base enricher that sends batched items to Claude and validates outputs.

    Subclasses must implement:
        _get_system_prompt() — return the system prompt string
        _validate_output(output) — validate a single LLM output dict

    Class variables:
        BATCH_SIZE — number of items per LLM call (override per enricher)
        MODEL — Anthropic model to use (default: claude-haiku-4-5-20251001)
    """

    BATCH_SIZE: int = 5
    MODEL: str = "claude-haiku-4-5-20251001"

    def __init__(
        self,
        anthropic_client: anthropic.Anthropic,
        prompt_version: str = "v1",
    ) -> None:
        self.client = anthropic_client
        self.prompt_version = prompt_version
        self.valid_count = 0
        self.invalid_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def apply(self, items: list[dict[str, Any]]) -> list[dict[str, Any] | None]:
        """Process all items through the LLM in batches.

        Returns a list aligned with input — None for items that failed validation.
        """
        self.valid_count = 0
        self.invalid_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        results: list[dict[str, Any] | None] = []

        for batch in self._chunk(items, self.BATCH_SIZE):
            batch_results = self._call_llm(batch)

            for output in batch_results:
                validated = self._validate_output(output)
                if validated is not None:
                    results.append(validated)
                    self.valid_count += 1
                else:
                    results.append(None)
                    self.invalid_count += 1

        self._log_summary()
        return results

    def _call_llm(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Send a batch of items to the Anthropic API and parse the JSON response."""
        user_content = "\n".join(
            f"I{i + 1}: {json.dumps(item)}" for i, item in enumerate(batch)
        )

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            system=self._get_system_prompt(),
            messages=[{"role": "user", "content": user_content}],
        )

        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens

        raw_text = response.content[0].text
        parsed: list[dict[str, Any]] = json.loads(raw_text)

        if len(parsed) != len(batch):
            raise ValueError(
                f"Output count mismatch: expected {len(batch)}, got {len(parsed)}"
            )

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
            "%s: processed %d items — %d valid, %d invalid "
            "(tokens: %d in, %d out)",
            self.__class__.__name__,
            total,
            self.valid_count,
            self.invalid_count,
            self.total_input_tokens,
            self.total_output_tokens,
        )
