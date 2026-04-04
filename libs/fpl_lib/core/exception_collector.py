"""Exception collector for accumulating errors during batch processing."""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class NonCriticalError(Exception):
    """An error that should be logged as a warning, not a failure."""


class CollectedError(Exception):
    """Raised when ExceptionCollector exits with accumulated errors."""

    def __init__(self, operation_name: str, errors: list[str]) -> None:
        self.operation_name = operation_name
        self.errors = errors
        super().__init__(
            f"{operation_name} failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


class ExceptionCollector:
    """Collect exceptions gracefully, raising all at once on exit.

    Usage:
        with ExceptionCollector("data validation") as collector:
            collector.safe_execute(validate_row, "row 1", row_data)
            collector.safe_execute(validate_row, "row 2", row_data)
        # Raises CollectedErrors if any errors were accumulated
    """

    def __init__(self, operation_name: str) -> None:
        self.operation_name = operation_name
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def __enter__(self) -> "ExceptionCollector":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self._log_if_warnings()
        self._raise_if_errors()

    def safe_execute(
        self,
        func: Callable[..., Any],
        error_context: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute func, catching exceptions as collected errors."""
        try:
            return func(*args, **kwargs)
        except NonCriticalError as e:
            self.warnings.append(f"{error_context}: {e}")
        except Exception as e:
            self.errors.append(f"{error_context}: {e}")
        return None

    def add_error(self, message: str) -> None:
        """Manually add an error."""
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Manually add a warning."""
        self.warnings.append(message)

    def _log_if_warnings(self) -> None:
        if self.warnings:
            logger.warning(
                "%s completed with %d warning(s):\n%s",
                self.operation_name,
                len(self.warnings),
                "\n".join(f"  - {w}" for w in self.warnings),
            )

    def _raise_if_errors(self) -> None:
        if self.errors:
            raise CollectedError(self.operation_name, self.errors)
