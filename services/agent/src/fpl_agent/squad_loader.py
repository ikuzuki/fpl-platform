"""Load and enrich a user's FPL squad for the ``GET /team`` endpoint.

The team-fetcher Lambda returns the FPL API's raw shape — picks carry only
``element`` IDs, no names. Both consumers of a squad (the dashboard's squad
card and the agent's recommender) need names + team + price, so this module
joins the raw response against Neon ``player_embeddings`` and serves an
enriched :class:`UserSquad`.

Errors map onto the API:

* :class:`SquadNotFoundError` — FPL returned 404 for that team_id (Lambda
  surfaces ``TeamNotFoundError``); the route translates to HTTP 404.
* :class:`SquadFetchError` — Lambda invoke failed, FPL was rate-limited, or
  Neon raised. Route translates to HTTP 502.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, cast

import boto3

from fpl_agent.models.responses import SquadPick, UserSquad
from fpl_lib.clients.neon import NeonClient

logger = logging.getLogger(__name__)


class SquadNotFoundError(Exception):
    """The FPL API does not have a manager with the requested team_id."""


class SquadFetchError(Exception):
    """The squad could not be loaded for a transient reason (FPL/Lambda/Neon)."""


def _invoke_team_fetcher_sync(function_name: str, team_id: int, gameweek: int) -> dict[str, Any]:
    """Sync boto3 invocation; called via ``asyncio.to_thread`` from the route.

    boto3 itself is sync — wrapping with ``to_thread`` keeps the event loop
    responsive while the request is in flight (FPL can take 1-2s under load).

    Returns the *unwrapped* ``body`` dict. The team-fetcher uses ``RunHandler``
    which envelopes every response as ``{"statusCode": N, "body": <payload>}`` —
    that envelope is what API Gateway / Function URL proxy integrations expect,
    but we invoke the Lambda directly (not via HTTP), so we peel it off here
    before returning. Non-200 statuses are surfaced as ``SquadFetchError``.
    """
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"team_id": team_id, "gameweek": gameweek}).encode("utf-8"),
    )
    raw = cast(dict[str, Any], json.loads(response["Payload"].read().decode("utf-8")))

    status_code = raw.get("statusCode")
    body = raw.get("body") if isinstance(raw.get("body"), dict) else None

    if status_code != 200 or body is None:
        # RunHandler catches TeamNotFoundError as a generic Exception → 500 with
        # `body.error = str(e)` where str(TeamNotFoundError(<id>)) is just the ID,
        # so we can't reliably distinguish 404-flavoured failures here. An empty
        # picks list (handled in ``load_user_squad``) covers the benign cases
        # (future GW, never-set team); everything else is an upstream fetch error.
        err = (body or {}).get("error") if isinstance(body, dict) else None
        raise SquadFetchError(
            f"team-fetcher returned statusCode={status_code}: {err or raw!r}"
        )

    return body


async def _fetch_player_metadata(
    neon: NeonClient, element_ids: list[int]
) -> dict[int, dict[str, Any]]:
    """Pull web_name / team_name / price for the squad's 15 element IDs in one query."""
    rows = await neon.fetch(
        """
        SELECT player_id, web_name, team_name, price, position
        FROM player_embeddings
        WHERE player_id = ANY($1::int[])
        """,
        element_ids,
    )
    return {int(row["player_id"]): dict(row) for row in rows}


def _enrich_pick(raw_pick: dict[str, Any], meta: dict[str, Any] | None) -> SquadPick:
    """Build a :class:`SquadPick` from one raw FPL pick + the matching Neon row.

    If a player isn't in our DB (brand-new transfer not yet run through the
    embeddings sync), fall back to a placeholder so the rest of the squad
    still renders. The dashboard surfaces the unknown player; the recommender
    sees the IDs in case it wants to flag the gap.
    """
    if meta is None:
        return SquadPick(
            element_id=raw_pick["element"],
            web_name=f"#{raw_pick['element']}",
            team_name="Unknown",
            position=raw_pick["position"],
            element_type=raw_pick.get("element_type", 0),
            multiplier=raw_pick["multiplier"],
            is_captain=raw_pick["is_captain"],
            is_vice_captain=raw_pick["is_vice_captain"],
            price=0.0,
        )
    return SquadPick(
        element_id=raw_pick["element"],
        web_name=meta["web_name"],
        team_name=meta["team_name"],
        position=raw_pick["position"],
        element_type=raw_pick.get("element_type", 0),
        multiplier=raw_pick["multiplier"],
        is_captain=raw_pick["is_captain"],
        is_vice_captain=raw_pick["is_vice_captain"],
        price=float(meta["price"]),
    )


async def load_user_squad(
    *,
    team_id: int,
    gameweek: int,
    neon: NeonClient,
    function_name: str,
) -> UserSquad:
    """Fetch and enrich one user's squad. The single entry point used by the route."""
    raw = await asyncio.to_thread(_invoke_team_fetcher_sync, function_name, team_id, gameweek)

    picks_raw: list[dict[str, Any]] = raw.get("picks", [])
    if not picks_raw:
        # No picks but no error — most likely a manager who has never set a
        # team, or a future gameweek. Treat as "not found" so the UI shows
        # the same friendly state as a wrong team_id.
        raise SquadNotFoundError(f"no picks for team_id={team_id} GW{gameweek}")

    element_ids = [int(p["element"]) for p in picks_raw]
    try:
        metadata = await _fetch_player_metadata(neon, element_ids)
    except Exception as exc:
        logger.exception("Neon metadata lookup failed for team %d GW%d", team_id, gameweek)
        raise SquadFetchError(f"metadata lookup failed: {exc}") from exc

    picks = [
        _enrich_pick(raw_pick, metadata.get(int(raw_pick["element"]))) for raw_pick in picks_raw
    ]

    eh: dict[str, Any] = raw.get("entry_history") or {}
    return UserSquad(
        team_id=team_id,
        gameweek=gameweek,
        picks=picks,
        # FPL serves money in tenths of millions on the wire (`bank=32` ↔ £3.2m).
        bank=int(eh.get("bank", 0)) / 10.0,
        total_value=int(eh.get("value", 0)) / 10.0,
        active_chip=raw.get("active_chip"),
        overall_rank=eh.get("overall_rank"),
        total_points=int(eh.get("total_points", 0)),
    )
