"""Shared fixtures for contract tests."""

from typing import Any

import pytest


@pytest.fixture()
def minimal_bootstrap_raw() -> dict[str, Any]:
    """Minimal raw FPL bootstrap-static API response with 3 players and 2 teams."""
    return {
        "elements": [
            {
                "id": 1,
                "web_name": "Haaland",
                "first_name": "Erling",
                "second_name": "Haaland",
                "team": 13,
                "element_type": 4,
                "now_cost": 144,
                "total_points": 197,
                "minutes": 2413,
                "goals_scored": 22,
                "assists": 7,
                "clean_sheets": 10,
                "goals_conceded": 27,
                "yellow_cards": 1,
                "red_cards": 0,
                "bonus": 35,
                "bps": 786,
                "starts": 28,
                "expected_goals": "21.06",
                "expected_assists": "1.94",
                "expected_goal_involvements": "23.00",
                "form": "2.0",
                "points_per_game": "6.8",
                "selected_by_percent": "55.0",
                "status": "a",
                "news": "",
                "chance_of_playing_next_round": 100,
                "transfers_in_event": 81351,
                "transfers_out_event": 69718,
                "influence": "977.0",
                "creativity": "264.7",
                "threat": "1217.0",
                "ict_index": "246.0",
            },
            {
                "id": 2,
                "web_name": "Saka",
                "first_name": "Bukayo",
                "second_name": "Saka",
                "team": 1,
                "element_type": 3,
                "now_cost": 110,
                "total_points": 155,
                "minutes": 2200,
                "goals_scored": 10,
                "assists": 12,
                "clean_sheets": 6,
                "goals_conceded": 20,
                "yellow_cards": 2,
                "red_cards": 0,
                "bonus": 20,
                "bps": 600,
                "starts": 26,
                "expected_goals": "8.50",
                "expected_assists": "7.00",
                "expected_goal_involvements": "15.50",
                "form": "7.0",
                "points_per_game": "6.0",
                "selected_by_percent": "30.0",
                "status": "a",
                "news": "",
                "chance_of_playing_next_round": 100,
                "transfers_in_event": 50000,
                "transfers_out_event": 10000,
                "influence": "800.0",
                "creativity": "900.0",
                "threat": "700.0",
                "ict_index": "240.0",
            },
            {
                "id": 3,
                "web_name": "Chalobah",
                "first_name": "Trevoh",
                "second_name": "Chalobah",
                "team": 1,
                "element_type": 2,
                "now_cost": 45,
                "total_points": 30,
                "minutes": 500,
                "goals_scored": 0,
                "assists": 0,
                "clean_sheets": 1,
                "goals_conceded": 15,
                "yellow_cards": 3,
                "red_cards": 0,
                "bonus": 1,
                "bps": 50,
                "starts": 5,
                "expected_goals": "0.20",
                "expected_assists": "0.30",
                "expected_goal_involvements": "0.50",
                "form": "0.5",
                "points_per_game": "1.5",
                "selected_by_percent": "2.0",
                "status": "a",
                "news": "",
                "chance_of_playing_next_round": 75,
                "transfers_in_event": 142,
                "transfers_out_event": 281314,
                "influence": "50.0",
                "creativity": "20.0",
                "threat": "10.0",
                "ict_index": "8.0",
            },
        ],
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS"},
            {"id": 13, "name": "Man City", "short_name": "MCI"},
        ],
        "events": [
            {"id": 31, "finished": True, "is_current": True},
        ],
    }


@pytest.fixture()
def minimal_understat_data() -> list[dict[str, Any]]:
    """Minimal Understat league stats for 2 players (Haaland + Saka)."""
    return [
        {
            "player_name": "Erling Haaland",
            "xG": "23.14",
            "xA": "4.77",
            "npxG": "20.09",
            "npg": "19",
            "shots": "102",
            "key_passes": "21",
            "xGChain": "26.24",
            "xGBuildup": "4.13",
        },
        {
            "player_name": "Bukayo Saka",
            "xG": "9.00",
            "xA": "8.00",
            "npxG": "8.50",
            "npg": "9",
            "shots": "60",
            "key_passes": "40",
            "xGChain": "15.00",
            "xGBuildup": "6.00",
        },
    ]


@pytest.fixture()
def enricher_output_samples() -> dict[str, dict[str, Any]]:
    """Valid output dict per enricher model, keyed by enricher class prefix."""
    return {
        "playersummary": {
            "summary": "Haaland has been in decent form with consistent goal returns.",
            "form_trend": "stable",
            "confidence": 0.90,
        },
        "injurysignal": {
            "risk_score": 1,
            "reasoning": "No injury concerns reported.",
            "injury_type": None,
            "sources": [],
        },
        "sentiment": {
            "sentiment": "positive",
            "score": 0.7,
            "key_themes": ["prolific", "clinical"],
        },
        "fixtureoutlook": {
            "difficulty_score": 3,
            "recommendation": "Hold — mixed fixtures ahead.",
            "best_gameweeks": [33, 35],
        },
    }
