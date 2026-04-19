"""DynamoDB-backed monthly cost tracker for the agent API.

Runs as a FastAPI dependency before every ``/chat`` request. If the current
month's accumulated spend exceeds the configured cap, the dependency raises
429 and the graph is never invoked — this is the "never overspend" policy
(checked up-front, not reconciled after the fact).

**Schema of the ``fpl-agent-usage-{env}`` table:**

- ``month`` (hash key, string, ``YYYY-MM``, UTC) — partition per calendar month
- ``total_input_tokens`` (N) — running sum across all LLM calls this month
- ``total_output_tokens`` (N)
- ``total_cost_usd`` (N) — running sum; source of truth for budget checks
- ``budget_limit_usd`` (N) — set on first write; cheap audit trail
- ``exceeded_at`` (S) — ISO timestamp stamped the moment we first detect
  spend >= limit; handy for Langfuse/PagerDuty correlation later
- ``updated_at`` (S) — ISO timestamp of last ``record_usage`` write

Rows are lazy-created on first touch via a conditional ``PutItem``; this
means a fresh month never requires a deploy.

**Pricing.** Per-model rates below are Anthropic public pricing (USD per
million tokens). Update when Anthropic publishes new rates — this file is
the single place the agent does the ``tokens → dollars`` calculation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# USD per 1M tokens. Anthropic public pricing (verify periodically).
_MODEL_RATES: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
}
_FALLBACK_RATE = (3.0, 15.0)  # assume Sonnet rates for unknown models — cautious


def _current_month() -> str:
    """Return the current month in UTC as ``YYYY-MM``."""
    return datetime.now(UTC).strftime("%Y-%m")


def cost_usd(input_tokens: int, output_tokens: int, model: str) -> float:
    """Convert token counts + model to USD using :data:`_MODEL_RATES`.

    Unknown models fall back to Sonnet rates so we overestimate rather
    than undercount — safer for a budget guardrail.
    """
    in_rate, out_rate = _MODEL_RATES.get(model, _FALLBACK_RATE)
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


class BudgetExceededError(Exception):
    """Raised by :meth:`BudgetTracker.check_available` callers to signal 429."""


class BudgetTracker:
    """Async wrapper around a DynamoDB usage counter.

    ``boto3`` is sync — we push every call through ``asyncio.to_thread`` so
    the FastAPI event loop is never blocked by the network round-trip.
    """

    def __init__(
        self,
        table_name: str,
        monthly_limit_usd: float = 5.0,
        *,
        region_name: str = "eu-west-2",
        dynamodb_client: object | None = None,
    ) -> None:
        """Initialise the tracker.

        Args:
            table_name: DynamoDB table (created by Terraform as
                ``fpl-agent-usage-{env}``).
            monthly_limit_usd: Spend cap. Requests are rejected once
                ``total_cost_usd >= monthly_limit_usd``.
            region_name: AWS region for the DynamoDB client.
            dynamodb_client: Optional pre-built boto3 DynamoDB client (used
                by tests to inject a moto-backed fixture). When ``None``, a
                fresh client is created on demand.
        """
        self._table_name = table_name
        self._limit = monthly_limit_usd
        self._region = region_name
        self._client = dynamodb_client or boto3.client("dynamodb", region_name=region_name)

    @property
    def monthly_limit_usd(self) -> float:
        return self._limit

    async def check_available(self) -> tuple[bool, float]:
        """Return ``(has_budget, current_spend_usd)`` for the current month.

        Also lazy-creates the month row if it does not yet exist, so the
        first request of a new month always succeeds.
        """
        month = _current_month()
        await self._ensure_month_row(month)
        spend = await asyncio.to_thread(self._fetch_cost, month)
        return spend < self._limit, spend

    async def record_usage(
        self, input_tokens: int, output_tokens: int, model: str
    ) -> float:
        """Atomically add one LLM call's usage to the monthly totals.

        Returns the new running cost (post-increment). Stamps
        ``exceeded_at`` the first time spend crosses the limit.
        """
        delta = cost_usd(input_tokens, output_tokens, model)
        month = _current_month()
        await self._ensure_month_row(month)
        new_total = await asyncio.to_thread(
            self._increment, month, input_tokens, output_tokens, delta
        )
        if new_total >= self._limit:
            await asyncio.to_thread(self._stamp_exceeded_if_missing, month)
        return new_total

    async def record_batch(self, usage_entries: list[dict]) -> float:
        """Record multiple LLM calls (one graph run's worth) in a single loop.

        Each entry is ``{"model": ..., "input_tokens": ..., "output_tokens": ...}``
        as produced by :func:`fpl_agent.graph.nodes._record_usage`. Returns
        the final running cost.
        """
        running = 0.0
        for entry in usage_entries:
            running = await self.record_usage(
                input_tokens=int(entry.get("input_tokens") or 0),
                output_tokens=int(entry.get("output_tokens") or 0),
                model=str(entry.get("model") or ""),
            )
        return running

    # ------------------------------------------------------------------ internals

    async def _ensure_month_row(self, month: str) -> None:
        """Create the month row if it doesn't exist. Idempotent."""
        try:
            await asyncio.to_thread(
                self._client.put_item,
                TableName=self._table_name,
                Item={
                    "month": {"S": month},
                    "total_input_tokens": {"N": "0"},
                    "total_output_tokens": {"N": "0"},
                    "total_cost_usd": {"N": "0"},
                    "budget_limit_usd": {"N": str(self._limit)},
                    "updated_at": {"S": datetime.now(UTC).isoformat()},
                },
                ConditionExpression="attribute_not_exists(#m)",
                ExpressionAttributeNames={"#m": "month"},
            )
            logger.info("budget: initialised usage row for month=%s", month)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return  # row already exists — expected common case
            raise

    def _fetch_cost(self, month: str) -> float:
        resp = self._client.get_item(
            TableName=self._table_name,
            Key={"month": {"S": month}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return 0.0
        return float(item.get("total_cost_usd", {}).get("N", "0"))

    def _increment(
        self,
        month: str,
        input_tokens: int,
        output_tokens: int,
        cost_delta: float,
    ) -> float:
        resp = self._client.update_item(
            TableName=self._table_name,
            Key={"month": {"S": month}},
            UpdateExpression=(
                "ADD total_input_tokens :it, "
                "total_output_tokens :ot, "
                "total_cost_usd :c "
                "SET updated_at = :ts"
            ),
            ExpressionAttributeValues={
                ":it": {"N": str(int(input_tokens))},
                ":ot": {"N": str(int(output_tokens))},
                ":c": {"N": str(cost_delta)},
                ":ts": {"S": datetime.now(UTC).isoformat()},
            },
            ReturnValues="UPDATED_NEW",
        )
        new_total = resp.get("Attributes", {}).get("total_cost_usd", {}).get("N", "0")
        return float(new_total)

    def _stamp_exceeded_if_missing(self, month: str) -> None:
        """Record the first-crossing timestamp. No-op if already stamped."""
        try:
            self._client.update_item(
                TableName=self._table_name,
                Key={"month": {"S": month}},
                UpdateExpression="SET exceeded_at = :ts",
                ConditionExpression="attribute_not_exists(exceeded_at)",
                ExpressionAttributeValues={":ts": {"S": datetime.now(UTC).isoformat()}},
            )
            logger.warning("budget: monthly cap first crossed for month=%s", month)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return
            raise
