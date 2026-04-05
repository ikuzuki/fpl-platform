"""Unit tests for team strength curator."""

from typing import Any

import pytest

from fpl_curate.curators.team_strength import build_team_strength


@pytest.mark.unit
class TestBuildTeamStrength:
    def _make_dashboard(self) -> list[dict[str, Any]]:
        return [
            {
                "player_id": 430,
                "web_name": "Haaland",
                "team_name": "Man City",
                "team_short": "MCI",
                "position": "FWD",
                "price": 14.4,
                "total_points": 197,
                "form": 2.0,
                "fpl_score": 70.0,
                "llm_summary": "Great striker.",
            },
            {
                "player_id": 82,
                "web_name": "Semenyo",
                "team_name": "Man City",
                "team_short": "MCI",
                "position": "MID",
                "price": 8.2,
                "total_points": 174,
                "form": 2.0,
                "fpl_score": 55.0,
                "llm_summary": "Consistent winger.",
            },
            {
                "player_id": 449,
                "web_name": "B.Fernandes",
                "team_name": "Man Utd",
                "team_short": "MUN",
                "position": "MID",
                "price": 10.3,
                "total_points": 189,
                "form": 11.5,
                "fpl_score": 80.0,
                "llm_summary": "In form.",
            },
        ]

    def test_correct_team_count(self) -> None:
        team_map = {
            13: {"name": "Man City", "short_name": "MCI"},
            14: {"name": "Man Utd", "short_name": "MUN"},
        }
        fixture_fdr = {
            13: {"next_3": 4.0, "next_6": 3.5},
            14: {"next_3": 2.5, "next_6": 3.0},
        }
        rows = build_team_strength(self._make_dashboard(), fixture_fdr, team_map, "2025-26", 31)
        assert len(rows) == 2

    def test_aggregation_values(self) -> None:
        team_map = {
            13: {"name": "Man City", "short_name": "MCI"},
            14: {"name": "Man Utd", "short_name": "MUN"},
        }
        fixture_fdr = {13: {"next_3": 4.0, "next_6": 3.5}, 14: {"next_3": 2.5, "next_6": 3.0}}
        rows = build_team_strength(self._make_dashboard(), fixture_fdr, team_map, "2025-26", 31)

        mci = next(r for r in rows if r["team_name"] == "Man City")
        assert mci["player_count"] == 2
        assert mci["total_points"] == 197 + 174
        assert mci["top_scorer_name"] == "Haaland"
        assert mci["avg_fpl_score"] == round((70.0 + 55.0) / 2, 1)
        assert mci["squad_value"] == round(14.4 + 8.2, 1)

    def test_enriched_count(self) -> None:
        team_map = {13: {"name": "Man City", "short_name": "MCI"}}
        dashboard = [
            {
                "player_id": 1,
                "web_name": "A",
                "team_name": "Man City",
                "team_short": "MCI",
                "position": "MID",
                "price": 5.0,
                "total_points": 50,
                "form": 3.0,
                "fpl_score": 40.0,
                "llm_summary": "Has data.",
            },
            {
                "player_id": 2,
                "web_name": "B",
                "team_name": "Man City",
                "team_short": "MCI",
                "position": "DEF",
                "price": 4.0,
                "total_points": 20,
                "form": 1.0,
                "fpl_score": 20.0,
                "llm_summary": None,
            },
        ]
        rows = build_team_strength(dashboard, {}, team_map, "2025-26", 31)
        assert rows[0]["enriched_player_count"] == 1
