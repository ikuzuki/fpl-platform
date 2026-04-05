"""Unit tests for FPL composite scoring logic."""

import pandas as pd
import pytest

from fpl_curate.curators.scoring import _min_max_scale, compute_fpl_scores


@pytest.mark.unit
class TestMinMaxScale:
    def test_basic_scaling(self) -> None:
        s = pd.Series([0, 50, 100])
        result = _min_max_scale(s)
        assert result.iloc[0] == 0.0
        assert result.iloc[1] == 50.0
        assert result.iloc[2] == 100.0

    def test_constant_series(self) -> None:
        s = pd.Series([5, 5, 5])
        result = _min_max_scale(s)
        assert (result == 50.0).all()

    def test_negative_values(self) -> None:
        s = pd.Series([-10, 0, 10])
        result = _min_max_scale(s)
        assert result.iloc[0] == 0.0
        assert result.iloc[1] == 50.0
        assert result.iloc[2] == 100.0


@pytest.mark.unit
class TestComputeFplScores:
    def test_scores_are_in_range(self, sample_enriched_df: pd.DataFrame) -> None:
        fixture_fdr = {
            1: {"next_3": 3.0, "next_6": 3.0},
            13: {"next_3": 4.0, "next_6": 4.0},
            14: {"next_3": 2.0, "next_6": 2.5},
        }
        result = compute_fpl_scores(sample_enriched_df, fixture_fdr=fixture_fdr)
        assert "fpl_score" in result.columns
        assert "fpl_score_rank" in result.columns
        assert result["fpl_score"].between(0, 100).all()
        assert result["fpl_score_rank"].min() == 1

    def test_rank_ordering(self, sample_enriched_df: pd.DataFrame) -> None:
        result = compute_fpl_scores(sample_enriched_df)
        # Rank 1 should have the highest score
        rank_1 = result[result["fpl_score_rank"] == 1].iloc[0]
        assert rank_1["fpl_score"] == result["fpl_score"].max()

    def test_no_component_columns_leaked(self, sample_enriched_df: pd.DataFrame) -> None:
        result = compute_fpl_scores(sample_enriched_df)
        component_cols = [c for c in result.columns if c.startswith("_c_")]
        assert component_cols == []

    def test_custom_weights(self, sample_enriched_df: pd.DataFrame) -> None:
        """All weight on form should rank highest-form player first."""
        weights = {
            "form": 1.0,
            "value": 0.0,
            "fixtures": 0.0,
            "xg_overperformance": 0.0,
            "ownership_momentum": 0.0,
            "ict": 0.0,
            "injury_risk": 0.0,
        }
        result = compute_fpl_scores(sample_enriched_df, weights=weights)
        top = result[result["fpl_score_rank"] == 1].iloc[0]
        # B.Fernandes has form=11.5, highest in the fixture
        assert top["web_name"] == "B.Fernandes"

    def test_handles_missing_understat(self, sample_enriched_df: pd.DataFrame) -> None:
        """Players with null Understat data should still get a score."""
        result = compute_fpl_scores(sample_enriched_df)
        bruno = result[result["web_name"] == "B.Fernandes"].iloc[0]
        assert pd.notna(bruno["fpl_score"])

    def test_handles_missing_fixture_fdr(self, sample_enriched_df: pd.DataFrame) -> None:
        """Empty fixture_fdr should default to neutral FDR (3.0)."""
        result = compute_fpl_scores(sample_enriched_df, fixture_fdr={})
        assert result["fpl_score"].notna().all()
