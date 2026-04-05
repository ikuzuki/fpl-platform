"""Shared fixtures for curate service tests."""

from typing import Any

import pandas as pd
import pytest


@pytest.fixture()
def team_map() -> dict[int, dict[str, str]]:
    """Sample team mapping."""
    return {
        1: {"name": "Arsenal", "short_name": "ARS"},
        12: {"name": "Liverpool", "short_name": "LIV"},
        13: {"name": "Man City", "short_name": "MCI"},
        14: {"name": "Man Utd", "short_name": "MUN"},
    }


@pytest.fixture()
def sample_fixtures_raw() -> list[dict[str, Any]]:
    """Sample raw fixtures JSON (4 GWs, 2 fixtures each)."""
    return [
        # GW31 (past)
        {"event": 31, "team_h": 1, "team_a": 12, "team_h_difficulty": 4, "team_a_difficulty": 4, "kickoff_time": "2026-04-05T15:00:00Z"},
        {"event": 31, "team_h": 13, "team_a": 14, "team_h_difficulty": 3, "team_a_difficulty": 4, "kickoff_time": "2026-04-05T17:30:00Z"},
        # GW32
        {"event": 32, "team_h": 1, "team_a": 14, "team_h_difficulty": 2, "team_a_difficulty": 4, "kickoff_time": "2026-04-12T15:00:00Z"},
        {"event": 32, "team_h": 12, "team_a": 13, "team_h_difficulty": 3, "team_a_difficulty": 4, "kickoff_time": "2026-04-12T17:30:00Z"},
        # GW33
        {"event": 33, "team_h": 14, "team_a": 12, "team_h_difficulty": 4, "team_a_difficulty": 3, "kickoff_time": "2026-04-19T15:00:00Z"},
        {"event": 33, "team_h": 13, "team_a": 1, "team_h_difficulty": 4, "team_a_difficulty": 5, "kickoff_time": "2026-04-19T17:30:00Z"},
        # GW34
        {"event": 34, "team_h": 1, "team_a": 13, "team_h_difficulty": 4, "team_a_difficulty": 5, "kickoff_time": "2026-04-26T15:00:00Z"},
        {"event": 34, "team_h": 14, "team_a": 12, "team_h_difficulty": 4, "team_a_difficulty": 3, "kickoff_time": "2026-04-26T17:30:00Z"},
    ]


