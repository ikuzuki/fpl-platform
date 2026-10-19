"""Unit tests for conversation memory."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from fpl_agent.conversation_store import (
    HISTORY_CHAR_CAP,
    MAX_TURNS,
    TTL_SECONDS,
    DynamoConversationStore,
    InMemoryConversationStore,
    append_turn,
    render_history,
)
from fpl_agent.models.conversation import ANALYSIS_CHARS, Turn
from fpl_agent.models.responses import ComparisonResult, PlayerAnalysis, ScoutReport

pytestmark = pytest.mark.unit


def _player(name: str) -> PlayerAnalysis:
    return PlayerAnalysis(
        player_name=name,
        position="MID",
        price=10.0,
        form=5.0,
        fixture_outlook="green",
        verdict="ok",
        confidence=0.8,
    )


def _turn(question: str = "How is Saka doing?") -> Turn:
    return Turn(
        question=question, players=["Saka"], analysis="Saka has 133 points.", recommendation="Keep."
    )


def test_turn_from_report_dedupes_players_and_truncates_analysis() -> None:
    report = ScoutReport(
        question="Saka or Palmer?",
        analysis="x" * (ANALYSIS_CHARS + 50),
        players=[_player("Saka"), _player("Palmer")],
        comparison=ComparisonResult(
            players=[_player("Saka"), _player("Palmer")], winner="Saka", reasoning="form"
        ),
        recommendation="Pick Saka.",
    )

    turn = Turn.from_report("Saka or Palmer?", report)

    assert turn.players == ["Saka", "Palmer"]
    assert len(turn.analysis) == ANALYSIS_CHARS


def test_append_turn_keeps_only_the_latest_turns() -> None:
    history: list[Turn] = []
    for i in range(MAX_TURNS + 2):
        history = append_turn(history, _turn(f"q{i}"))

    assert [t.question for t in history] == [f"q{i}" for i in range(2, MAX_TURNS + 2)]


def test_render_history_says_none_for_a_new_conversation() -> None:
    assert render_history([]).startswith("None.")


def test_render_history_drops_oldest_turns_past_the_cap() -> None:
    long = Turn(question="old", players=[], analysis="a" * HISTORY_CHAR_CAP, recommendation="r")
    rendered = render_history([long, _turn("recent")])

    assert "Q: old" not in rendered
    assert "Q: recent" in rendered


@pytest.mark.asyncio
async def test_in_memory_store_expires_after_ttl() -> None:
    now = [1000.0]
    store = InMemoryConversationStore(clock=lambda: now[0])
    await store.save("c1", [_turn()])

    assert len(await store.load("c1")) == 1
    now[0] += TTL_SECONDS + 1
    assert await store.load("c1") == []


@pytest.mark.asyncio
async def test_dynamo_store_round_trips_and_ignores_expired_items() -> None:
    client = MagicMock()
    store = DynamoConversationStore("t", client=client, clock=lambda: 1000.0)

    await store.save("c1", [_turn()])
    item = client.put_item.call_args.kwargs["Item"]
    assert item["expires_at"] == {"N": str(1000 + TTL_SECONDS)}

    client.get_item.return_value = {"Item": item}
    assert [t.question for t in await store.load("c1")] == ["How is Saka doing?"]

    expired = {**item, "expires_at": {"N": "999"}}
    client.get_item.return_value = {"Item": expired}
    assert await store.load("c1") == []


@pytest.mark.asyncio
async def test_dynamo_store_fails_open() -> None:
    client = MagicMock()
    client.get_item.side_effect = RuntimeError("no table")
    client.put_item.side_effect = RuntimeError("no table")
    store = DynamoConversationStore("t", client=client)

    assert await store.load("c1") == []
    await store.save("c1", [_turn()])  # must not raise


def test_dynamo_item_turns_are_plain_json() -> None:
    client = MagicMock()
    store = DynamoConversationStore("t", client=client, clock=lambda: 0.0)
    store._save_sync("c1", [_turn()])

    turns = json.loads(client.put_item.call_args.kwargs["Item"]["turns"]["S"])
    assert turns[0]["players"] == ["Saka"]
