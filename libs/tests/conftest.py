"""Shared test fixtures for fpl_lib tests."""

import pytest


@pytest.fixture
def sample_player_data() -> dict:
    """Return sample player data matching the FPL API format."""
    return {
        "id": 1,
        "web_name": "Salah",
        "team": 14,
        "team_name": "Liverpool",
        "element_type": 3,
        "total_points": 250,
        "minutes": 2800,
        "goals_scored": 20,
        "assists": 12,
        "clean_sheets": 0,
        "now_cost": 130,
        "selected_by_percent": "45.2",
        "form": "8.5",
        "points_per_game": "7.2",
    }


@pytest.fixture
def sample_fixture_data() -> dict:
    """Return sample fixture data."""
    return {
        "id": 100,
        "gameweek": 15,
        "home_team": "Liverpool",
        "away_team": "Arsenal",
        "home_difficulty": 3,
        "away_difficulty": 4,
    }
