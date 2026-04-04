"""RunHandler pattern for wrapping async functions as Lambda handlers."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


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
        try:
            params = self._extract_params(lambda_event)
            logger.info("Executing %s with params: %s", self.main_func.__name__, params)

            result = asyncio.run(self.main_func(**params))

            return {
                "statusCode": 200,
                "body": result if isinstance(result, dict) else {"result": str(result)},
            }
        except ValueError as e:
            logger.error("Parameter error: %s", e)
            return {"statusCode": 400, "body": {"error": str(e)}}
        except Exception as e:
            logger.exception("Handler failed: %s", e)
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
