"""Unit tests for the BudgetTracker.

Backed by moto — the DynamoDB table is created per-test and thrown away.
No real AWS calls.
"""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from fpl_agent.middleware.budget import BudgetTracker, cost_usd

pytestmark = pytest.mark.unit

TABLE_NAME = "fpl-agent-usage-test"


@pytest.fixture
def dynamo_client():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="eu-west-2")
        client.create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[{"AttributeName": "month", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "month", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client


def test_cost_calculation_for_haiku() -> None:
    # 1000 input + 500 output at Haiku 4.5 rates ($1/$5 per MTok):
    # 1000/1e6 * 1 + 500/1e6 * 5 = 0.001 + 0.0025 = 0.0035
    assert cost_usd(1000, 500, "claude-haiku-4-5") == pytest.approx(0.0035)


def test_cost_calculation_for_sonnet() -> None:
    # 1000 input + 500 output at Sonnet 4.6 rates ($3/$15 per MTok):
    # 1000/1e6 * 3 + 500/1e6 * 15 = 0.003 + 0.0075 = 0.0105
    assert cost_usd(1000, 500, "claude-sonnet-4-6") == pytest.approx(0.0105)


def test_cost_calculation_unknown_model_falls_back_to_sonnet_rates() -> None:
    # Fallback must not undercount.
    fallback = cost_usd(1000, 500, "claude-opus-unknown")
    sonnet = cost_usd(1000, 500, "claude-sonnet-4-6")
    assert fallback == pytest.approx(sonnet)


@pytest.mark.asyncio
async def test_check_available_lazy_creates_month_row(dynamo_client) -> None:
    tracker = BudgetTracker(TABLE_NAME, monthly_limit_usd=5.0, dynamodb_client=dynamo_client)
    available, spend = await tracker.check_available()
    assert available is True
    assert spend == pytest.approx(0.0)

    # Row should now exist (check by scanning).
    resp = dynamo_client.scan(TableName=TABLE_NAME)
    assert resp["Count"] == 1


@pytest.mark.asyncio
async def test_check_available_under_limit(dynamo_client) -> None:
    tracker = BudgetTracker(TABLE_NAME, monthly_limit_usd=5.0, dynamodb_client=dynamo_client)
    await tracker.record_usage(1000, 500, "claude-haiku-4-5")
    available, spend = await tracker.check_available()
    assert available is True
    assert spend == pytest.approx(0.0035, rel=1e-3)


@pytest.mark.asyncio
async def test_check_available_blocks_over_limit(dynamo_client) -> None:
    # Tiny limit so one Sonnet call blows it.
    tracker = BudgetTracker(TABLE_NAME, monthly_limit_usd=0.001, dynamodb_client=dynamo_client)
    await tracker.record_usage(1000, 500, "claude-sonnet-4-6")  # ~$0.0105
    available, spend = await tracker.check_available()
    assert available is False
    assert spend > 0.001


@pytest.mark.asyncio
async def test_record_usage_accumulates_atomically(dynamo_client) -> None:
    tracker = BudgetTracker(TABLE_NAME, monthly_limit_usd=5.0, dynamodb_client=dynamo_client)
    for _ in range(5):
        await tracker.record_usage(100, 50, "claude-haiku-4-5")
    _, spend = await tracker.check_available()
    # 5 calls × (100 * 1 + 50 * 5) / 1e6 = 5 × 0.00035 = 0.00175
    assert spend == pytest.approx(0.00175, rel=1e-3)


@pytest.mark.asyncio
async def test_record_batch_sums_mixed_models(dynamo_client) -> None:
    tracker = BudgetTracker(TABLE_NAME, monthly_limit_usd=5.0, dynamodb_client=dynamo_client)
    entries = [
        {"model": "claude-haiku-4-5", "input_tokens": 1000, "output_tokens": 500},
        {"model": "claude-sonnet-4-6", "input_tokens": 2000, "output_tokens": 1000},
    ]
    total = await tracker.record_batch(entries)
    # Haiku: 0.001 + 0.0025 = 0.0035
    # Sonnet: 0.006 + 0.015 = 0.021
    assert total == pytest.approx(0.0245, rel=1e-3)


@pytest.mark.asyncio
async def test_exceeded_at_stamped_on_first_crossing(dynamo_client) -> None:
    tracker = BudgetTracker(TABLE_NAME, monthly_limit_usd=0.001, dynamodb_client=dynamo_client)
    await tracker.record_usage(1000, 500, "claude-sonnet-4-6")
    # Verify the exceeded_at column is set.
    resp = dynamo_client.scan(TableName=TABLE_NAME)
    items = resp["Items"]
    assert items, "month row missing"
    assert "exceeded_at" in items[0], "exceeded_at should be stamped when limit crossed"
