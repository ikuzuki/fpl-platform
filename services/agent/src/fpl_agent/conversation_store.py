"""Short-lived conversation memory keyed by a per-chat ``conversation_id``.

Each conversation keeps its last :data:`MAX_TURNS` turns, each a compact
record of the question and the agent's answer, so a follow-up such as "what
about his fixtures?" can be resolved against the previous turn. Items expire
:data:`TTL_SECONDS` after the last write. DynamoDB deletes expired items
lazily, so expiry is also checked on read.

Read and write failures are logged and swallowed: memory is an enhancement,
and a failure falls back to answering the question on its own.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import boto3

from fpl_agent.models.conversation import Turn

logger = logging.getLogger(__name__)

MAX_TURNS = 3
TTL_SECONDS = 30 * 60
HISTORY_CHAR_CAP = 4000


def render_history(turns: Sequence[Turn]) -> str:
    """Render turns oldest-first for the prompts, dropping the oldest past the cap."""
    if not turns:
        return "None. This is the first question in the conversation."
    blocks = [
        f"Q: {t.question}\n"
        f"Players discussed: {', '.join(t.players) or 'none'}\n"
        f"Answer: {t.analysis}\n"
        f"Recommendation: {t.recommendation}"
        for t in turns
    ]
    while len(blocks) > 1 and sum(len(b) for b in blocks) > HISTORY_CHAR_CAP:
        blocks.pop(0)
    return "\n\n".join(blocks)


def append_turn(history: Sequence[Turn], turn: Turn) -> list[Turn]:
    return [*history, turn][-MAX_TURNS:]


class ConversationStore(Protocol):
    async def load(self, conversation_id: str) -> list[Turn]: ...
    async def save(self, conversation_id: str, turns: Sequence[Turn]) -> None: ...


class InMemoryConversationStore:
    """Process-local store for evals and tests; same expiry rule as DynamoDB."""

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._items: dict[str, tuple[float, list[Turn]]] = {}
        self._clock = clock

    async def load(self, conversation_id: str) -> list[Turn]:
        item = self._items.get(conversation_id)
        if item is None or item[0] <= self._clock():
            return []
        return list(item[1])

    async def save(self, conversation_id: str, turns: Sequence[Turn]) -> None:
        self._items[conversation_id] = (self._clock() + TTL_SECONDS, list(turns))


class DynamoConversationStore:
    """DynamoDB-backed store. Hash key ``conversation_id``; TTL attribute ``expires_at``."""

    def __init__(
        self,
        table_name: str,
        *,
        region_name: str = "eu-west-2",
        client: Any = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.table_name = table_name
        self._client = client or boto3.client("dynamodb", region_name=region_name)
        self._clock = clock

    async def load(self, conversation_id: str) -> list[Turn]:
        try:
            return await asyncio.to_thread(self._load_sync, conversation_id)
        except Exception:
            logger.exception("conversation read failed for %s", conversation_id)
            return []

    def _load_sync(self, conversation_id: str) -> list[Turn]:
        item = self._client.get_item(
            TableName=self.table_name,
            Key={"conversation_id": {"S": conversation_id}},
        ).get("Item")
        if not item or int(item["expires_at"]["N"]) <= self._clock():
            return []
        return [Turn.model_validate(t) for t in json.loads(item["turns"]["S"])]

    async def save(self, conversation_id: str, turns: Sequence[Turn]) -> None:
        try:
            await asyncio.to_thread(self._save_sync, conversation_id, turns)
        except Exception:
            logger.exception("conversation write failed for %s", conversation_id)

    def _save_sync(self, conversation_id: str, turns: Sequence[Turn]) -> None:
        self._client.put_item(
            TableName=self.table_name,
            Item={
                "conversation_id": {"S": conversation_id},
                "turns": {"S": json.dumps([t.model_dump() for t in turns])},
                "expires_at": {"N": str(int(self._clock()) + TTL_SECONDS)},
            },
        )
