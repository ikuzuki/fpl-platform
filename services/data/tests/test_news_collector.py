"""Unit tests for News/RSS collector."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from fpl_data.collectors.news_collector import NewsCollector


def _make_feed_entry(
    title: str,
    published: str,
    link: str = "https://example.com",
    date_tuple: tuple[int, int, int] | None = None,
) -> SimpleNamespace:
    """Create a mock feedparser entry."""
    published_parsed = None
    if date_tuple:
        published_parsed = time.struct_time((*date_tuple, 0, 0, 0, 0, 0, 0))
    return SimpleNamespace(
        title=title,
        summary=f"Summary of {title}",
        link=link,
        published=published,
        published_parsed=published_parsed,
    )


def _make_feed(entries: list) -> SimpleNamespace:
    """Create a mock feedparser result."""
    return SimpleNamespace(entries=entries)


@pytest.fixture
def mock_s3_client() -> MagicMock:
    client = MagicMock()
    client.object_exists.return_value = False
    client.put_json.return_value = None
    return client


@pytest.fixture
def collector(mock_s3_client: MagicMock) -> NewsCollector:
    return NewsCollector(s3_client=mock_s3_client, output_bucket="test-bucket")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_rss_feeds_success(
    collector: NewsCollector,
    mock_s3_client: MagicMock,
) -> None:
    feed = _make_feed(
        [
            _make_feed_entry(
                "Salah scores hat-trick",
                "Fri, 04 Apr 2026 12:00:00 GMT",
                date_tuple=(2026, 4, 4),
            ),
            _make_feed_entry(
                "Haaland injured",
                "Fri, 04 Apr 2026 14:00:00 GMT",
                date_tuple=(2026, 4, 4),
            ),
            _make_feed_entry(
                "Old article",
                "Thu, 03 Apr 2026 10:00:00 GMT",
                date_tuple=(2026, 4, 3),
            ),
        ]
    )
    with patch("fpl_data.collectors.news_collector.feedparser.parse", return_value=feed):
        result = await collector.collect_rss_feeds("2026-04-04")

    assert result.status == "success"
    # 2 matching articles × 3 RSS feeds = 6
    assert result.records_collected == 6
    assert result.output_path == "raw/news/date=2026-04-04/rss_articles.jsonl"
    mock_s3_client.put_json.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_rss_feeds_filters_by_date(
    collector: NewsCollector,
    mock_s3_client: MagicMock,
) -> None:
    feed = _make_feed(
        [
            _make_feed_entry("Wrong day", "Thu, 03 Apr 2026 10:00:00 GMT", date_tuple=(2026, 4, 3)),
            _make_feed_entry(
                "Also wrong", "Wed, 02 Apr 2026 10:00:00 GMT", date_tuple=(2026, 4, 2)
            ),
        ]
    )
    with patch("fpl_data.collectors.news_collector.feedparser.parse", return_value=feed):
        result = await collector.collect_rss_feeds("2026-04-04")

    assert result.records_collected == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_rss_feeds_skips_if_exists(
    collector: NewsCollector,
    mock_s3_client: MagicMock,
) -> None:
    mock_s3_client.object_exists.return_value = True

    with patch("fpl_data.collectors.news_collector.feedparser.parse") as mock_parse:
        result = await collector.collect_rss_feeds("2026-04-04")

    mock_parse.assert_not_called()
    assert result.records_collected == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_rss_feeds_handles_parse_error(
    collector: NewsCollector,
    mock_s3_client: MagicMock,
) -> None:
    with patch(
        "fpl_data.collectors.news_collector.feedparser.parse",
        side_effect=Exception("Parse error"),
    ):
        result = await collector.collect_rss_feeds("2026-04-04")

    # Should not crash — logs the error and returns 0 articles
    assert result.status == "success"
    assert result.records_collected == 0
