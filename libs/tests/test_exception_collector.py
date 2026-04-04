"""Tests for ExceptionCollector."""

import pytest

from fpl_lib.core.exception_collector import (
    CollectedError,
    ExceptionCollector,
    NonCriticalError,
)


@pytest.mark.unit
class TestExceptionCollector:
    def test_no_errors_exits_cleanly(self) -> None:
        with ExceptionCollector("test op") as collector:
            pass
        assert collector.errors == []
        assert collector.warnings == []

    def test_collects_errors_and_raises_on_exit(self) -> None:
        with pytest.raises(CollectedError, match="2 error"), ExceptionCollector("test op") as collector:
            collector.add_error("first error")
            collector.add_error("second error")

    def test_collects_warnings_without_raising(self) -> None:
        with ExceptionCollector("test op") as collector:
            collector.add_warning("minor issue")
        assert len(collector.warnings) == 1
        assert collector.errors == []

    def test_safe_execute_success(self) -> None:
        def add(a: int, b: int) -> int:
            return a + b

        with ExceptionCollector("test op") as collector:
            result = collector.safe_execute(add, "addition", 2, 3)
        assert result == 5
        assert collector.errors == []

    def test_safe_execute_catches_error(self) -> None:
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(CollectedError), ExceptionCollector("test op") as collector:
            collector.safe_execute(fail, "failing func")
        assert len(collector.errors) == 1
        assert "boom" in collector.errors[0]

    def test_safe_execute_catches_non_critical_as_warning(self) -> None:
        def warn() -> None:
            raise NonCriticalError("just a warning")

        with ExceptionCollector("test op") as collector:
            collector.safe_execute(warn, "warning func")
        assert len(collector.warnings) == 1
        assert collector.errors == []

    def test_collected_errors_message_format(self) -> None:
        err = CollectedError("my op", ["err1", "err2"])
        assert "my op" in str(err)
        assert "2 error(s)" in str(err)
        assert "err1" in str(err)
        assert "err2" in str(err)
