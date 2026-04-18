"""Async Postgres client wrapper for Neon with pgvector support.

Backed by an :class:`asyncpg.Pool` rather than a single connection, so
concurrent callers (e.g. the agent's tool executor running queries in
parallel via ``asyncio.gather``) don't race on a shared connection.
asyncpg explicitly forbids concurrent queries on one connection — the
second raises ``InterfaceError: another operation is in progress``.

The public API (``execute`` / ``fetch`` / ``fetch_one``) stays the same;
each call internally acquires a connection from the pool and releases it
when done. If you need multi-statement / transactional work on the same
connection, use :meth:`connection` as an async context manager.

Extension setup (e.g. ``pgvector.asyncpg.register_vector``) that needs to
run on every connection should be passed via the ``init`` parameter —
asyncpg invokes it once per new pool connection.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

ConnectionInit = Callable[[asyncpg.Connection], Awaitable[None]]


class NeonClient:
    """Async pool-backed wrapper around asyncpg for Neon Postgres operations."""

    def __init__(
        self,
        database_url: str,
        *,
        min_size: int = 1,
        max_size: int = 5,
        init: ConnectionInit | None = None,
    ) -> None:
        """Initialise the client (no connection opened yet).

        Args:
            database_url: Postgres connection string.
            min_size: Minimum pool size; asyncpg keeps this many connections
                alive while the pool is open. Default 1 keeps Lambda cold-start
                cost low while still holding one warm connection across
                invocations.
            max_size: Maximum pool size. Default 5 matches the expected
                worst-case concurrency (agent fires up to ~5 tools in one
                plan via asyncio.gather).
            init: Optional async callback ``(conn) -> None`` run on every new
                pool connection. Used by the agent to call
                ``pgvector.asyncpg.register_vector`` so vector types round-trip
                natively on every connection the pool hands out.
        """
        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._init = init
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Open the pool."""
        self._pool = await asyncpg.create_pool(
            self._database_url,
            min_size=self._min_size,
            max_size=self._max_size,
            init=self._init,
        )
        logger.info("Opened Neon pool (min=%d, max=%d)", self._min_size, self._max_size)

    async def close(self) -> None:
        """Close the pool and all its connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Closed Neon pool")

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a statement on a pooled connection."""
        pool = self._require_pool()
        async with pool.acquire() as conn:
            result: str = await conn.execute(query, *args)
            return result

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Run a SELECT on a pooled connection and return all rows."""
        pool = self._require_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetch_one(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Run a SELECT on a pooled connection and return the first row, or None."""
        pool = self._require_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a raw connection for multi-statement or transactional work.

        Prefer the top-level ``execute`` / ``fetch`` / ``fetch_one`` methods
        when you only need a single query — they release the connection
        immediately. Use this context manager only when you need several
        statements to run on the same connection (e.g. a transaction).
        """
        pool = self._require_pool()
        async with pool.acquire() as conn:
            yield conn

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                "NeonClient is not connected. Call connect() or use as async context manager."
            )
        return self._pool

    async def __aenter__(self) -> "NeonClient":
        await self.connect()
        return self

    async def __aexit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any
    ) -> None:
        await self.close()
