"""Async tool implementations for the scout report agent.

The :func:`make_tools` factory takes a live :class:`NeonClient` and returns a
dict of six callable tools, each with the client captured in a closure. The
graph's ``tool_executor`` node dispatches calls from the planner's plan into
this dict by name.

Every tool:

* Is ``async`` so the executor can gather calls concurrently.
* Is wrapped with Langfuse ``@observe`` for tracing.
* Returns a JSON-serialisable ``dict`` (the raw Postgres rows, coerced to
  ordinary dicts — the recommender does narrative shaping).
* Raises :class:`ToolError` on unrecoverable failures. Transient issues are
  captured by the executor's ``return_exceptions=True`` so one bad tool does
  not cancel its siblings.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, cast

import asyncpg
import boto3

from fpl_lib.clients.neon import NeonClient
from fpl_lib.observability import observe

logger = logging.getLogger(__name__)


ToolFn = Callable[..., Awaitable[dict[str, Any] | list[dict[str, Any]]]]


class ToolError(RuntimeError):
    """Raised by a tool when it fails in a way the executor should record."""


# ----------------------------------------------------------------------------
# Row helpers
# ----------------------------------------------------------------------------
# The ``embedding`` column is a 384-dim vector — useful for similarity search
# internally, but orders of magnitude larger than the rest of the row and of
# no value to the recommender. Strip it from every response.

_OMIT_COLUMNS = {"embedding"}


def _row_to_dict(row: asyncpg.Record | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: v for k, v in row.items() if k not in _OMIT_COLUMNS}


def _rows_to_dicts(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [cast(dict[str, Any], _row_to_dict(r)) for r in rows]


# ----------------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------------
def make_tools(neon: NeonClient) -> dict[str, ToolFn]:
    """Create the six agent tools, each closed over the shared NeonClient.

    Returns a dict keyed by tool name (matching ``ToolCall.name`` literals)
    so the executor can dispatch planner output directly.
    """

    @observe(name="tool.query_player", as_type="tool")
    async def query_player(name: str) -> dict[str, Any]:
        """Look up a single player by name (case-insensitive partial match)."""
        row = await neon.fetch_one(
            """
            SELECT *
            FROM player_embeddings
            WHERE web_name ILIKE $1
            ORDER BY total_points DESC
            LIMIT 1
            """,
            f"%{name}%",
        )
        if row is None:
            raise ToolError(f"No player found matching '{name}'")
        return cast(dict[str, Any], _row_to_dict(row))

    @observe(name="tool.search_similar_players", as_type="tool")
    async def search_similar_players(player_name: str, k: int = 5) -> dict[str, Any]:
        """Find the k players most similar to ``player_name`` by embedding cosine distance."""
        target = await neon.fetch_one(
            """
            SELECT player_id, embedding, web_name
            FROM player_embeddings
            WHERE web_name ILIKE $1
            LIMIT 1
            """,
            f"%{player_name}%",
        )
        if target is None:
            raise ToolError(f"No player found matching '{player_name}'")

        neighbours = await neon.fetch(
            """
            SELECT *, 1 - (embedding <=> $1) AS similarity
            FROM player_embeddings
            WHERE player_id != $2
            ORDER BY embedding <=> $1
            LIMIT $3
            """,
            target["embedding"],
            target["player_id"],
            k,
        )
        return {
            "target": target["web_name"],
            "similar": _rows_to_dicts(neighbours),
        }

    @observe(name="tool.query_players_by_criteria", as_type="tool")
    async def query_players_by_criteria(
        position: str | None = None,
        max_price: float | None = None,
        min_form: float | None = None,
        team: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Filter players by structured criteria, ordered by total points."""
        clauses: list[str] = []
        args: list[Any] = []

        def _param(value: Any) -> str:
            args.append(value)
            return f"${len(args)}"

        if position is not None:
            clauses.append(f"position = {_param(position.upper())}")
        if max_price is not None:
            clauses.append(f"price <= {_param(max_price)}")
        if min_form is not None:
            clauses.append(f"form >= {_param(min_form)}")
        if team is not None:
            clauses.append(f"team_name ILIKE {_param(f'%{team}%')}")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = await neon.fetch(
            f"""
            SELECT *
            FROM player_embeddings
            {where}
            ORDER BY total_points DESC
            LIMIT {_param(limit)}
            """,
            *args,
        )
        return {"count": len(rows), "players": _rows_to_dicts(rows)}

    @observe(name="tool.get_fixture_outlook", as_type="tool")
    async def get_fixture_outlook(player_name: str) -> dict[str, Any]:
        """Return the player's stored fixture-difficulty signal.

        Richer per-gameweek fixture data is a future enrichment; for now
        the pipeline stores a single ``fixture_difficulty`` float per player.
        Flag this limitation in the ScoutReport's ``caveats``.
        """
        row = await neon.fetch_one(
            """
            SELECT web_name, team_name, fixture_difficulty
            FROM player_embeddings
            WHERE web_name ILIKE $1
            LIMIT 1
            """,
            f"%{player_name}%",
        )
        if row is None:
            raise ToolError(f"No player found matching '{player_name}'")
        return {
            "player": row["web_name"],
            "team": row["team_name"],
            "difficulty": row["fixture_difficulty"],
            "note": "Single aggregate difficulty score; per-GW breakdown not yet available.",
        }

    @observe(name="tool.get_injury_signals", as_type="tool")
    async def get_injury_signals(player_name: str) -> dict[str, Any]:
        """Return stored injury risk + form-trend enrichment for a player."""
        row = await neon.fetch_one(
            """
            SELECT web_name, injury_risk_score, form_trend, summary
            FROM player_embeddings
            WHERE web_name ILIKE $1
            LIMIT 1
            """,
            f"%{player_name}%",
        )
        if row is None:
            raise ToolError(f"No player found matching '{player_name}'")
        return {
            "player": row["web_name"],
            "injury_risk_score": row["injury_risk_score"],
            "form_trend": row["form_trend"],
            "summary": row["summary"],
        }

    @observe(name="tool.fetch_user_squad", as_type="tool")
    async def fetch_user_squad(team_id: int, gameweek: int) -> dict[str, Any]:
        """Invoke the team-fetcher Lambda to retrieve a user's FPL squad.

        The target function name comes from ``TEAM_FETCHER_FUNCTION_NAME``; if
        the environment variable is unset the tool raises :class:`ToolError`
        rather than crashing the whole graph — the agent can still answer
        questions that don't need a user squad.
        """
        function_name = os.environ.get("TEAM_FETCHER_FUNCTION_NAME")
        if not function_name:
            raise ToolError("TEAM_FETCHER_FUNCTION_NAME not set — squad lookups are unavailable.")

        payload = json.dumps({"team_id": team_id, "gameweek": gameweek}).encode("utf-8")
        import asyncio

        def _invoke() -> dict[str, Any]:
            client = boto3.client("lambda")
            response = client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=payload,
            )
            body = response["Payload"].read().decode("utf-8")
            if response.get("FunctionError"):
                raise ToolError(f"team-fetcher Lambda error: {body}")
            return cast(dict[str, Any], json.loads(body))

        return await asyncio.to_thread(_invoke)

    return {
        "query_player": query_player,
        "search_similar_players": search_similar_players,
        "query_players_by_criteria": query_players_by_criteria,
        "get_fixture_outlook": get_fixture_outlook,
        "get_injury_signals": get_injury_signals,
        "fetch_user_squad": fetch_user_squad,
    }
