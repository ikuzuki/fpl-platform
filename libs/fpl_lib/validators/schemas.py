"""Great Expectations-style validation schema definitions."""

from typing import Any

PLAYER_SCHEMA: dict[str, Any] = {
    "column_presence": [
        "id",
        "web_name",
        "team",
        "element_type",
        "total_points",
        "minutes",
        "now_cost",
    ],
    "not_null": ["id", "web_name", "team", "element_type"],
    "unique": ["id"],
    "value_ranges": {
        "element_type": {"min": 1, "max": 4},
        "total_points": {"min": -100, "max": 500},
        "minutes": {"min": 0, "max": 5000},
        "now_cost": {"min": 30, "max": 200},
    },
}

FIXTURE_SCHEMA: dict[str, Any] = {
    "column_presence": [
        "id",
        "gameweek",
        "home_team",
        "away_team",
        "home_difficulty",
        "away_difficulty",
    ],
    "not_null": ["id", "gameweek", "home_team", "away_team"],
    "unique": ["id"],
    "value_ranges": {
        "gameweek": {"min": 1, "max": 38},
        "home_difficulty": {"min": 1, "max": 5},
        "away_difficulty": {"min": 1, "max": 5},
    },
}
