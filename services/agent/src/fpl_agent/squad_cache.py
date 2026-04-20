"""Write-once DynamoDB cache for raw FPL squad responses.

Squad picks for a given ``(team_id, gameweek)`` pair are immutable once the
gameweek deadline passes — the user's lineup is locked and FPL's
``/entry/{team_id}/event/{gw}/picks/`` endpoint returns the same payload
forever after. That makes this cache the simplest possible shape: write on
first successful fetch, read forever thereafter, no TTL, no invalidation.

The cache also insulates the Lambda from intermittent FPL / Fastly IP blocks
— once a squad is cached, subsequent reads never touch FPL, so the user can
still load their squad even while the AWS egress IP is flagged.

Failures on either side (read or write) are logged and swallowed. The cache
is an optimisation, not a correctness dependency — any failure must fall
through to the live path rather than breaking ``/team``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol

import boto3

logger = logging.getLogger(__name__)


class SquadCache(Protocol):
    """Interface for a squad cache — used so tests can swap in an in-memory fake."""

    async def get(self, team_id: int, gameweek: int) -> dict[str, Any] | None: ...
    async def put(self, team_id: int, gameweek: int, body: dict[str, Any]) -> None: ...


class DynamoSquadCache:
    """DynamoDB-backed :class:`SquadCache`.

    Hash key: ``team_gameweek`` (string ``"{team_id}#{gameweek}"``).
    One payload attribute: ``body`` (JSON-encoded string of the raw
    team-fetcher response). boto3 is synchronous; every public method
    wraps the call with :func:`asyncio.to_thread` to keep the event loop
    responsive during the sub-10ms DynamoDB round trip.
    """

    def __init__(self, table_name: str, *, client: Any = None) -> None:
        self.table_name = table_name
        self._client = client or boto3.client("dynamodb")

    async def get(self, team_id: int, gameweek: int) -> dict[str, Any] | None:
        try:
            return await asyncio.to_thread(self._get_sync, team_id, gameweek)
        except Exception:
            logger.exception("squad cache read failed for team %d GW%d", team_id, gameweek)
            return None

    def _get_sync(self, team_id: int, gameweek: int) -> dict[str, Any] | None:
        response = self._client.get_item(
            TableName=self.table_name,
            Key={"team_gameweek": {"S": _key(team_id, gameweek)}},
            ConsistentRead=False,
        )
        item = response.get("Item")
        if not item or "body" not in item:
            return None
        body: dict[str, Any] = json.loads(item["body"]["S"])
        return body

    async def put(self, team_id: int, gameweek: int, body: dict[str, Any]) -> None:
        try:
            await asyncio.to_thread(self._put_sync, team_id, gameweek, body)
        except Exception:
            logger.exception("squad cache write failed for team %d GW%d", team_id, gameweek)

    def _put_sync(self, team_id: int, gameweek: int, body: dict[str, Any]) -> None:
        self._client.put_item(
            TableName=self.table_name,
            Item={
                "team_gameweek": {"S": _key(team_id, gameweek)},
                "body": {"S": json.dumps(body)},
            },
        )


def _key(team_id: int, gameweek: int) -> str:
    return f"{team_id}#{gameweek}"
