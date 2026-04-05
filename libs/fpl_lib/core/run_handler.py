"""RunHandler pattern for wrapping async functions as Lambda handlers."""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Set root logger to INFO for Lambda environments.

    Lambda defaults to WARNING, which suppresses all our INFO-level logs.
    Only configures if no handlers are set (avoids duplicate setup).
    """
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(levelname)s] %(asctime)s %(name)s: %(message)s",
        )
    else:
        root.setLevel(logging.INFO)


class RunHandler:
    """Wraps an async main function for Lambda execution.

    Usage:
        async def main(gameweek: int, season: str = "2025-26") -> dict:
            ...

        def lambda_handler(event, context):
            return RunHandler(
                main_func=main,
                required_main_params=["gameweek"],
                optional_main_params=["season"],
            ).lambda_executor(lambda_event=event)
    """

    def __init__(
        self,
        main_func: Callable[..., Any],
        required_main_params: list[str] | None = None,
        optional_main_params: list[str] | None = None,
    ) -> None:
        self.main_func = main_func
        self.required_main_params = required_main_params or []
        self.optional_main_params = optional_main_params or []

    def lambda_executor(self, lambda_event: dict[str, Any]) -> dict[str, Any]:
        """Parse params from Lambda event and execute the main function."""
        _configure_logging()
        handler_name = self.main_func.__module__ + "." + self.main_func.__name__
        start_time = time.time()

        try:
            params = self._extract_params(lambda_event)
            logger.info(
                "[START] %s | params=%s",
                handler_name,
                json.dumps(params, default=str),
            )

            result = asyncio.run(self.main_func(**params))

            duration = time.time() - start_time
            logger.info(
                "[SUCCESS] %s | duration=%.2fs | result_keys=%s",
                handler_name,
                duration,
                list(result.keys()) if isinstance(result, dict) else type(result).__name__,
            )

            return {
                "statusCode": 200,
                "body": result if isinstance(result, dict) else {"result": str(result)},
            }
        except ValueError as e:
            duration = time.time() - start_time
            logger.error(
                "[ERROR] %s | duration=%.2fs | type=ValueError | error=%s",
                handler_name,
                duration,
                e,
            )
            return {"statusCode": 400, "body": {"error": str(e)}}
        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "[ERROR] %s | duration=%.2fs | type=%s | error=%s",
                handler_name,
                duration,
                type(e).__name__,
                e,
            )
            return {"statusCode": 500, "body": {"error": str(e)}}

    def _extract_params(self, event: dict[str, Any]) -> dict[str, Any]:
        """Extract required and optional parameters from the event dict."""
        params: dict[str, Any] = {}

        for param in self.required_main_params:
            if param not in event:
                raise ValueError(f"Missing required parameter: {param}")
            params[param] = event[param]

        for param in self.optional_main_params:
            if param in event:
                params[param] = event[param]

        return params