@pytest.fixture()
def sample_enriched_df() -> pd.DataFrame:
    """Sample enriched player DataFrame with 4 players across 2 teams."""
    data = [
        {
            "id": 430, "web_name": "Haaland", "first_name": "Erling", "second_name": "Haaland",
            "team": 13, "element_type": 4, "now_cost": 144, "total_points": 197,
            "minutes": 2413, "goals_scored": 22, "assists": 7, "clean_sheets": 10,
            "goals_conceded": 27, "yellow_cards": 1, "red_cards": 0, "bonus": 35,
            "bps": 786, "starts": 28, "expected_goals": 21.06, "expected_assists": 1.94,
            "expected_goal_involvements": 23.0, "form": 2.0, "points_per_game": 6.8,
            "selected_by_percent": 55.0, "status": "a", "news": "",
            "chance_of_playing_next_round": 100.0, "transfers_in_event": 81351,
            "transfers_out_event": 69718, "influence": 977.0, "creativity": 264.7,
            "threat": 1217.0, "ict_index": 246.0, "season": "2025-26",
            "collected_at": "2026-04-05", "understat_xg": 23.14, "understat_xa": 4.77,
            "understat_npxg": 20.09, "understat_npg": 19.0, "understat_shots": 102.0,
            "understat_key_passes": 21.0, "understat_xg_chain": 26.24,
            "understat_xg_buildup": 4.13,
            "player_summary_summary": "Haaland has delivered 22 goals and 7 assists.",
            "player_summary_form_trend": "stable", "player_summary_confidence": 0.95,
            "injury_signal_risk_score": 0, "injury_signal_reasoning": "No injury concerns.",
            "injury_signal_injury_type": None, "injury_signal_sources": [],
            "sentiment_sentiment": "positive", "sentiment_score": 0.85,
            "sentiment_key_themes": ["hat-trick", "clinical finishing"],
            "fixture_outlook_difficulty_score": 3,
            "fixture_outlook_recommendation": "Tough GW32-33 but GW34 is easier.",
            "fixture_outlook_best_gameweeks": [34, 35, 36],
        },
        {
            "id": 449, "web_name": "B.Fernandes", "first_name": "Bruno", "second_name": "Fernandes",
            "team": 14, "element_type": 3, "now_cost": 103, "total_points": 189,
            "minutes": 2435, "goals_scored": 8, "assists": 17, "clean_sheets": 4,
            "goals_conceded": 39, "yellow_cards": 3, "red_cards": 0, "bonus": 36,
            "bps": 795, "starts": 28, "expected_goals": 10.32, "expected_assists": 9.03,
            "expected_goal_involvements": 19.35, "form": 11.5, "points_per_game": 6.8,
            "selected_by_percent": 44.7, "status": "a", "news": "",
            "chance_of_playing_next_round": 100.0, "transfers_in_event": 156843,
            "transfers_out_event": 5157, "influence": 1030.4, "creativity": 1467.1,
            "threat": 510.0, "ict_index": 301.0, "season": "2025-26",
            "collected_at": "2026-04-05", "understat_xg": None, "understat_xa": None,
            "understat_npxg": None, "understat_npg": None, "understat_shots": None,
            "understat_key_passes": None, "understat_xg_chain": None,
            "understat_xg_buildup": None,
            "player_summary_summary": "B.Fernandes in strong form with 11.5 ppg.",
            "player_summary_form_trend": "improving", "player_summary_confidence": 0.88,
            "injury_signal_risk_score": 0, "injury_signal_reasoning": "No data.",
            "injury_signal_injury_type": None, "injury_signal_sources": [],
            "sentiment_sentiment": "neutral", "sentiment_score": 0.0,
            "sentiment_key_themes": ["no coverage"],
            "fixture_outlook_difficulty_score": 3,
            "fixture_outlook_recommendation": "GW32 home fixture is favorable.",
            "fixture_outlook_best_gameweeks": [32, 34, 35],
        },
        {
            "id": 100, "web_name": "Saka", "first_name": "Bukayo", "second_name": "Saka",
            "team": 1, "element_type": 3, "now_cost": 110, "total_points": 155,
            "minutes": 2200, "goals_scored": 10, "assists": 12, "clean_sheets": 6,
            "goals_conceded": 20, "yellow_cards": 2, "red_cards": 0, "bonus": 20,
            "bps": 600, "starts": 26, "expected_goals": 8.5, "expected_assists": 7.0,
            "expected_goal_involvements": 15.5, "form": 7.0, "points_per_game": 6.0,
            "selected_by_percent": 30.0, "status": "a", "news": "",
            "chance_of_playing_next_round": 100.0, "transfers_in_event": 50000,
            "transfers_out_event": 10000, "influence": 800.0, "creativity": 900.0,
            "threat": 700.0, "ict_index": 240.0, "season": "2025-26",
            "collected_at": "2026-04-05", "understat_xg": 9.0, "understat_xa": 8.0,
            "understat_npxg": 8.5, "understat_npg": 9.0, "understat_shots": 60.0,
            "understat_key_passes": 40.0, "understat_xg_chain": 15.0,
            "understat_xg_buildup": 6.0,
            "player_summary_summary": "Saka is a consistent performer on the right wing.",
            "player_summary_form_trend": "improving", "player_summary_confidence": 0.90,
            "injury_signal_risk_score": 2, "injury_signal_reasoning": "Minor knock.",
            "injury_signal_injury_type": "knock", "injury_signal_sources": ["BBC Sport"],
            "sentiment_sentiment": "positive", "sentiment_score": 0.6,
            "sentiment_key_themes": ["creative", "consistent"],
            "fixture_outlook_difficulty_score": 4,
            "fixture_outlook_recommendation": "Tough run ahead.",
            "fixture_outlook_best_gameweeks": [35, 36],
        },
        {
            "id": 200, "web_name": "Chalobah", "first_name": "Trevoh", "second_name": "Chalobah",
            "team": 14, "element_type": 2, "now_cost": 45, "total_points": 30,
            "minutes": 500, "goals_scored": 0, "assists": 0, "clean_sheets": 1,
            "goals_conceded": 15, "yellow_cards": 3, "red_cards": 0, "bonus": 1,
            "bps": 50, "starts": 5, "expected_goals": 0.2, "expected_assists": 0.3,
            "expected_goal_involvements": 0.5, "form": 0.5, "points_per_game": 1.5,
            "selected_by_percent": 2.0, "status": "a", "news": "",
            "chance_of_playing_next_round": 75.0, "transfers_in_event": 142,
            "transfers_out_event": 281314, "influence": 50.0, "creativity": 20.0,
            "threat": 10.0, "ict_index": 8.0, "season": "2025-26",
            "collected_at": "2026-04-05", "understat_xg": None, "understat_xa": None,
            "understat_npxg": None, "understat_npg": None, "understat_shots": None,
            "understat_key_passes": None, "understat_xg_chain": None,
            "understat_xg_buildup": None,
            "player_summary_summary": "Chalobah has struggled for game time this season.",
            "player_summary_form_trend": "declining", "player_summary_confidence": 0.70,
            "injury_signal_risk_score": 5, "injury_signal_reasoning": "Limited minutes.",
            "injury_signal_injury_type": None, "injury_signal_sources": [],
            "sentiment_sentiment": "negative", "sentiment_score": -0.4,
            "sentiment_key_themes": ["benched", "transfer rumours"],
            "fixture_outlook_difficulty_score": 3,
            "fixture_outlook_recommendation": "Mixed fixtures.",
            "fixture_outlook_best_gameweeks": [32],
        },
    ]
    return pd.DataFrame(data)


@pytest.fixture()
def fixture_fdr() -> dict[int, dict[str, float]]:
    """Sample fixture FDR lookup."""
    return {
        1: {"next_3": 3.7, "next_6": 3.5},
        12: {"next_3": 3.3, "next_6": 3.2},
        13: {"next_3": 4.0, "next_6": 3.8},
        14: {"next_3": 3.7, "next_6": 3.5},
    }
