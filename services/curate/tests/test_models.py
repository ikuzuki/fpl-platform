"""Unit tests for curated dataset Pydantic models."""

import pytest
from pydantic import ValidationError

from fpl_curate.curators.models import (
    FixtureTickerRow,
    PlayerDashboardRow,
    TeamStrengthRow,
    TransferPickRow,
)


@pytest.mark.unit
class TestPlayerDashboardRow:
    def test_valid_full(self) -> None:
        row = PlayerDashboardRow(
            player_id=430,
            web_name="Haaland",
            full_name="Erling Haaland",
            team_name="Man City",
            team_short="MCI",
            position="FWD",
            total_points=197,
            minutes=2413,
            goals_scored=22,
            assists=7,
            clean_sheets=10,
            bonus=35,
            form=2.0,
            points_per_game=6.8,
            price=14.4,
            ownership_pct=55.0,
            points_per_million=13.7,
            transfers_in=81351,
            transfers_out=69718,
            net_transfers=11633,
            xg=23.14,
            xa=4.77,
            npxg=20.09,
            xg_delta=-1.14,
            influence=977.0,
            creativity=264.7,
            threat=1217.0,
            ict_index=246.0,
            form_trend="stable",
            form_confidence=0.95,
            llm_summary="Consistent scorer.",
            injury_risk=0,
            sentiment_label="positive",
            sentiment_score=0.85,
            fpl_score=78.5,
            fpl_score_rank=1,
            season="2025-26",
            gameweek=31,
        )
        assert row.position == "FWD"
        assert row.price == 14.4

    def test_valid_nullable_fields(self) -> None:
        """Should accept None for optional enrichment/xStats fields."""
        row = PlayerDashboardRow(
            player_id=1,
            web_name="Test",
            full_name="Test Player",
            team_name="Team",
            team_short="TST",
            position="MID",
            total_points=50,
            minutes=1000,
            goals_scored=3,
            assists=2,
            clean_sheets=2,
            bonus=5,
            form=3.0,
            points_per_game=4.0,
            price=6.0,
            ownership_pct=10.0,
            points_per_million=8.3,
            transfers_in=100,
            transfers_out=50,
            net_transfers=50,
            influence=100.0,
            creativity=100.0,
            threat=100.0,
            ict_index=30.0,
            fpl_score=50.0,
            fpl_score_rank=150,
            season="2025-26",
            gameweek=31,
        )
        assert row.xg is None
        assert row.injury_risk is None

    def test_invalid_position(self) -> None:
        with pytest.raises(ValidationError):
            PlayerDashboardRow(
                player_id=1,
                web_name="Test",
                full_name="Test Player",
                team_name="Team",
                team_short="TST",
                position="STRIKER",
                total_points=50,
                minutes=1000,
                goals_scored=3,
                assists=2,
                clean_sheets=2,
                bonus=5,
                form=3.0,
                points_per_game=4.0,
                price=6.0,
                ownership_pct=10.0,
                points_per_million=8.3,
                transfers_in=100,
                transfers_out=50,
                net_transfers=50,
                influence=100.0,
                creativity=100.0,
                threat=100.0,
                ict_index=30.0,
                fpl_score=50.0,
                fpl_score_rank=150,
                season="2025-26",
                gameweek=31,
            )

    def test_fpl_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            PlayerDashboardRow(
                player_id=1,
                web_name="Test",
                full_name="Test Player",
                team_name="Team",
                team_short="TST",
                position="MID",
                total_points=50,
                minutes=1000,
                goals_scored=3,
                assists=2,
                clean_sheets=2,
                bonus=5,
                form=3.0,
                points_per_game=4.0,
                price=6.0,
                ownership_pct=10.0,
                points_per_million=8.3,
                transfers_in=100,
                transfers_out=50,
                net_transfers=50,
                influence=100.0,
                creativity=100.0,
                threat=100.0,
                ict_index=30.0,
                fpl_score=101.0,
                fpl_score_rank=1,
                season="2025-26",
                gameweek=31,
            )

    def test_injury_risk_range(self) -> None:
        with pytest.raises(ValidationError):
            PlayerDashboardRow(
                player_id=1,
                web_name="Test",
                full_name="Test Player",
                team_name="Team",
                team_short="TST",
                position="DEF",
                total_points=50,
                minutes=1000,
                goals_scored=0,
                assists=1,
                clean_sheets=5,
                bonus=3,
                form=3.0,
                points_per_game=4.0,
                price=5.0,
                ownership_pct=5.0,
                points_per_million=10.0,
                transfers_in=100,
                transfers_out=50,
                net_transfers=50,
                influence=100.0,
                creativity=50.0,
                threat=30.0,
                ict_index=18.0,
                injury_risk=11,
                fpl_score=50.0,
                fpl_score_rank=150,
                season="2025-26",
                gameweek=31,
            )


@pytest.mark.unit
class TestFixtureTickerRow:
    def test_valid(self) -> None:
        row = FixtureTickerRow(
            team_id=1,
            team_name="Arsenal",
            team_short="ARS",
            gameweek=32,
            opponent="Liverpool",
            opponent_short="LIV",
            is_home=True,
            fdr=4,
            season="2025-26",
        )
        assert row.is_home is True

    def test_fdr_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            FixtureTickerRow(
                team_id=1,
                team_name="Arsenal",
                team_short="ARS",
                gameweek=32,
                opponent="Liverpool",
                opponent_short="LIV",
                is_home=True,
                fdr=6,
                season="2025-26",
            )


@pytest.mark.unit
class TestTransferPickRow:
    def test_valid(self) -> None:
        row = TransferPickRow(
            player_id=430,
            web_name="Haaland",
            team_name="Man City",
            team_short="MCI",
            position="FWD",
            price=14.4,
            fpl_score=78.5,
            fpl_score_rank=1,
            recommendation="buy",
            recommendation_reasons=["Strong FPL score (78.5)"],
            form=6.0,
            net_transfers=11633,
            season="2025-26",
            gameweek=31,
        )
        assert row.recommendation == "buy"

    def test_invalid_recommendation(self) -> None:
        with pytest.raises(ValidationError):
            TransferPickRow(
                player_id=1,
                web_name="Test",
                team_name="Team",
                team_short="TST",
                position="MID",
                price=6.0,
                fpl_score=50.0,
                fpl_score_rank=100,
                recommendation="avoid",
                recommendation_reasons=[],
                form=3.0,
                net_transfers=0,
                season="2025-26",
                gameweek=31,
            )


@pytest.mark.unit
class TestTeamStrengthRow:
    def test_valid(self) -> None:
        row = TeamStrengthRow(
            team_id=13,
            team_name="Man City",
            team_short="MCI",
            avg_fpl_score=65.0,
            total_points=500,
            avg_form=5.0,
            squad_value=120.0,
            top_scorer_id=430,
            top_scorer_name="Haaland",
            top_scorer_points=197,
            avg_fdr_remaining=3.5,
            player_count=15,
            enriched_player_count=10,
            season="2025-26",
            gameweek=31,
        )
        assert row.team_short == "MCI"
