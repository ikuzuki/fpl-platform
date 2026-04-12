"""Shared HTTP fetch for the FPL API with Cloudflare bypass.

All FPL API collectors should use `fpl_fetch` instead of implementing
their own retry logic. Uses curl_cffi with Chrome TLS impersonation to
bypass Cloudflare fingerprint-based blocking on AWS Lambda IPs.
"""

import asyncio
import logging

from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

FPL_BASE_URL = "https://fantasy.premierleague.com/api"


async def fpl_fetch(url: str, max_retries: int = 5) -> dict | list:
    """Fetch JSON from the FPL API with exponential backoff on 403.

    Args:
        url: Full URL to fetch.
        max_retries: Maximum number of attempts (default 5).

    Returns:
        Parsed JSON response (dict or list).

    Raises:
        curl_cffi.requests.errors.RequestsError: On non-403 HTTP errors.
    """
    async with AsyncSession(impersonate="chrome", timeout=30) as session:
        for attempt in range(max_retries):
            logger.info("[FPL API] GET %s (attempt %d/%d)", url, attempt + 1, max_retries)
            response = await session.get(url)
            logger.info(
                "[FPL API] %s | status=%d | size=%d bytes",
                url.split("/api/")[-1] if "/api/" in url else url,
                response.status_code,
                len(response.content),
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 403 and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2, 4, 8, 16, 32 seconds
                logger.warning(
                    "[FPL API] 403 Forbidden — retrying in %ds (attempt %d/%d)",
                    wait,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()

    response.raise_for_status()
    return response.json()  # unreachable but satisfies type checker
