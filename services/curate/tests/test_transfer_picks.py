"""Unit tests for transfer picks curator."""

import pytest

from fpl_curate.curators.transfer_picks import _classify_player, build_transfer_picks


@pytest.mark.unit
class TestClassifyPlayer:
    def test_buy_high_score_good_form_easy_fixtures(self) -> None:
        player = {
            "fpl_score": 75,
            "form": 8.0,
            "fdr_next_3": 2.0,
            "injury_risk": 0,
            "net_transfers": 50000,
            "form_trend": "improving",
            "points_per_million": 6.0,
        }
        rec, reasons = _classify_player(player)
        assert rec == "buy"
        assert len(reasons) > 0

    def test_sell_low_score_poor_form(self) -> None:
        player = {
            "fpl_score": 20,
            "form": 0.5,
            "fdr_next_3": 4.5,
            "injury_risk": 3,
            "net_transfers": -100000,
            "form_trend": "declining",
            "points_per_million": 2.0,
        }
        rec, reasons = _classify_player(player)
        assert rec == "sell"

    def test_sell_high_injury_risk(self) -> None:
        player = {
            "fpl_score": 50,
            "form": 4.0,
            "fdr_next_3": 3.0,
            "injury_risk": 9,
            "net_transfers": -5000,
            "form_trend": "declining",
            "points_per_million": 4.0,
        }
        rec, _ = _classify_player(player)
        assert rec == "sell"

    def test_hold_average_player(self) -> None:
        player = {
            "fpl_score": 45,
            "form": 3.0,
            "fdr_next_3": 3.0,
            "injury_risk": 2,
            "net_transfers": 1000,
            "form_trend": "stable",
            "points_per_million": 4.0,
        }
        rec, _ = _classify_player(player)
        assert rec == "hold"

    def test_watch_decent_score_high_demand(self) -> None:
        player = {
            "fpl_score": 58,
            "form": 4.0,
            "fdr_next_3": 3.0,
            "injury_risk": 1,
            "net_transfers": 50000,
            "form_trend": "stable",
            "points_per_million": 4.5,
        }
        rec, _ = _classify_player(player)
        assert rec == "watch"


@pytest.mark.unit
class TestBuildTransferPicks:
    def test_all_players_get_recommendation(self) -> None:
        dashboard = [
            {
                "player_id": 1,
                "web_name": "A",
                "team_name": "Team",
                "team_short": "TST",
                "position": "MID",
                "price": 6.0,
                "fpl_score": 60.0,
                "fpl_score_rank": 1,
                "form": 5.0,
                "form_trend": "stable",
                "injury_risk": 0,
                "fdr_next_3": 3.0,
                "net_transfers": 1000,
                "points_per_million": 5.0,
            },
            {
                "player_id": 2,
                "web_name": "B",
                "team_name": "Team",
                "team_short": "TST",
                "position": "DEF",
                "price": 4.5,
                "fpl_score": 30.0,
                "fpl_score_rank": 2,
                "form": 1.0,
                "form_trend": "declining",
                "injury_risk": 7,
                "fdr_next_3": 4.0,
                "net_transfers": -50000,
                "points_per_million": 3.0,
            },
        ]
        rows = build_transfer_picks(dashboard, "2025-26", 31)
        assert len(rows) == 2
        recs = {r["recommendation"] for r in rows}
        assert recs.issubset({"buy", "sell", "hold", "watch"})

    def test_reasons_not_empty(self) -> None:
        dashboard = [
            {
                "player_id": 1,
                "web_name": "A",
                "team_name": "T",
                "team_short": "T",
                "position": "FWD",
                "price": 10.0,
                "fpl_score": 50.0,
                "fpl_score_rank": 1,
                "form": 3.0,
                "form_trend": "stable",
                "injury_risk": 2,
                "fdr_next_3": 3.0,
                "net_transfers": 100,
                "points_per_million": 4.0,
            }
        ]
        rows = build_transfer_picks(dashboard, "2025-26", 31)
        assert len(rows[0]["recommendation_reasons"]) > 0
