"""Unit tests for NeonClient pool behaviour.

The critical property we test: every ``fetch`` / ``fetch_one`` / ``execute``
call acquires its own connection from the pool. Without this, concurrent
callers (agent tools run via ``asyncio.gather``) would race on a single
``asyncpg.Connection`` and raise ``InterfaceError: another operation is in
progress``.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fpl_lib.clients.neon import NeonClient

pytestmark = pytest.mark.unit


def _make_pool_mock(fetch: Any = None, fetch_one: Any = None, execute: str = "OK") -> MagicMock:
    """Fake pool whose ``acquire()`` returns an async context manager
    yielding a per-call Connection mock."""
    pool = MagicMock()

    def _acquire() -> Any:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=fetch or [])
        conn.fetchrow = AsyncMock(return_value=fetch_one)
        conn.execute = AsyncMock(return_value=execute)
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    pool.acquire = _acquire
    pool.close = AsyncMock()
    return pool


@pytest.mark.asyncio
async def test_connect_passes_pool_sizing_and_init_callback() -> None:
    captured = {}

    async def fake_create_pool(url: str, **kwargs: Any) -> MagicMock:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _make_pool_mock()

    async def init_cb(_conn: Any) -> None: ...

    with patch("fpl_lib.clients.neon.asyncpg.create_pool", side_effect=fake_create_pool):
        client = NeonClient("postgres://x", min_size=2, max_size=7, init=init_cb)
        await client.connect()
        await client.close()

    assert captured["url"] == "postgres://x"
    assert captured["kwargs"]["min_size"] == 2
    assert captured["kwargs"]["max_size"] == 7
    assert captured["kwargs"]["init"] is init_cb


@pytest.mark.asyncio
async def test_fetch_acquires_connection_from_pool() -> None:
    pool = _make_pool_mock(fetch=[{"id": 1}])

    with patch("fpl_lib.clients.neon.asyncpg.create_pool", AsyncMock(return_value=pool)):
        async with NeonClient("postgres://x") as client:
            result = await client.fetch("SELECT 1")

    assert result == [{"id": 1}]


@pytest.mark.asyncio
async def test_fetch_one_acquires_connection_from_pool() -> None:
    pool = _make_pool_mock(fetch_one={"id": 1})

    with patch("fpl_lib.clients.neon.asyncpg.create_pool", AsyncMock(return_value=pool)):
        async with NeonClient("postgres://x") as client:
            row = await client.fetch_one("SELECT 1 LIMIT 1")

    assert row == {"id": 1}


@pytest.mark.asyncio
async def test_concurrent_calls_each_acquire_their_own_connection() -> None:
    """Regression guard for the "single shared connection" bug.

    Kicks off three concurrent calls via asyncio.gather and asserts each
    one acquired a distinct connection from the pool — i.e. no caller is
    serialised behind another on the same asyncpg.Connection.
    """
    acquired_conns: list[Any] = []
    pool = MagicMock()

    def _acquire() -> Any:
        idx = len(acquired_conns)
        conn = MagicMock(name=f"conn{idx}")

        async def _slow_fetch(*_args: Any, **_kwargs: Any) -> list[dict[str, int]]:
            await asyncio.sleep(0.02)
            return [{"id": idx}]

        conn.fetch = _slow_fetch
        acquired_conns.append(conn)
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    pool.acquire = _acquire
    pool.close = AsyncMock()

    with patch("fpl_lib.clients.neon.asyncpg.create_pool", AsyncMock(return_value=pool)):
        async with NeonClient("postgres://x") as client:
            results = await asyncio.gather(
                client.fetch("q1"),
                client.fetch("q2"),
                client.fetch("q3"),
            )

    assert len(acquired_conns) == 3
    assert len({id(c) for c in acquired_conns}) == 3
    assert results == [[{"id": 0}], [{"id": 1}], [{"id": 2}]]


@pytest.mark.asyncio
async def test_methods_raise_if_not_connected() -> None:
    client = NeonClient("postgres://x")
    with pytest.raises(RuntimeError, match="not connected"):
        await client.fetch("SELECT 1")


@pytest.mark.asyncio
async def test_connection_context_manager_yields_raw_connection() -> None:
    pool = _make_pool_mock(fetch=[{"x": 1}])

    with patch("fpl_lib.clients.neon.asyncpg.create_pool", AsyncMock(return_value=pool)):
        async with NeonClient("postgres://x") as client:
            async with client.connection() as conn:
                rows = await conn.fetch("SELECT 1")

    assert rows == [{"x": 1}]
