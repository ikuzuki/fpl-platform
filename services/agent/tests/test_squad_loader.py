"""Unit tests for the squad loader (FPL → Lambda → Neon enrichment)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fpl_agent.models.responses import UserSquad
from fpl_agent.squad_loader import (
    SquadFetchError,
    SquadNotFoundError,
    load_user_squad,
)

pytestmark = pytest.mark.unit


def _raw_picks(*element_ids: int) -> list[dict[str, Any]]:
    """Build a list of raw FPL picks for the given element IDs.

    Mirrors the on-the-wire shape captured against team_id=5767400 GW33 —
    ``element_type`` is included because it's present in the real API even
    though the legacy fixture omitted it.
    """
    out = []
    for i, eid in enumerate(element_ids, start=1):
        out.append(
            {
                "element": eid,
                "position": i,
                "multiplier": 2 if i == 1 else 1,
                "is_captain": i == 1,
                "is_vice_captain": i == 2,
                "element_type": (i % 4) + 1,
            }
        )
    return out


def _raw_body(picks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The unwrapped FPL payload (what ``team_fetcher.main`` returns)."""
    return {
        "picks": picks if picks is not None else _raw_picks(341, 430, 235),
        "active_chip": "freehit",
        "automatic_subs": [],
        "entry_history": {
            "event": 33,
            "points": 65,
            "total_points": 1871,
            "rank": 50000,
            "overall_rank": 493581,
            "bank": 32,  # tenths-of-millions on the wire ↔ £3.2m
            "value": 1031,  # ↔ £103.1m
        },
    }


def _run_handler_envelope(body: dict[str, Any], status_code: int = 200) -> dict[str, Any]:
    """Wrap a body the way ``fpl_lib.core.run_handler.RunHandler`` does on the wire."""
    return {"statusCode": status_code, "body": body}


def _mock_lambda_client(payload: dict[str, Any]) -> MagicMock:
    """Build a boto3 Lambda client mock whose ``invoke`` returns *payload* verbatim.

    ``payload`` is the whole Lambda return value — in production that's always
    the ``RunHandler`` envelope ``{"statusCode": N, "body": {...}}``. Tests use
    ``_run_handler_envelope`` to construct it.
    """
    payload_mock = MagicMock()
    payload_mock.read.return_value = json.dumps(payload).encode("utf-8")
    client = MagicMock()
    client.invoke.return_value = {"Payload": payload_mock}
    return client


def _mock_neon(rows: list[dict[str, Any]]) -> MagicMock:
    neon = MagicMock()
    neon.fetch = AsyncMock(return_value=rows)
    return neon


@pytest.mark.asyncio
async def test_load_user_squad_enriches_picks_with_neon_metadata() -> None:
    raw = _run_handler_envelope(_raw_body())
    metadata_rows = [
        {
            "player_id": 341,
            "web_name": "Raya",
            "team_name": "Arsenal",
            "price": 5.5,
            "position": "GKP",
        },
        {
            "player_id": 430,
            "web_name": "Haaland",
            "team_name": "Man City",
            "price": 14.2,
            "position": "FWD",
        },
        {
            "player_id": 235,
            "web_name": "Saka",
            "team_name": "Arsenal",
            "price": 10.5,
            "position": "MID",
        },
    ]
    lambda_client = _mock_lambda_client(raw)
    neon = _mock_neon(metadata_rows)

    with patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client):
        squad = await load_user_squad(
            team_id=5767400,
            gameweek=33,
            neon=neon,
            function_name="fpl-dev-team-fetcher",
        )

    assert isinstance(squad, UserSquad)
    assert squad.team_id == 5767400
    assert squad.gameweek == 33
    # Money fields converted from tenths-of-millions to whole millions.
    assert squad.bank == 3.2
    assert squad.total_value == 103.1
    assert squad.active_chip == "freehit"
    assert squad.overall_rank == 493581

    # Picks enriched with web_name / team_name / price from Neon.
    by_id = {p.element_id: p for p in squad.picks}
    assert by_id[341].web_name == "Raya"
    assert by_id[430].web_name == "Haaland"
    assert by_id[430].price == 14.2
    # Captain comes from the raw FPL data (first pick in our fixture).
    captain = next(p for p in squad.picks if p.is_captain)
    assert captain.element_id == 341


