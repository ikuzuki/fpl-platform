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


def _raw_response(picks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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


def _mock_lambda_payload(body: Any, *, function_error: str | None = None) -> MagicMock:
    payload = MagicMock()
    payload.read.return_value = (
        json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    )
    response: dict[str, Any] = {"Payload": payload}
    if function_error:
        response["FunctionError"] = function_error
    client = MagicMock()
    client.invoke.return_value = response
    return client


def _mock_neon(rows: list[dict[str, Any]]) -> MagicMock:
    neon = MagicMock()
    neon.fetch = AsyncMock(return_value=rows)
    return neon


@pytest.mark.asyncio
async def test_load_user_squad_enriches_picks_with_neon_metadata() -> None:
    raw = _raw_response()
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
    lambda_client = _mock_lambda_payload(raw)
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
    raw = _raw_response(picks=_raw_picks(999_999))
    lambda_client = _mock_lambda_payload(raw)
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
async def test_load_user_squad_raises_squad_not_found_on_team_error() -> None:
    """Lambda surfaces TeamNotFoundError → loader raises SquadNotFoundError."""
    lambda_client = _mock_lambda_payload(
        {"errorType": "TeamNotFoundError", "errorMessage": "team 99999 not found"},
        function_error="Unhandled",
    )
    neon = _mock_neon([])

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadNotFoundError),
    ):
        await load_user_squad(team_id=99999, gameweek=33, neon=neon, function_name="fn")


@pytest.mark.asyncio
async def test_load_user_squad_raises_squad_fetch_error_on_other_lambda_failures() -> None:
    lambda_client = _mock_lambda_payload(
        {"errorType": "FPLAccessError", "errorMessage": "403 forbidden"},
        function_error="Unhandled",
    )
    neon = _mock_neon([])

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadFetchError),
    ):
        await load_user_squad(team_id=1, gameweek=33, neon=neon, function_name="fn")


@pytest.mark.asyncio
async def test_load_user_squad_raises_squad_not_found_on_empty_picks() -> None:
    """An empty picks array (future GW, never-set team) → SquadNotFoundError."""
    raw = {"picks": [], "active_chip": None, "entry_history": {}}
    lambda_client = _mock_lambda_payload(raw)
    neon = _mock_neon([])

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadNotFoundError),
    ):
        await load_user_squad(team_id=1, gameweek=99, neon=neon, function_name="fn")


@pytest.mark.asyncio
async def test_load_user_squad_invokes_lambda_with_correct_payload() -> None:
    raw = _raw_response()
    lambda_client = _mock_lambda_payload(raw)
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
async def test_load_user_squad_wraps_neon_failures_as_squad_fetch_error() -> None:
    raw = _raw_response()
    lambda_client = _mock_lambda_payload(raw)
    neon = MagicMock()
    neon.fetch = AsyncMock(side_effect=RuntimeError("connection lost"))

    with (
        patch("fpl_agent.squad_loader.boto3.client", return_value=lambda_client),
        pytest.raises(SquadFetchError, match="metadata lookup failed"),
    ):
        await load_user_squad(team_id=1, gameweek=33, neon=neon, function_name="fn")
