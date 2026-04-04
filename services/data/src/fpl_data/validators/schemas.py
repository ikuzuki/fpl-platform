"""Validation schemas for raw FPL API data (pre-transformation).

These use raw API column names — the lib-level schemas in
fpl_lib.validators.schemas use clean/transformed column names.
"""

from typing import Any

PLAYER_EXPECTATIONS: dict[str, Any] = {
    "column_presence": [
        "id",
        "web_name",
        "team",
        "element_type",
        "total_points",
        "minutes",
    ],
    "not_null": ["id", "web_name", "team"],
    "unique": ["id"],
    "value_ranges": {
        "total_points": {"min": -10, "max": 300},
        "minutes": {"min": 0, "max": 5000},
        "element_type": {"allowed": [1, 2, 3, 4]},
    },
}

FIXTURE_EXPECTATIONS: dict[str, Any] = {
    "column_presence": [
        "id",
        "event",
        "team_h",
        "team_a",
        "team_h_difficulty",
        "team_a_difficulty",
    ],
    "not_null": ["id", "team_h", "team_a"],
    "unique": ["id"],
    "value_ranges": {
        "team_h_difficulty": {"min": 1, "max": 5},
        "team_a_difficulty": {"min": 1, "max": 5},
    },
}
