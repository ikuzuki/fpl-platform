"""Stub API handler for the Scout Agent.

The real LangGraph-backed implementation lands in Wave 3 (ikuzuki/fpl-platform#91).
This stub exists so Wave 2 Terraform can provision the Lambda and API Gateway
with an image that actually responds, letting us validate wiring end-to-end
before the agent logic is built.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Return 200 on /health, 501 on everything else.

    API Gateway v2 payload format 2.0 puts the path in `event["rawPath"]`.
    """
    path = event.get("rawPath", "")
    logger.info("agent stub received request: path=%s", path)

    if path == "/health":
        return {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"status": "ok", "stub": True}),
        }

    return {
        "statusCode": 501,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"error": "agent not yet implemented — see issue #91"}),
    }
