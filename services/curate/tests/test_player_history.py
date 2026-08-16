"""Unit tests for player history curator."""

from typing import Any

import pytest

from fpl_curate.curators.player_history import HISTORY_FIELDS, build_player_history


def _make_player(player_id: int, gameweek: int, fpl_score: float) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "web_name": f"Player{player_id}",
        "team_short": "TST",
        "position": "MID",
        "total_points": 50,
        "form": 3.0,
        "price": 6.0,
        "ownership_pct": 10.0,
        "fpl_score": fpl_score,
        "fpl_score_rank": 1,
        "form_trend": "stable",
        "injury_risk": 0,
        "sentiment_score": 0.5,
        "fdr_next_3": 3.0,
        "net_transfers": 1000,
        "points_per_million": 8.3,
        "gameweek": gameweek,
        "season": "2025-26",
    }


@pytest.mark.unit
class TestBuildPlayerHistory:
    def test_first_gameweek_creates_history(self) -> None:
        dashboard = [_make_player(1, 31, 60.0), _make_player(2, 31, 50.0)]
        result = build_player_history(dashboard, [], "2025-26", 31)
        assert len(result) == 2
        assert result[0]["gameweek"] == 31

    def test_appends_new_gameweek(self) -> None:
        existing = [_make_player(1, 31, 60.0), _make_player(2, 31, 50.0)]
        new_dashboard = [_make_player(1, 32, 65.0), _make_player(2, 32, 48.0)]
        result = build_player_history(new_dashboard, existing, "2025-26", 32)
        assert len(result) == 4
        gws = {r["gameweek"] for r in result}
        assert gws == {31, 32}

    def test_upsert_same_gameweek_replaces(self) -> None:
        existing = [_make_player(1, 31, 60.0), _make_player(2, 31, 50.0)]
        updated_dashboard = [_make_player(1, 31, 70.0), _make_player(2, 31, 55.0)]
        result = build_player_history(updated_dashboard, existing, "2025-26", 31)
        assert len(result) == 2  # Not 4 — replaced, not appended
        assert result[0]["fpl_score"] == 70.0
        assert result[1]["fpl_score"] == 55.0

    def test_older_gameweek_inserts_in_order(self) -> None:
        existing = [
            _make_player(1, 31, 60.0),
            _make_player(1, 33, 70.0),
        ]
        backfill = [_make_player(1, 32, 65.0)]
        result = build_player_history(backfill, existing, "2025-26", 32)
        assert len(result) == 3
        assert [r["gameweek"] for r in result] == [31, 32, 33]

    def test_sorted_by_gameweek_then_player_id(self) -> None:
        existing = [_make_player(2, 31, 50.0), _make_player(1, 31, 60.0)]
        new_dashboard = [_make_player(2, 32, 48.0), _make_player(1, 32, 65.0)]
        result = build_player_history(new_dashboard, existing, "2025-26", 32)
        ids = [(r["gameweek"], r["player_id"]) for r in result]
        assert ids == [(31, 1), (31, 2), (32, 1), (32, 2)]

    def test_only_history_fields_included(self) -> None:
        dashboard = [
            {
                **_make_player(1, 31, 60.0),
                "llm_summary": "Should not appear in history",
                "fixture_recommendation": "Excluded",
            }
        ]
        result = build_player_history(dashboard, [], "2025-26", 31)
        assert "llm_summary" not in result[0]
        assert "fixture_recommendation" not in result[0]
        assert set(result[0].keys()).issubset(set(HISTORY_FIELDS))

    def test_empty_dashboard(self) -> None:
        existing = [_make_player(1, 31, 60.0)]
        result = build_player_history([], existing, "2025-26", 32)
        assert len(result) == 1  # Existing untouched, nothing new added

    def test_season_rollover_sorts_before_gameweek(self) -> None:
        """GW1 of a new season must sort after GW38 of the last one, even
        though 1 < 38 — gameweek numbers reset every August, so sorting by
        gameweek alone would interleave the two seasons."""
        existing = [
            {**_make_player(1, 37, 55.0), "season": "2025-26"},
            {**_make_player(1, 38, 60.0), "season": "2025-26"},
        ]
        new_dashboard = [_make_player(1, 1, 40.0)]
        result = build_player_history(new_dashboard, existing, "2026-27", 1)

        assert len(result) == 3
        ordering = [(r["season"], r["gameweek"]) for r in result]
        assert ordering == [
            ("2025-26", 37),
            ("2025-26", 38),
            ("2026-27", 1),
        ]

    def test_same_gameweek_number_different_season_does_not_collide(self) -> None:
        """GW1 of a new season must not overwrite GW1 of the last one — the
        upsert-by-gameweek removal must also match on season."""
        existing = [{**_make_player(1, 1, 50.0), "season": "2025-26"}]
        new_dashboard = [_make_player(1, 1, 45.0)]
        result = build_player_history(new_dashboard, existing, "2026-27", 1)

        assert len(result) == 2  # Both seasons' GW1 rows survive
        by_season = {r["season"]: r["fpl_score"] for r in result}
        assert by_season == {"2025-26": 50.0, "2026-27": 45.0}
