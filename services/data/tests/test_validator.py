"""Unit tests for data validation engine and handler."""

from unittest.mock import MagicMock

import pytest

from fpl_data.validators.engine import validate_records
from fpl_data.validators.schemas import FIXTURE_EXPECTATIONS, PLAYER_EXPECTATIONS


def _make_player(**overrides: object) -> dict:
    """Create a valid player record with optional overrides."""
    base = {
        "id": 1,
        "web_name": "Salah",
        "team": 14,
        "element_type": 3,
        "total_points": 180,
        "minutes": 2800,
    }
    base.update(overrides)
    return base


def _make_fixture(**overrides: object) -> dict:
    """Create a valid fixture record with optional overrides."""
    base = {
        "id": 1,
        "event": 1,
        "team_h": 1,
        "team_a": 2,
        "team_h_difficulty": 3,
        "team_a_difficulty": 2,
    }
    base.update(overrides)
    return base


# --- validate_records: player tests ---


@pytest.mark.unit
def test_valid_player_data_passes() -> None:
    records = [_make_player(id=1), _make_player(id=2, web_name="Haaland")]
    valid, failed = validate_records(records, PLAYER_EXPECTATIONS, "players")

    assert len(valid) == 2
    assert len(failed) == 0


@pytest.mark.unit
def test_missing_required_column_adds_error() -> None:
    record = {"id": 1, "web_name": "Salah"}  # missing team, element_type, etc.
    valid, failed = validate_records([record], PLAYER_EXPECTATIONS, "players")

    # Column presence is checked but doesn't reject individual records
    # Not-null check on "team" will fail though
    assert len(failed) == 1
    assert "null value in required column 'team'" in failed[0]["errors"][0]


@pytest.mark.unit
def test_duplicate_ids_detected() -> None:
    records = [_make_player(id=1), _make_player(id=1, web_name="Duplicate")]
    valid, failed = validate_records(records, PLAYER_EXPECTATIONS, "players")

    # Both records pass per-record checks, but uniqueness is a dataset-level error
    # logged via ExceptionCollector — records themselves aren't rejected
    assert len(valid) == 2


@pytest.mark.unit
def test_null_required_field_fails_record() -> None:
    records = [_make_player(id=1, web_name=None)]
    valid, failed = validate_records(records, PLAYER_EXPECTATIONS, "players")

    assert len(valid) == 0
    assert len(failed) == 1
    assert "web_name" in failed[0]["errors"][0]


@pytest.mark.unit
def test_value_range_violation_is_warning_not_reject() -> None:
    records = [_make_player(id=1, total_points=999)]  # above max 300
    valid, failed = validate_records(records, PLAYER_EXPECTATIONS, "players")

    # Record is still valid — range violations are warnings
    assert len(valid) == 1
    assert len(failed) == 0


@pytest.mark.unit
def test_allowed_values_violation_is_warning() -> None:
    records = [_make_player(id=1, element_type=99)]  # not in [1,2,3,4]
    valid, failed = validate_records(records, PLAYER_EXPECTATIONS, "players")

    assert len(valid) == 1  # still valid — it's a warning


# --- validate_records: fixture tests ---


@pytest.mark.unit
def test_valid_fixture_data_passes() -> None:
    records = [_make_fixture(id=1), _make_fixture(id=2)]
    valid, failed = validate_records(records, FIXTURE_EXPECTATIONS, "fixtures")

    assert len(valid) == 2
    assert len(failed) == 0


@pytest.mark.unit
def test_fixture_null_team_fails() -> None:
    records = [_make_fixture(id=1, team_h=None)]
    valid, failed = validate_records(records, FIXTURE_EXPECTATIONS, "fixtures")

    assert len(failed) == 1


# --- handler tests ---


@pytest.mark.unit
def test_handler_returns_400_on_missing_params() -> None:
    from fpl_data.handlers.validator import lambda_handler

    result = lambda_handler({"season": "2025-26"}, None)
    assert result["statusCode"] == 400
    assert "gameweek" in result["body"]["error"]


# --- DLQ writing ---


@pytest.mark.unit
def test_dlq_written_on_failure() -> None:
    from fpl_data.handlers.validator import _write_dlq

    mock_s3 = MagicMock()
    failed = [{"record": {"id": 1}, "errors": ["bad data"]}]

    _write_dlq(mock_s3, "test-bucket", "2025-26", 1, "players", failed)

    mock_s3.put_json.assert_called_once()
    call_args = mock_s3.put_json.call_args
    assert "dlq" in call_args[0][1]
    assert "players_validation_failures" in call_args[0][1]
