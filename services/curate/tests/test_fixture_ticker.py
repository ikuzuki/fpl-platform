"""Unit tests for fixture ticker curator."""

from typing import Any

import pytest

from fpl_curate.curators.fixture_ticker import build_fixture_ticker, build_team_map


@pytest.mark.unit
class TestBuildFixtureTicker:
    def test_filters_past_gameweeks(
        self, sample_fixtures_raw: list[dict[str, Any]], team_map: dict[int, dict[str, str]]
    ) -> None:
        rows, _ = build_fixture_ticker(
            sample_fixtures_raw, team_map, current_gw=31, season="2025-26"
        )
        gameweeks = {r["gameweek"] for r in rows}
        assert 31 not in gameweeks
        assert 32 in gameweeks

    def test_two_rows_per_fixture(
        self, sample_fixtures_raw: list[dict[str, Any]], team_map: dict[int, dict[str, str]]
    ) -> None:
        rows, _ = build_fixture_ticker(
            sample_fixtures_raw, team_map, current_gw=31, season="2025-26"
        )
        # 6 remaining fixtures (GW32-34) * 2 rows each = 12
        assert len(rows) == 12

    def test_home_away_correct(
        self, sample_fixtures_raw: list[dict[str, Any]], team_map: dict[int, dict[str, str]]
    ) -> None:
        rows, _ = build_fixture_ticker(
            sample_fixtures_raw, team_map, current_gw=31, season="2025-26"
        )
        # GW32: Arsenal (1) home vs Man Utd (14) away
        arsenal_gw32 = [r for r in rows if r["team_id"] == 1 and r["gameweek"] == 32]
        assert len(arsenal_gw32) == 1
        assert arsenal_gw32[0]["is_home"] is True
        assert arsenal_gw32[0]["opponent"] == "Man Utd"

    def test_fdr_lookup_structure(
        self, sample_fixtures_raw: list[dict[str, Any]], team_map: dict[int, dict[str, str]]
    ) -> None:
        _, fdr = build_fixture_ticker(
            sample_fixtures_raw, team_map, current_gw=31, season="2025-26"
        )
        assert 1 in fdr
        assert "next_3" in fdr[1]
        assert "next_6" in fdr[1]
        assert isinstance(fdr[1]["next_3"], float)

    def test_empty_fixtures(self, team_map: dict[int, dict[str, str]]) -> None:
        rows, fdr = build_fixture_ticker([], team_map, current_gw=31, season="2025-26")
        assert rows == []
        assert fdr == {}


@pytest.mark.unit
class TestBuildTeamMap:
    def test_extracts_teams(self) -> None:
        bootstrap = {
            "teams": [
                {"id": 1, "name": "Arsenal", "short_name": "ARS"},
                {"id": 12, "name": "Liverpool", "short_name": "LIV"},
            ]
        }
        result = build_team_map(bootstrap)
        assert result[1] == {"name": "Arsenal", "short_name": "ARS"}
        assert len(result) == 2

    def test_empty_bootstrap(self) -> None:
        assert build_team_map({}) == {}
