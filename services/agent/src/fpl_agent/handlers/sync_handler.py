"""Lambda handler for syncing player embeddings into Neon pgvector.

Reads curated player data from S3, generates embeddings, and upserts
into the Neon vector database. Triggered by Step Functions after
the curate stage completes.
"""

import logging
from typing import Any

import boto3
from pgvector.asyncpg import register_vector

from fpl_agent.embeddings.embedder import PlayerEmbedder
from fpl_agent.embeddings.sync_embeddings import sync_embeddings
from fpl_lib.clients.neon import NeonClient
from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.run_handler import RunHandler

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "fpl-data-lake-dev"
NEON_SECRET_ID = "/fpl-platform/dev/neon-database-url"


def _get_neon_database_url() -> str:
    """Retrieve the Neon database URL from Secrets Manager."""
    sm = boto3.client("secretsmanager", region_name="eu-west-2")
    resp = sm.get_secret_value(SecretId=NEON_SECRET_ID)
    return resp["SecretString"]


async def main(
    season: str,
    gameweek: int,
    output_bucket: str = DEFAULT_BUCKET,
    force: bool = False,
) -> dict[str, Any]:
    """Sync player embeddings from curated S3 data into Neon pgvector.

    Args:
        season: Season string, e.g. "2025-26".
        gameweek: Gameweek number.
        output_bucket: S3 bucket containing curated data.
        force: Not currently used; reserved for future skip-if-exists logic.

    Returns:
        Dict with players_synced, embedding_dim, and duration_seconds.
    """
    database_url = _get_neon_database_url()
    s3_client = S3Client()
    embedder = PlayerEmbedder()

    async with NeonClient(database_url) as neon_client:
        await register_vector(neon_client._conn)
        result = await sync_embeddings(
            s3_client=s3_client,
            neon_client=neon_client,
            embedder=embedder,
            bucket=output_bucket,
            season=season,
            gameweek=gameweek,
        )

    return result


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for embedding sync."""
    return RunHandler(
        main_func=main,
        required_main_params=["season", "gameweek"],
        optional_main_params=["output_bucket", "force"],
    ).lambda_executor(lambda_event=event)
