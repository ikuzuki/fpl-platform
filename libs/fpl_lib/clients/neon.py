"""Async Postgres client wrapper for Neon with pgvector support.

Uses asyncpg for async connections. Connection string sourced from
Secrets Manager or environment variable NEON_DATABASE_URL.
"""

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class NeonClient:
    """Async wrapper around asyncpg for Neon Postgres operations."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn: asyncpg.Connection | None = None

    async def connect(self) -> None:
        """Establish connection to Neon Postgres."""
        self._conn = await asyncpg.connect(self._database_url)
        logger.info("Connected to Neon Postgres")

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Closed Neon Postgres connection")

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status string."""
        self._ensure_connected()
        result: str = await self._conn.execute(query, *args)  # type: ignore[union-attr]
        return result

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a query and return all rows."""
        self._ensure_connected()
        return await self._conn.fetch(query, *args)  # type: ignore[union-attr]

    async def fetch_one(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute a query and return a single row, or None."""
        self._ensure_connected()
        return await self._conn.fetchrow(query, *args)  # type: ignore[union-attr]

    def _ensure_connected(self) -> None:
        """Raise if the client has not been connected."""
        if self._conn is None:
            raise RuntimeError(
                "NeonClient is not connected. Call connect() or use as async context manager."
            )

    async def __aenter__(self) -> "NeonClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        await self.close()
