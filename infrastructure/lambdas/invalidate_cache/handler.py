"""Lambda handler to invalidate CloudFront cache after a successful pipeline run.

Triggered by EventBridge when the Step Functions pipeline execution succeeds.
Invalidates the /api/v1/* path pattern so the dashboard serves fresh data.
"""

import logging
import os
import time
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

cloudfront = boto3.client("cloudfront")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Create a CloudFront cache invalidation for dashboard data paths.

    Args:
        event: EventBridge event for Step Functions execution status change.
        context: Lambda context (unused).

    Returns:
        Dict with invalidation ID and status.
    """
    distribution_id = os.environ["CLOUDFRONT_DISTRIBUTION_ID"]

    logger.info(
        "Pipeline succeeded — invalidating CloudFront distribution %s",
        distribution_id,
    )

    response = cloudfront.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/api/v1/*"]},
            "CallerReference": f"pipeline-{int(time.time())}",
        },
    )

    invalidation_id = response["Invalidation"]["Id"]
    logger.info("Invalidation created: %s", invalidation_id)

    return {
        "statusCode": 200,
        "invalidationId": invalidation_id,
        "distributionId": distribution_id,
    }
