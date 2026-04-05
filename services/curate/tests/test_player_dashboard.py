"""Unit tests for player dashboard curator."""

import pandas as pd
import pytest

from fpl_curate.curators.player_dashboard import build_player_dashboard


@pytest.mark.unit
class TestBuildPlayerDashboard:
    def test_output_row_count(
        self,
        sample_enriched_df: pd.DataFrame,
        team_map: dict[int, dict[str, str]],
        fixture_fdr: dict[int, dict[str, float]],
    ) -> None:
        rows = build_player_dashboard(
            sample_enriched_df,
            team_map,
            fixture_fdr,
            None,
            "2025-26",
            31,
        )
        # All 4 test players have player_summary_summary populated
        assert len(rows) == 4

    def test_position_mapping(
        self,
        sample_enriched_df: pd.DataFrame,
        team_map: dict[int, dict[str, str]],
        fixture_fdr: dict[int, dict[str, float]],
    ) -> None:
        rows = build_player_dashboard(
            sample_enriched_df,
            team_map,
            fixture_fdr,
            None,
            "2025-26",
            31,
        )
        haaland = next(r for r in rows if r["web_name"] == "Haaland")
        assert haaland["position"] == "FWD"
        chalobah = next(r for r in rows if r["web_name"] == "Chalobah")
        assert chalobah["position"] == "DEF"

    def test_team_name_mapped(
        self,
        sample_enriched_df: pd.DataFrame,
        team_map: dict[int, dict[str, str]],
        fixture_fdr: dict[int, dict[str, float]],
    ) -> None:
        rows = build_player_dashboard(
            sample_enriched_df,
            team_map,
            fixture_fdr,
            None,
            "2025-26",
            31,
        )
        haaland = next(r for r in rows if r["web_name"] == "Haaland")
        assert haaland["team_name"] == "Man City"
        assert haaland["team_short"] == "MCI"

    def test_derived_fields(
        self,
        sample_enriched_df: pd.DataFrame,
        team_map: dict[int, dict[str, str]],
        fixture_fdr: dict[int, dict[str, float]],
    ) -> None:
        rows = build_player_dashboard(
            sample_enriched_df,
            team_map,
            fixture_fdr,
            None,
            "2025-26",
            31,
        )
        haaland = next(r for r in rows if r["web_name"] == "Haaland")
        assert haaland["price"] == 14.4
        assert haaland["net_transfers"] == 81351 - 69718

    def test_nullable_xg_fields(
        self,
        sample_enriched_df: pd.DataFrame,
        team_map: dict[int, dict[str, str]],
        fixture_fdr: dict[int, dict[str, float]],
    ) -> None:
        rows = build_player_dashboard(
            sample_enriched_df,
            team_map,
            fixture_fdr,
            None,
            "2025-26",
            31,
        )
        # Bruno has no Understat data
        bruno = next(r for r in rows if r["web_name"] == "B.Fernandes")
        assert bruno["xg"] is None
        assert bruno["xa"] is None

    def test_fpl_score_present_and_ranked(
        self,
        sample_enriched_df: pd.DataFrame,
        team_map: dict[int, dict[str, str]],
        fixture_fdr: dict[int, dict[str, float]],
    ) -> None:
        rows = build_player_dashboard(
            sample_enriched_df,
            team_map,
            fixture_fdr,
            None,
            "2025-26",
            31,
        )
        scores = [r["fpl_score"] for r in rows]
        ranks = [r["fpl_score_rank"] for r in rows]
        assert all(0 <= s <= 100 for s in scores)
        assert 1 in ranks

    def test_filters_non_enriched_players(
        self,
        team_map: dict[int, dict[str, str]],
        fixture_fdr: dict[int, dict[str, float]],
    ) -> None:
        """Players without LLM enrichment should be excluded."""
        df = pd.DataFrame(
            [
                {
                    "id": 999,
                    "web_name": "Nobody",
                    "first_name": "No",
                    "second_name": "Body",
                    "team": 1,
                    "element_type": 2,
                    "now_cost": 40,
                    "total_points": 5,
                    "minutes": 100,
                    "goals_scored": 0,
                    "assists": 0,
                    "clean_sheets": 0,
                    "goals_conceded": 5,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "bonus": 0,
                    "bps": 10,
                    "starts": 1,
                    "expected_goals": 0.0,
                    "expected_assists": 0.0,
                    "expected_goal_involvements": 0.0,
                    "form": 0.0,
                    "points_per_game": 0.5,
                    "selected_by_percent": 0.1,
                    "status": "a",
                    "news": "",
                    "chance_of_playing_next_round": None,
                    "transfers_in_event": 0,
                    "transfers_out_event": 0,
                    "influence": 0.0,
                    "creativity": 0.0,
                    "threat": 0.0,
                    "ict_index": 0.0,
                    "season": "2025-26",
                    "collected_at": "2026-04-05",
                    "understat_xg": None,
                    "understat_xa": None,
                    "understat_npxg": None,
                    "understat_npg": None,
                    "understat_shots": None,
                    "understat_key_passes": None,
                    "understat_xg_chain": None,
                    "understat_xg_buildup": None,
                    "player_summary_summary": None,  # NOT enriched
                    "player_summary_form_trend": None,
                    "player_summary_confidence": None,
                    "injury_signal_risk_score": None,
                    "injury_signal_reasoning": None,
                    "injury_signal_injury_type": None,
                    "injury_signal_sources": None,
                    "sentiment_sentiment": None,
                    "sentiment_score": None,
                    "sentiment_key_themes": None,
                    "fixture_outlook_difficulty_score": None,
                    "fixture_outlook_recommendation": None,
                    "fixture_outlook_best_gameweeks": None,
                }
            ]
        )
        rows = build_player_dashboard(df, team_map, fixture_fdr, None, "2025-26", 31)
        assert len(rows) == 0