@pytest.mark.asyncio
async def test_load_user_squad_falls_back_for_unknown_player() -> None:
    """If a pick's element isn't in Neon (brand-new transfer), use a placeholder."""
    raw = _run_handler_envelope(_raw_body(picks=_raw_picks(999_999)))
    lambda_client = _mock_lambda_client(raw)
    neon = _mock_neon([])  # no rows match

    with patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client):
        squad = await load_user_squad(
            team_id=1,
            gameweek=33,
            neon=neon,
            function_name="fn",
        )

    assert squad.picks[0].web_name == "#999999"
    assert squad.picks[0].team_name == "Unknown"
    assert squad.picks[0].price == 0.0


@pytest.mark.asyncio
async def test_load_user_squad_raises_squad_fetch_error_on_non_200_status() -> None:
    """RunHandler returns ``statusCode: 500`` when the handler raises — loader surfaces as SquadFetchError."""
    raw = _run_handler_envelope({"error": "99999"}, status_code=500)
    lambda_client = _mock_lambda_client(raw)
    neon = _mock_neon([])

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadFetchError, match="statusCode=500"),
    ):
        await load_user_squad(team_id=99999, gameweek=33, neon=neon, function_name="fn")


@pytest.mark.asyncio
async def test_load_user_squad_raises_squad_fetch_error_on_bad_request() -> None:
    """RunHandler returns ``statusCode: 400`` for ValueError — also a fetch failure from the loader's POV."""
    raw = _run_handler_envelope({"error": "missing team_id"}, status_code=400)
    lambda_client = _mock_lambda_client(raw)
    neon = _mock_neon([])

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadFetchError, match="statusCode=400"),
    ):
        await load_user_squad(team_id=1, gameweek=33, neon=neon, function_name="fn")


@pytest.mark.asyncio
async def test_load_user_squad_raises_squad_not_found_on_empty_picks() -> None:
    """An empty picks array (future GW, never-set team) → SquadNotFoundError."""
    raw = _run_handler_envelope({"picks": [], "active_chip": None, "entry_history": {}})
    lambda_client = _mock_lambda_client(raw)
    neon = _mock_neon([])

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadNotFoundError),
    ):
        await load_user_squad(team_id=1, gameweek=99, neon=neon, function_name="fn")


@pytest.mark.asyncio
async def test_load_user_squad_invokes_lambda_with_correct_payload() -> None:
    raw = _run_handler_envelope(_raw_body())
    lambda_client = _mock_lambda_client(raw)
    neon = _mock_neon(
        [
            {"player_id": eid, "web_name": "p", "team_name": "t", "price": 5.0, "position": "MID"}
            for eid in (341, 430, 235)
        ]
    )

    with patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client):
        await load_user_squad(
            team_id=5767400, gameweek=33, neon=neon, function_name="fpl-dev-team-fetcher"
        )

    call_kwargs = lambda_client.invoke.call_args.kwargs
    assert call_kwargs["FunctionName"] == "fpl-dev-team-fetcher"
    assert call_kwargs["InvocationType"] == "RequestResponse"
    assert json.loads(call_kwargs["Payload"]) == {"team_id": 5767400, "gameweek": 33}


@pytest.mark.asyncio
async def test_load_user_squad_unwraps_run_handler_envelope() -> None:
    """Regression: ``RunHandler`` wraps every response as ``{"statusCode": N, "body": ...}``.

    Before this guard, the loader treated the envelope as the body, so
    ``raw.get("picks")`` was always ``None`` and every valid team returned
    ``SquadNotFoundError``. The loader must peel off the envelope.
    """
    body = _raw_body()
    envelope = _run_handler_envelope(body)
    lambda_client = _mock_lambda_client(envelope)
    neon = _mock_neon(
        [
            {"player_id": eid, "web_name": "p", "team_name": "t", "price": 5.0, "position": "MID"}
            for eid in (341, 430, 235)
        ]
    )

    with patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client):
        squad = await load_user_squad(team_id=1, gameweek=33, neon=neon, function_name="fn")

    # All three picks from the body are loaded — *not* zero picks from the envelope.
    assert len(squad.picks) == 3


