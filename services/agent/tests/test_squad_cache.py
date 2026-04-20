"""Unit tests for the DynamoDB squad cache."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from fpl_agent.squad_cache import DynamoSquadCache, _key

pytestmark = pytest.mark.unit


def _body() -> dict[str, Any]:
    return {
        "picks": [{"element": 341, "position": 1, "is_captain": True}],
        "active_chip": None,
        "entry_history": {"event": 33, "bank": 0, "value": 1000},
    }


def _mock_client_empty() -> MagicMock:
    client = MagicMock()
    client.get_item.return_value = {}
    client.put_item.return_value = {}
    return client


def _mock_client_with(body: dict[str, Any]) -> MagicMock:
    client = MagicMock()
    client.get_item.return_value = {
        "Item": {
            "team_gameweek": {"S": "5767400#33"},
            "body": {"S": json.dumps(body)},
        }
    }
    client.put_item.return_value = {}
    return client


def test_key_format() -> None:
    assert _key(5767400, 33) == "5767400#33"


@pytest.mark.asyncio
async def test_get_returns_parsed_body_on_hit() -> None:
    client = _mock_client_with(_body())
    cache = DynamoSquadCache("fpl-squad-cache-test", client=client)

    got = await cache.get(5767400, 33)

    assert got == _body()
    client.get_item.assert_called_once_with(
        TableName="fpl-squad-cache-test",
        Key={"team_gameweek": {"S": "5767400#33"}},
        ConsistentRead=False,
    )


@pytest.mark.asyncio
async def test_get_returns_none_on_miss() -> None:
    cache = DynamoSquadCache("tbl", client=_mock_client_empty())
    assert await cache.get(1, 1) is None


@pytest.mark.asyncio
async def test_get_returns_none_when_item_missing_body_attr() -> None:
    """Corrupted row shape — treat as miss rather than blow up the route."""
    client = MagicMock()
    client.get_item.return_value = {"Item": {"team_gameweek": {"S": "1#1"}}}
    cache = DynamoSquadCache("tbl", client=client)
    assert await cache.get(1, 1) is None


@pytest.mark.asyncio
async def test_get_swallows_exceptions() -> None:
    """DynamoDB down must not break the live path — cache is an optimisation."""
    client = MagicMock()
    client.get_item.side_effect = RuntimeError("throttled")
    cache = DynamoSquadCache("tbl", client=client)

    assert await cache.get(1, 1) is None


@pytest.mark.asyncio
async def test_put_writes_json_encoded_body() -> None:
    client = _mock_client_empty()
    cache = DynamoSquadCache("tbl", client=client)

    await cache.put(5767400, 33, _body())

    client.put_item.assert_called_once()
    kwargs = client.put_item.call_args.kwargs
    assert kwargs["TableName"] == "tbl"
    assert kwargs["Item"]["team_gameweek"] == {"S": "5767400#33"}
    assert json.loads(kwargs["Item"]["body"]["S"]) == _body()


@pytest.mark.asyncio
async def test_put_swallows_exceptions() -> None:
    """Cache write failure must not surface to the caller."""
    client = MagicMock()
    client.put_item.side_effect = RuntimeError("throttled")
    cache = DynamoSquadCache("tbl", client=client)

    # Must not raise.
    await cache.put(1, 1, _body())
