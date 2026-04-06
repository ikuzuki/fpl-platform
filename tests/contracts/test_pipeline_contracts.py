"""Contract tests: verify data schemas match between pipeline stages.

These are pure-Python tests with no I/O — they validate that each service's
output schema matches what the downstream service expects to read.
"""

from typing import Any

import pytest

from fpl_data.transformers.player_transformer import (
    COLUMN_MAP,
    UNDERSTAT_RENAME,
    flatten_player_data,
    join_understat,
)
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
from fpl_enrich.handlers.merge_enrichments import ENRICHER_NAMES
from fpl_lib.core.responses import (
    CollectionResponse,
    CurationResult,
    EnrichmentResult,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# 1. Collection → Transformation contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectionToTransformContract:
    """Verify that flatten_player_data produces all expected clean columns."""

    def test_bootstrap_json_survives_flatten(self, minimal_bootstrap_raw: dict[str, Any]) -> None:
        """Raw bootstrap elements can be flattened into the expected column set."""
        df = flatten_player_data(minimal_bootstrap_raw, season="2025-26")

        # Must contain every mapped column
        expected_columns = set(COLUMN_MAP.values()) | {"season", "collected_at"}
        assert expected_columns.issubset(set(df.columns)), (
            f"Missing columns after flatten: {expected_columns - set(df.columns)}"
        )

        # Row count matches elements
        assert len(df) == len(minimal_bootstrap_raw["elements"])

    def test_flatten_plus_understat_join_produces_full_clean_schema(
        self,
        minimal_bootstrap_raw: dict[str, Any],
        minimal_understat_data: list[dict[str, Any]],
    ) -> None:
        """Clean schema includes both bootstrap and Understat columns."""
        df = flatten_player_data(minimal_bootstrap_raw, season="2025-26")
        df = join_understat(df, minimal_understat_data)

        understat_cols = set(UNDERSTAT_RENAME.values())
        assert understat_cols.issubset(set(df.columns)), (
            f"Missing Understat columns: {understat_cols - set(df.columns)}"
        )


# ---------------------------------------------------------------------------
# 2. Transformation → Enrichment contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTransformToEnrichContract:
    """Verify clean DataFrame has all fields each enricher needs."""

    def test_clean_columns_include_enricher_relevant_fields(
        self,
        minimal_bootstrap_raw: dict[str, Any],
        minimal_understat_data: list[dict[str, Any]],
    ) -> None:
        """Each enricher's RELEVANT_FIELDS are present in the clean DataFrame."""
        df = flatten_player_data(minimal_bootstrap_raw, season="2025-26")
        df = join_understat(df, minimal_understat_data)
        clean_columns = set(df.columns)

        enrichers = [
            PlayerSummaryEnricher,
            InjurySignalEnricher,
            SentimentEnricher,
            FixtureOutlookEnricher,
        ]

        for enricher_cls in enrichers:
            relevant = enricher_cls.RELEVANT_FIELDS
            if relevant is None:
                continue
            # Some fields are injected at enrichment time (e.g. news_articles,
            # upcoming_fixtures) — skip those since they come from the handler
            injected_fields = {"news_articles", "upcoming_fixtures"}
            expected = set(relevant) - injected_fields
            missing = expected - clean_columns
            assert not missing, (
                f"{enricher_cls.__name__}.RELEVANT_FIELDS not in clean schema: {missing}"
            )

    def test_clean_has_sort_key_for_enrichment_filtering(
        self,
        minimal_bootstrap_raw: dict[str, Any],
    ) -> None:
        """Clean data has selected_by_percent used to filter top 300."""
        df = flatten_player_data(minimal_bootstrap_raw, season="2025-26")
        assert "selected_by_percent" in df.columns


# ---------------------------------------------------------------------------
# 3. Enrichment → Curation contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnrichToCurateContract:
    """Verify enricher output columns match what curate expects to read."""

    # Columns the curator reads via row.get() in build_player_dashboard
    CURATOR_ENRICHMENT_COLUMNS = {
        "player_summary_summary",
        "player_summary_form_trend",
        "player_summary_confidence",
        "injury_signal_risk_score",
        "injury_signal_reasoning",
        "sentiment_sentiment",
        "sentiment_score",
        "sentiment_key_themes",
        "fixture_outlook_best_gameweeks",
        "fixture_outlook_recommendation",
    }

    # Mapping: enricher name (as in ENRICHER_NAMES) → Pydantic model
    ENRICHER_MODELS: dict[str, type] = {
        "player_summary": PlayerSummaryOutput,
        "injury_signal": InjurySignalOutput,
        "sentiment": SentimentOutput,
        "fixture_outlook": FixtureOutlookOutput,
    }

    def test_enricher_prefixed_columns_match_curator_expectations(self) -> None:
        """Merge prefix + model field names produce the columns curate reads."""
        produced_columns: set[str] = set()
        for enricher_name, model_cls in self.ENRICHER_MODELS.items():
            for field_name in model_cls.model_fields:
                produced_columns.add(f"{enricher_name}_{field_name}")

        missing = self.CURATOR_ENRICHMENT_COLUMNS - produced_columns
        assert not missing, f"Curator expects columns not produced by enrichers: {missing}"

    def test_merge_enrichments_uses_correct_prefixes(self) -> None:
        """ENRICHER_NAMES in merge_enrichments.py match the expected prefixes."""
        expected_prefixes = {"player_summary", "injury_signal", "sentiment", "fixture_outlook"}
        assert set(ENRICHER_NAMES) == expected_prefixes


# ---------------------------------------------------------------------------
# 4. Curation → Pydantic output models contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCurateOutputContract:
    """Verify curator output rows validate against Pydantic models."""

    def test_curator_output_validates_against_pydantic_models(
        self,
        enricher_output_samples: dict[str, dict[str, Any]],
    ) -> None:
        """The enricher Pydantic models accept the sample outputs."""
        model_map = {
            "playersummary": PlayerSummaryOutput,
            "injurysignal": InjurySignalOutput,
            "sentiment": SentimentOutput,
            "fixtureoutlook": FixtureOutlookOutput,
        }
        for prefix, sample in enricher_output_samples.items():
            model_cls = model_map[prefix]
            validated = model_cls.model_validate(sample)
            assert validated is not None, f"Failed to validate {prefix} output"


# ---------------------------------------------------------------------------
# 5. Response model status literals
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResponseModelContracts:
    """Verify response models accept all status values handlers return."""

    def test_collection_response_status_values(self) -> None:
        for status in ("success", "partial", "failed"):
            resp = CollectionResponse(status=status, records_collected=0, output_path="test")
            assert resp.status == status

    def test_validation_result_status_values(self) -> None:
        for status in ("valid", "invalid", "partial"):
            resp = ValidationResult(status=status)
            assert resp.status == status

    def test_enrichment_result_status_values(self) -> None:
        for status in ("success", "partial", "failed"):
            resp = EnrichmentResult(status=status)
            assert resp.status == status

    def test_curation_result_status_values(self) -> None:
        for status in ("success", "partial", "failed"):
            resp = CurationResult(status=status)
            assert resp.status == status
