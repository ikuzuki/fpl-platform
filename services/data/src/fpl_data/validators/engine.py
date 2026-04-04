"""Validation engine that runs schema checks against raw data records."""

import logging
from typing import Any

from fpl_lib.core.exception_collector import ExceptionCollector

logger = logging.getLogger(__name__)


def validate_records(
    records: list[dict[str, Any]],
    schema: dict[str, Any],
    dataset_name: str,
) -> tuple[list[dict], list[dict]]:
    """Validate a list of records against a schema.

    Uses ExceptionCollector to accumulate ALL errors (not fail-fast).
    Critical errors (missing columns, duplicate IDs) are errors.
    Value range violations are warnings.

    Args:
        records: List of raw data dicts to validate.
        schema: Validation schema with column_presence, not_null, unique, value_ranges.
        dataset_name: Name for logging (e.g. "players", "fixtures").

    Returns:
        Tuple of (valid_records, failed_records).
    """
    collector = ExceptionCollector(f"{dataset_name} validation")
    failed: list[dict] = []
    valid: list[dict] = []

    # Column presence check (critical — checked once on first record)
    if records:
        _check_column_presence(collector, records[0], schema)

    # Uniqueness check (critical — checked across all records)
    _check_uniqueness(collector, records, schema)

    # Per-record checks
    for i, record in enumerate(records):
        record_id = record.get("id", f"row-{i}")
        record_errors: list[str] = []

        # Not-null check (critical)
        for col in schema.get("not_null", []):
            if record.get(col) is None:
                record_errors.append(f"null value in required column '{col}'")

        # Value range checks (warnings — don't reject the record)
        for col, constraints in schema.get("value_ranges", {}).items():
            val = record.get(col)
            if val is None:
                continue
            if "allowed" in constraints:
                if val not in constraints["allowed"]:
                    collector.add_warning(
                        f"Record {record_id}: {col}={val} not in allowed values {constraints['allowed']}"
                    )
            else:
                if "min" in constraints and val < constraints["min"]:
                    collector.add_warning(
                        f"Record {record_id}: {col}={val} below min {constraints['min']}"
                    )
                if "max" in constraints and val > constraints["max"]:
                    collector.add_warning(
                        f"Record {record_id}: {col}={val} above max {constraints['max']}"
                    )

        if record_errors:
            failed.append({"record": record, "errors": record_errors})
        else:
            valid.append(record)

    # Log warnings but don't raise — only critical errors raise
    if collector.warnings:
        logger.warning(
            "%s validation: %d warning(s):\n%s",
            dataset_name,
            len(collector.warnings),
            "\n".join(f"  - {w}" for w in collector.warnings),
        )

    # Critical errors raise CollectedError
    if collector.errors:
        logger.error(
            "%s validation: %d critical error(s):\n%s",
            dataset_name,
            len(collector.errors),
            "\n".join(f"  - {e}" for e in collector.errors),
        )

    return valid, failed


def _check_column_presence(
    collector: ExceptionCollector,
    record: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """Check that all required columns are present."""
    for col in schema.get("column_presence", []):
        if col not in record:
            collector.add_error(f"Missing required column: '{col}'")


def _check_uniqueness(
    collector: ExceptionCollector,
    records: list[dict[str, Any]],
    schema: dict[str, Any],
) -> None:
    """Check that unique columns have no duplicate values."""
    for col in schema.get("unique", []):
        seen: set = set()
        duplicates: list = []
        for record in records:
            val = record.get(col)
            if val in seen:
                duplicates.append(val)
            seen.add(val)
        if duplicates:
            collector.add_error(
                f"Duplicate values in '{col}': {duplicates[:10]}"
                + (f" (and {len(duplicates) - 10} more)" if len(duplicates) > 10 else "")
            )
