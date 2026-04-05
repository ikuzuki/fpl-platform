"""Unit tests for concrete enricher implementations and Pydantic output models."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from fpl_enrich.enrichers.fixture_outlook import FixtureOutlookEnricher
from fpl_enrich.enrichers.injury_signal import InjurySignalEnricher
from fpl_enrich.enrichers.models import (
    FixtureOutlookOutput,
    InjurySignalOutput,
    PlayerSummaryOutput,
    SentimentOutput,
)
from fpl_enrich.enrichers.player_summary import PlayerSummaryEnricher
from fpl_enrich.enrichers.sentiment import SentimentEnricher


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


# --- Pydantic model validation tests ----------------------------------------


@pytest.mark.unit
class TestPlayerSummaryOutput:
    def test_valid(self) -> None:
        out = PlayerSummaryOutput(
            summary="Scored 3 goals in 5 games with an average of 6.2 points.",
            form_trend="improving",
            confidence=0.85,
        )
        assert out.form_trend == "improving"

    def test_summary_too_short(self) -> None:
        with pytest.raises(ValidationError):
            PlayerSummaryOutput(summary="Short", form_trend="stable", confidence=0.5)

    def test_invalid_form_trend(self) -> None:
        with pytest.raises(ValidationError):
            PlayerSummaryOutput(
                summary="A long enough summary for testing purposes here.",
                form_trend="skyrocketing",
                confidence=0.5,
            )

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            PlayerSummaryOutput(
                summary="A long enough summary for testing purposes here.",
                form_trend="stable",
                confidence=1.5,
            )


@pytest.mark.unit
class TestInjurySignalOutput:
    def test_valid(self) -> None:
        out = InjurySignalOutput(
            risk_score=7,
            reasoning="Hamstring concern flagged in training report.",
            injury_type="hamstring",
            sources=["BBC Sport"],
        )
        assert out.risk_score == 7

    def test_risk_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            InjurySignalOutput(risk_score=11, reasoning="Test")

    def test_empty_reasoning_fails(self) -> None:
        with pytest.raises(ValidationError):
            InjurySignalOutput(risk_score=3, reasoning="")

    def test_null_injury_type_allowed(self) -> None:
        out = InjurySignalOutput(risk_score=0, reasoning="No concern", injury_type=None)
        assert out.injury_type is None


@pytest.mark.unit
class TestSentimentOutput:
    def test_valid(self) -> None:
        out = SentimentOutput(
            sentiment="positive",
            score=0.7,
            key_themes=["good form", "goal scoring"],
        )
        assert out.sentiment == "positive"

    def test_invalid_sentiment(self) -> None:
        with pytest.raises(ValidationError):
            SentimentOutput(sentiment="amazing", score=0.5, key_themes=[])

    def test_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            SentimentOutput(sentiment="neutral", score=1.5, key_themes=[])


@pytest.mark.unit
class TestFixtureOutlookOutput:
    def test_valid(self) -> None:
        out = FixtureOutlookOutput(
            difficulty_score=2,
            recommendation="Favourable run of fixtures with 3 home games.",
            best_gameweeks=[10, 11, 13],
        )
        assert out.difficulty_score == 2

    def test_difficulty_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            FixtureOutlookOutput(difficulty_score=0, recommendation="Test", best_gameweeks=[])

    def test_empty_recommendation_fails(self) -> None:
        with pytest.raises(ValidationError):
            FixtureOutlookOutput(difficulty_score=3, recommendation="", best_gameweeks=[])


# --- Enricher _validate_output tests ----------------------------------------


@pytest.mark.unit
class TestPlayerSummaryEnricherValidation:
    def test_valid_output(self, mock_client: MagicMock) -> None:
        enricher = PlayerSummaryEnricher(anthropic_client=mock_client)
        result = enricher._validate_output(
            {
                "summary": "Scored 3 goals in last 5 games. Points average rising.",
                "form_trend": "improving",
                "confidence": 0.8,
            }
        )
        assert result is not None
        assert result["form_trend"] == "improving"

    def test_invalid_output_returns_none(self, mock_client: MagicMock) -> None:
        enricher = PlayerSummaryEnricher(anthropic_client=mock_client)
        result = enricher._validate_output(
            {"summary": "Short", "form_trend": "improving", "confidence": 0.8}
        )
        assert result is None

    def test_missing_field_returns_none(self, mock_client: MagicMock) -> None:
        enricher = PlayerSummaryEnricher(anthropic_client=mock_client)
        result = enricher._validate_output({"summary": "A long enough summary text here."})
        assert result is None


@pytest.mark.unit
class TestInjurySignalEnricherValidation:
    def test_valid_output(self, mock_client: MagicMock) -> None:
        enricher = InjurySignalEnricher(anthropic_client=mock_client)
        result = enricher._validate_output(
            {
                "risk_score": 5,
                "reasoning": "Missed training session with calf issue.",
                "injury_type": "calf",
                "sources": ["Sky Sports"],
            }
        )
        assert result is not None
        assert result["risk_score"] == 5

    def test_invalid_risk_score(self, mock_client: MagicMock) -> None:
        enricher = InjurySignalEnricher(anthropic_client=mock_client)
        result = enricher._validate_output({"risk_score": 15, "reasoning": "Test"})
        assert result is None


@pytest.mark.unit
class TestSentimentEnricherValidation:
    def test_valid_output(self, mock_client: MagicMock) -> None:
        enricher = SentimentEnricher(anthropic_client=mock_client)
        result = enricher._validate_output(
            {"sentiment": "mixed", "score": 0.2, "key_themes": ["form", "rotation"]}
        )
        assert result is not None
        assert result["sentiment"] == "mixed"

    def test_invalid_sentiment_value(self, mock_client: MagicMock) -> None:
        enricher = SentimentEnricher(anthropic_client=mock_client)
        result = enricher._validate_output(
            {"sentiment": "fantastic", "score": 0.9, "key_themes": []}
        )
        assert result is None


@pytest.mark.unit
class TestFixtureOutlookEnricherValidation:
    def test_valid_output(self, mock_client: MagicMock) -> None:
        enricher = FixtureOutlookEnricher(anthropic_client=mock_client)
        result = enricher._validate_output(
            {
                "difficulty_score": 2,
                "recommendation": "Good run of home fixtures coming up.",
                "best_gameweeks": [10, 12],
            }
        )
        assert result is not None
        assert result["difficulty_score"] == 2

    def test_invalid_difficulty_score(self, mock_client: MagicMock) -> None:
        enricher = FixtureOutlookEnricher(anthropic_client=mock_client)
        result = enricher._validate_output(
            {"difficulty_score": 6, "recommendation": "Test", "best_gameweeks": []}
        )
        assert result is None

    def test_uses_sonnet_model(self, mock_client: MagicMock) -> None:
        enricher = FixtureOutlookEnricher(anthropic_client=mock_client)
        assert "sonnet" in enricher.MODEL


# --- Enricher configuration tests -------------------------------------------


@pytest.mark.unit
class TestEnricherConfig:
    def test_player_summary_batch_size(self, mock_client: MagicMock) -> None:
        enricher = PlayerSummaryEnricher(anthropic_client=mock_client)
        assert enricher.BATCH_SIZE == 10

    def test_injury_signal_batch_size(self, mock_client: MagicMock) -> None:
        enricher = InjurySignalEnricher(anthropic_client=mock_client)
        assert enricher.BATCH_SIZE == 10

    def test_sentiment_batch_size(self, mock_client: MagicMock) -> None:
        enricher = SentimentEnricher(anthropic_client=mock_client)
        assert enricher.BATCH_SIZE == 10

    def test_fixture_outlook_batch_size(self, mock_client: MagicMock) -> None:
        enricher = FixtureOutlookEnricher(anthropic_client=mock_client)
        assert enricher.BATCH_SIZE == 5

    def test_player_summary_loads_prompt(self, mock_client: MagicMock) -> None:
        enricher = PlayerSummaryEnricher(anthropic_client=mock_client)
        prompt = enricher._get_system_prompt()
        assert "form_trend" in prompt
        assert "{window_size}" not in prompt  # should be formatted

    def test_fixture_outlook_loads_prompt(self, mock_client: MagicMock) -> None:
        enricher = FixtureOutlookEnricher(anthropic_client=mock_client)
        prompt = enricher._get_system_prompt()
        assert "difficulty_score" in prompt


# --- Cost calculation tests -------------------------------------------------


@pytest.mark.unit
class TestCostCalculation:
    def test_calculate_cost(self) -> None:
        from fpl_enrich.handlers.enricher import _calculate_cost

        mock_enrichers = []
        for model, input_tok, output_tok in [
            ("claude-haiku-4-5-20251001", 10000, 5000),
            ("claude-sonnet-4-6-20250514", 2000, 1000),
        ]:
            e = MagicMock()
            e.MODEL = model
            e.__class__.__name__ = f"Test{model}"
            e.total_input_tokens = input_tok
            e.total_output_tokens = output_tok
            mock_enrichers.append(e)

        report = _calculate_cost(mock_enrichers)

        assert report["total_input_tokens"] == 12000
        assert report["total_output_tokens"] == 6000
        assert report["estimated_cost_usd"] > 0
        assert len(report["model_breakdown"]) == 2


def _make_handler_response(results: list[dict[str, Any]]) -> MagicMock:
    """Build a mock Anthropic messages.create() response."""
    import json

    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(results))]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    return response
