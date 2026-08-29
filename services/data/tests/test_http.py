"""Unit tests for the FPL API fetch helper and its S3 mirror fallback."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from curl_cffi.requests.exceptions import HTTPError

from fpl_data.collectors import http
from fpl_data.collectors.http import FPL_BASE_URL, fpl_fetch, mirror_prefix_for, read_mirror

BOOTSTRAP_URL = f"{FPL_BASE_URL}/bootstrap-static/"


def _response(status_code: int, payload: dict | list | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.content = b""
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = HTTPError(
            f"HTTP Error {status_code}: ", 0, response
        )
    return response


def _session_returning(*responses: MagicMock) -> MagicMock:
    """Patch AsyncSession so each `async with` block yields the next response."""
    session = MagicMock()
    session.get = AsyncMock(side_effect=list(responses))

    async def _aenter(_self):
        return session

    async def _aexit(_self, *_args):
        return False

    ctx = MagicMock()
    ctx.__aenter__ = _aenter
    ctx.__aexit__ = _aexit
    return MagicMock(return_value=ctx), session


def _key_at(url: str, moment: datetime) -> str:
    return f"{mirror_prefix_for(url)}{moment.isoformat()}.json"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (BOOTSTRAP_URL, "raw/fpl-api-mirror/bootstrap-static/"),
        (f"{FPL_BASE_URL}/fixtures/", "raw/fpl-api-mirror/fixtures/"),
        (f"{FPL_BASE_URL}/event/7/live/", "raw/fpl-api-mirror/event/7/live/"),
    ],
)
def test_mirror_prefix_is_derived_from_the_endpoint(url: str, expected: str) -> None:
    assert mirror_prefix_for(url) == expected


@pytest.mark.unit
def test_read_mirror_returns_the_newest_snapshot() -> None:
    now = datetime.now(UTC)
    older = _key_at(BOOTSTRAP_URL, now - timedelta(hours=6))
    newest = _key_at(BOOTSTRAP_URL, now - timedelta(hours=1))

    client = MagicMock()
    client.list_objects.return_value = [older, newest]
    client.read_json.return_value = {"elements": [{"id": 1}]}

    with patch.object(http, "S3Client", return_value=client):
        assert read_mirror(BOOTSTRAP_URL, bucket="test-bucket") == {"elements": [{"id": 1}]}

    client.read_json.assert_called_once_with("test-bucket", newest)


@pytest.mark.unit
def test_read_mirror_raises_when_no_snapshot_exists() -> None:
    client = MagicMock()
    client.list_objects.return_value = []

    with (
        patch.object(http, "S3Client", return_value=client),
        pytest.raises(FileNotFoundError, match="No mirrored snapshot"),
    ):
        read_mirror(BOOTSTRAP_URL, bucket="test-bucket")


@pytest.mark.unit
def test_read_mirror_refuses_a_stale_snapshot() -> None:
    stale = _key_at(BOOTSTRAP_URL, datetime.now(UTC) - (http.MAX_MIRROR_AGE + timedelta(hours=1)))

    client = MagicMock()
    client.list_objects.return_value = [stale]

    with (
        patch.object(http, "S3Client", return_value=client),
        pytest.raises(RuntimeError, match="refusing to serve it as current data"),
    ):
        read_mirror(BOOTSTRAP_URL, bucket="test-bucket")

    client.read_json.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fpl_fetch_returns_live_data_when_the_request_succeeds() -> None:
    session_cls, session = _session_returning(_response(200, {"elements": []}))

    with patch.object(http, "AsyncSession", session_cls):
        assert await fpl_fetch(BOOTSTRAP_URL) == {"elements": []}

    assert session.get.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fpl_fetch_retries_a_403_on_a_fresh_session() -> None:
    session_cls, session = _session_returning(_response(403), _response(200, {"elements": []}))

    with patch.object(http, "AsyncSession", session_cls), patch.object(http.asyncio, "sleep"):
        assert await fpl_fetch(BOOTSTRAP_URL) == {"elements": []}

    # One session per attempt — a retry down the rejected connection cannot recover.
    assert session_cls.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fpl_fetch_falls_back_to_the_mirror_when_every_attempt_is_blocked() -> None:
    session_cls, _ = _session_returning(*[_response(403) for _ in range(3)])

    with (
        patch.object(http, "AsyncSession", session_cls),
        patch.object(http.asyncio, "sleep"),
        patch.object(http, "read_mirror", return_value={"elements": [{"id": 9}]}) as read,
    ):
        assert await fpl_fetch(BOOTSTRAP_URL) == {"elements": [{"id": 9}]}

    read.assert_called_once_with(BOOTSTRAP_URL)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fpl_fetch_raises_rather_than_mirroring_when_the_mirror_is_disallowed() -> None:
    session_cls, _ = _session_returning(*[_response(403) for _ in range(3)])

    with (
        patch.object(http, "AsyncSession", session_cls),
        patch.object(http.asyncio, "sleep"),
        patch.object(http, "read_mirror") as read,
        pytest.raises(HTTPError),
    ):
        await fpl_fetch(BOOTSTRAP_URL, allow_mirror=False)

    read.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fpl_fetch_does_not_retry_a_non_403_error() -> None:
    session_cls, session = _session_returning(_response(500))

    with patch.object(http, "AsyncSession", session_cls), pytest.raises(HTTPError):
        await fpl_fetch(BOOTSTRAP_URL)

    assert session.get.call_count == 1
