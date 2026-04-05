"""Unit tests for gameweek briefing curator."""

from typing import Any

import pytest

from fpl_curate.curators.gameweek_briefing import build_gameweek_briefing


def _make_dashboard_player(
    player_id: int,
    web_name: str,
    team_short: str,
    position: str = "MID",
    fpl_score: float = 50.0,
    form_trend: str | None = "stable",
    injury_risk: int | None = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "web_name": web_name,
        "team_short": team_short,
        "position": position,
        "price": 7.0,
        "form": 5.0,
        "fpl_score": fpl_score,
        "form_trend": form_trend,
        "injury_risk": injury_risk,
        "injury_reasoning": None,
        "llm_summary": f"{web_name} is performing well.",
        "sentiment_label": "positive",
        "key_themes": ["consistent"],
        "fixture_recommendation": "Good run ahead.",
        "best_gameweeks": [32, 33],
        **kwargs,
    }


def _make_transfer(
    player_id: int,
    web_name: str,
    team_short: str,
    recommendation: str = "buy",
    fpl_score: float = 70.0,
) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "web_name": web_name,
        "team_short": team_short,
        "position": "MID",
        "price": 7.0,
        "fpl_score": fpl_score,
        "recommendation": recommendation,
        "recommendation_reasons": ["Good form", "Easy fixtures"],
        "form": 6.0,
    }


@pytest.fixture()
def sample_data() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[int, dict[str, float]],
    dict[int, dict[str, str]],
]:
    dashboard = [
        _make_dashboard_player(1, "Fernandes", "MUN", fpl_score=76.0, form_trend="improving"),
        _make_dashboard_player(
            2, "Saka", "ARS", fpl_score=65.0, form_trend="improving", injury_risk=6
        ),
        _make_dashboard_player(
            3, "Isak", "NEW", fpl_score=30.0, form_trend="declining", injury_risk=8
        ),
        _make_dashboard_player(4, "Haaland", "MCI", fpl_score=50.0, form_trend="stable"),
    ]
    transfers = [
        _make_transfer(1, "Fernandes", "MUN", "buy", 76.0),
        _make_transfer(2, "Saka", "ARS", "buy", 65.0),
        _make_transfer(3, "Isak", "NEW", "sell", 30.0),
        _make_transfer(4, "Haaland", "MCI", "hold", 50.0),
    ]
    fixture_fdr = {
        1: {"next_3": 2.5, "next_6": 2.8},
        13: {"next_3": 4.0, "next_6": 3.5},
        15: {"next_3": 3.0, "next_6": 3.2},
    }
    team_map = {
        1: {"name": "Arsenal", "short_name": "ARS"},
        13: {"name": "Man City", "short_name": "MCI"},
        15: {"name": "Newcastle", "short_name": "NEW"},
    }
    return dashboard, transfers, fixture_fdr, team_map


@pytest.mark.unit
class TestBuildGameweekBriefing:
    def test_returns_expected_keys(
        self,
        sample_data: tuple,
    ) -> None:
        dashboard, transfers, fdr, teams = sample_data
        result = build_gameweek_briefing(dashboard, transfers, fdr, teams, "2025-26", 31)
        assert "top_picks" in result
        assert "sell_alerts" in result
        assert "injury_alerts" in result
        assert "best_fixtures" in result
        assert "worst_fixtures" in result
        assert "rising_players" in result
        assert "falling_players" in result
        assert "trending_themes" in result
        assert "summary_stats" in result
        assert result["season"] == "2025-26"
        assert result["gameweek"] == 31

    def test_top_picks_are_buy_recommendations(
        self,
        sample_data: tuple,
    ) -> None:
        dashboard, transfers, fdr, teams = sample_data
        result = build_gameweek_briefing(dashboard, transfers, fdr, teams, "2025-26", 31)
        assert len(result["top_picks"]) == 2  # Only 2 buys
        assert result["top_picks"][0]["web_name"] == "Fernandes"  # Highest score buy

    def test_injury_alerts_filtered_by_risk(
        self,
        sample_data: tuple,
    ) -> None:
        dashboard, transfers, fdr, teams = sample_data
        result = build_gameweek_briefing(dashboard, transfers, fdr, teams, "2025-26", 31)
        assert len(result["injury_alerts"]) == 2  # Saka (6) and Isak (8)
        assert result["injury_alerts"][0]["injury_risk"] == 8  # Highest risk first

    def test_rising_and_falling_players(
        self,
        sample_data: tuple,
    ) -> None:
        dashboard, transfers, fdr, teams = sample_data
        result = build_gameweek_briefing(dashboard, transfers, fdr, teams, "2025-26", 31)
        assert len(result["rising_players"]) == 2  # Fernandes + Saka
        assert len(result["falling_players"]) == 1  # Isak

    def test_fixture_ordering(
        self,
        sample_data: tuple,
    ) -> None:
        dashboard, transfers, fdr, teams = sample_data
        result = build_gameweek_briefing(dashboard, transfers, fdr, teams, "2025-26", 31)
        # Best fixtures = lowest FDR first
        assert result["best_fixtures"][0]["team_short"] == "ARS"

    def test_summary_stats(
        self,
        sample_data: tuple,
    ) -> None:
        dashboard, transfers, fdr, teams = sample_data
        result = build_gameweek_briefing(dashboard, transfers, fdr, teams, "2025-26", 31)
        stats = result["summary_stats"]
        assert stats["total_players"] == 4
        assert stats["buy_count"] == 2
        assert stats["sell_count"] == 1
        assert stats["injury_count"] == 2