class _FakeCache:
    """Dict-backed :class:`SquadCache` for tests — no DynamoDB, no asyncio.to_thread."""

    def __init__(self, initial: dict[tuple[int, int], dict[str, Any]] | None = None) -> None:
        self._store: dict[tuple[int, int], dict[str, Any]] = dict(initial or {})
        self.gets: list[tuple[int, int]] = []
        self.puts: list[tuple[int, int, dict[str, Any]]] = []

    async def get(self, team_id: int, gameweek: int) -> dict[str, Any] | None:
        self.gets.append((team_id, gameweek))
        return self._store.get((team_id, gameweek))

    async def put(self, team_id: int, gameweek: int, body: dict[str, Any]) -> None:
        self.puts.append((team_id, gameweek, body))
        self._store[(team_id, gameweek)] = body


@pytest.mark.asyncio
async def test_load_user_squad_reads_from_cache_and_skips_lambda() -> None:
    """Cache hit means zero Lambda invokes — the whole point of the cache."""
    cache = _FakeCache(initial={(5767400, 33): _raw_body()})
    # A broken lambda client proves the cache short-circuits before boto3 is touched.
    lambda_client = MagicMock()
    lambda_client.invoke.side_effect = AssertionError("lambda must not be invoked on cache hit")
    neon = _mock_neon(
        [
            {"player_id": eid, "web_name": "p", "team_name": "t", "price": 5.0, "position": "MID"}
            for eid in (341, 430, 235)
        ]
    )

    with patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client):
        squad = await load_user_squad(
            team_id=5767400, gameweek=33, neon=neon, function_name="fn", cache=cache
        )

    assert len(squad.picks) == 3
    assert cache.gets == [(5767400, 33)]
    assert cache.puts == []  # cache was already warm, no write needed
    lambda_client.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_load_user_squad_writes_cache_on_miss_after_successful_fetch() -> None:
    """Cache miss → Lambda → cache write (so the next call is a hit)."""
    cache = _FakeCache()
    body = _raw_body()
    lambda_client = _mock_lambda_client(_run_handler_envelope(body))
    neon = _mock_neon(
        [
            {"player_id": eid, "web_name": "p", "team_name": "t", "price": 5.0, "position": "MID"}
            for eid in (341, 430, 235)
        ]
    )

    with patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client):
        await load_user_squad(
            team_id=5767400, gameweek=33, neon=neon, function_name="fn", cache=cache
        )

    assert cache.puts == [(5767400, 33, body)]
    lambda_client.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_load_user_squad_does_not_cache_empty_picks() -> None:
    """Empty picks means ``never set`` or ``future GW`` — caching would freeze that forever."""
    cache = _FakeCache()
    empty_body = {"picks": [], "active_chip": None, "entry_history": {}}
    lambda_client = _mock_lambda_client(_run_handler_envelope(empty_body))
    neon = _mock_neon([])

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadNotFoundError),
    ):
        await load_user_squad(team_id=1, gameweek=99, neon=neon, function_name="fn", cache=cache)

    assert cache.puts == []  # did NOT persist the empty body


@pytest.mark.asyncio
async def test_load_user_squad_works_when_cache_is_none() -> None:
    """Passing ``cache=None`` must behave exactly like the pre-cache implementation."""
    lambda_client = _mock_lambda_client(_run_handler_envelope(_raw_body()))
    neon = _mock_neon(
        [
            {"player_id": eid, "web_name": "p", "team_name": "t", "price": 5.0, "position": "MID"}
            for eid in (341, 430, 235)
        ]
    )

    with patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client):
        squad = await load_user_squad(
            team_id=1, gameweek=33, neon=neon, function_name="fn", cache=None
        )

    assert len(squad.picks) == 3
    lambda_client.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_load_user_squad_wraps_neon_failures_as_squad_fetch_error() -> None:
    raw = _run_handler_envelope(_raw_body())
    lambda_client = _mock_lambda_client(raw)
    neon = MagicMock()
    neon.fetch = AsyncMock(side_effect=RuntimeError("connection lost"))

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadFetchError, match="metadata lookup failed"),
    ):
        await load_user_squad(team_id=1, gameweek=33, neon=neon, function_name="fn")
