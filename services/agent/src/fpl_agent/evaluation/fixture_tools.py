"""Pandas-backed tool registry mirroring :mod:`fpl_agent.tools.player_tools`.

Same callable signatures, same return shapes, same :class:`ToolError`
semantics as the production tools — the eval framework swaps registries
into :func:`fpl_agent.graph.builder.build_agent_graph` without changing
anything else in the agent.

The five tools each translate the SQL their production counterpart issues
into a pandas/numpy operation against an in-memory
:class:`~fpl_agent.evaluation.fixture_data.PlayerFixture`:

* ``query_player`` — case-insensitive substring match on ``web_name``,
  highest ``total_points`` wins ties.
* ``search_similar_players`` — batched cosine similarity in numpy. The
  production query uses pgvector's ``<=>`` operator with an IVFFlat index;
  the in-memory version is exact rather than approximate, so neighbour
  ordering can differ at the margins. That's documented in the baseline.
* ``query_players_by_criteria`` — chained pandas filters.
* ``get_fixture_outlook`` / ``get_injury_signals`` — single-row lookup +
  projection. Each preserves the production tool's ``note``/``summary``
  framing so the recommender prompt sees identical context.

The embedding column is stripped from every response, matching
:data:`fpl_agent.tools.player_tools._OMIT_COLUMNS`. Numpy scalars are
coerced to native Python ints/floats so the dicts are JSON-serialisable
(LangGraph state, Langfuse traces).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from fpl_agent.evaluation.fixture_data import PlayerFixture
from fpl_agent.tools.player_tools import ToolError, ToolFn
from fpl_lib.observability import observe

logger = logging.getLogger(__name__)

# Mirrors player_tools._OMIT_COLUMNS — keep the embedding off the wire so the
# recommender's context window doesn't fill with 384 floats per player.
_OMIT_COLUMNS = {"embedding"}


def _coerce_scalar(value: Any) -> Any:
    """Convert numpy scalar types to native Python so dicts JSON-serialise."""
    if isinstance(value, np.generic):
        return value.item()
    return value


def _row_to_dict(row: pd.Series) -> dict[str, Any]:
    """Mirror :func:`player_tools._row_to_dict` for pandas Series rows."""
    return {k: _coerce_scalar(v) for k, v in row.items() if k not in _OMIT_COLUMNS}


def _ilike_mask(series: pd.Series, pattern: str) -> pd.Series:
    """Case-insensitive substring match — pandas equivalent of SQL ``ILIKE '%pat%'``."""
    return series.astype(str).str.contains(pattern, case=False, na=False, regex=False)


def make_fixture_tools(fixture: PlayerFixture) -> dict[str, ToolFn]:
    """Build the eval tool registry over an in-memory fixture.

    Returns a dict in the same shape as :func:`fpl_agent.tools.make_tools`
    so the graph builder sees a drop-in replacement.
    """

    df = fixture.df
    embeddings = fixture.embeddings

    @observe(name="tool.query_player", as_type="tool")
    async def query_player(name: str) -> dict[str, Any]:
        matches = df[_ilike_mask(df["web_name"], name)]
        if matches.empty:
            raise ToolError(f"No player found matching '{name}'")
        # ORDER BY total_points DESC LIMIT 1
        row = matches.nlargest(1, "total_points").iloc[0]
        return _row_to_dict(row)

    @observe(name="tool.search_similar_players", as_type="tool")
    async def search_similar_players(player_name: str, k: int = 5) -> dict[str, Any]:
        target_matches = df[_ilike_mask(df["web_name"], player_name)]
        if target_matches.empty:
            raise ToolError(f"No player found matching '{player_name}'")
        target_idx = int(target_matches.index[0])
        target_row = df.loc[target_idx]
        target_vec = embeddings[target_idx]

        # similarity = 1 - cosine_distance. Compute as dot / (norm * norm).
        # 1e-9 floor on the denominator guards against an all-zero embedding —
        # shouldn't happen in the real snapshot but cheap insurance.
        target_norm = float(np.linalg.norm(target_vec))
        all_norms = np.linalg.norm(embeddings, axis=1)
        dots = embeddings @ target_vec
        similarities = dots / (all_norms * target_norm + 1e-9)

        # Drop self before ranking — the production SQL uses player_id != target.
        similarities[target_idx] = -np.inf

        top_k = min(k, len(df) - 1)
        top_idx = np.argpartition(similarities, -top_k)[-top_k:]
        top_idx = top_idx[np.argsort(similarities[top_idx])[::-1]]

        similar_rows: list[dict[str, Any]] = []
        for idx in top_idx:
            row_dict = _row_to_dict(df.iloc[int(idx)])
            row_dict["similarity"] = float(similarities[idx])
            similar_rows.append(row_dict)

        return {
            "target": str(target_row["web_name"]),
            "similar": similar_rows,
        }

    @observe(name="tool.query_players_by_criteria", as_type="tool")
    async def query_players_by_criteria(
        position: str | None = None,
        max_price: float | None = None,
        min_form: float | None = None,
        team: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        filtered = df
        if position is not None:
            filtered = filtered[filtered["position"] == position.upper()]
        if max_price is not None:
            filtered = filtered[filtered["price"] <= max_price]
        if min_form is not None:
            filtered = filtered[filtered["form"] >= min_form]
        if team is not None:
            filtered = filtered[_ilike_mask(filtered["team_name"], team)]

        ordered = filtered.nlargest(limit, "total_points")
        return {
            "count": len(ordered),
            "players": [_row_to_dict(row) for _, row in ordered.iterrows()],
        }

    @observe(name="tool.get_fixture_outlook", as_type="tool")
    async def get_fixture_outlook(player_name: str) -> dict[str, Any]:
        matches = df[_ilike_mask(df["web_name"], player_name)]
        if matches.empty:
            raise ToolError(f"No player found matching '{player_name}'")
        row = matches.iloc[0]
        return {
            "player": str(row["web_name"]),
            "team": str(row["team_name"]),
            "difficulty": float(row["fixture_difficulty"]),
            "note": "Single aggregate difficulty score; per-GW breakdown not yet available.",
        }

    @observe(name="tool.get_injury_signals", as_type="tool")
    async def get_injury_signals(player_name: str) -> dict[str, Any]:
        matches = df[_ilike_mask(df["web_name"], player_name)]
        if matches.empty:
            raise ToolError(f"No player found matching '{player_name}'")
        row = matches.iloc[0]
        return {
            "player": str(row["web_name"]),
            "injury_risk_score": _coerce_scalar(row["injury_risk_score"]),
            "form_trend": _coerce_scalar(row["form_trend"]),
            "summary": _coerce_scalar(row["summary"]),
        }

    return {
        "query_player": query_player,
        "search_similar_players": search_similar_players,
        "query_players_by_criteria": query_players_by_criteria,
        "get_fixture_outlook": get_fixture_outlook,
        "get_injury_signals": get_injury_signals,
    }
