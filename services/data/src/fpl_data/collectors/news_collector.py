"""Collector for football news from RSS feeds and NewsAPI.

Collects broadly — the LLM enrichment layer filters for FPL relevance later.
"""

import json
import logging
from datetime import UTC, datetime

import feedparser
import httpx

from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import CollectionResponse

logger = logging.getLogger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"

RSS_FEEDS: dict[str, str] = {
    "bbc_football": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky_sports": "https://www.skysports.com/rss/12040",
    "the_guardian_football": "https://www.theguardian.com/football/rss",
}


class NewsCollector:
    """Collects football news from RSS feeds and NewsAPI."""

    def __init__(self, s3_client: S3Client, output_bucket: str) -> None:
        self.s3_client = s3_client
        self.output_bucket = output_bucket

    async def collect_rss_feeds(self, date: str, *, force: bool = False) -> CollectionResponse:
        """Collect articles from RSS feeds for a given date.

        Args:
            date: Date string in YYYY-MM-DD format.
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = number of articles.
        """
        key = f"raw/news/date={date}/rss_articles.jsonl"
        if not force and self.s3_client.object_exists(self.output_bucket, key):
            logger.info("RSS articles already exist for date=%s, skipping", date)
            return CollectionResponse(status="success", records_collected=0, output_path=key)

        collected_at = datetime.now(UTC).isoformat()
        articles: list[dict] = []

        for source, feed_url in RSS_FEEDS.items():
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    published = getattr(entry, "published", "")
                    published_parsed = getattr(entry, "published_parsed", None)
                    if published_parsed:
                        entry_date = f"{published_parsed.tm_year}-{published_parsed.tm_mon:02d}-{published_parsed.tm_mday:02d}"
                    else:
                        entry_date = ""
                    if entry_date != date:
                        continue
                    articles.append(
                        {
                            "title": getattr(entry, "title", ""),
                            "summary": getattr(entry, "summary", ""),
                            "link": getattr(entry, "link", ""),
                            "published": published,
                            "source": source,
                            "collected_at": collected_at,
                        }
                    )
            except Exception:
                logger.exception("Failed to parse RSS feed %s", source)

        jsonl = "\n".join(json.dumps(a) for a in articles)
        self.s3_client.put_json(self.output_bucket, key, jsonl)

        logger.info("Collected %d RSS articles for date=%s", len(articles), date)
        return CollectionResponse(
            status="success", records_collected=len(articles), output_path=key
        )

    async def collect_newsapi(
        self, query: str, date: str, api_key: str, *, force: bool = False
    ) -> CollectionResponse:
        """Collect articles from NewsAPI.

        Args:
            query: Search query (e.g. "Premier League transfer").
            date: Date string in YYYY-MM-DD format.
            api_key: NewsAPI API key.
            force: If True, overwrite existing data.

        Returns:
            CollectionResponse with records_collected = number of articles.
        """
        key = f"raw/news/date={date}/newsapi_articles.jsonl"
        if not force and self.s3_client.object_exists(self.output_bucket, key):
            logger.info("NewsAPI articles already exist for date=%s, skipping", date)
            return CollectionResponse(status="success", records_collected=0, output_path=key)

        collected_at = datetime.now(UTC).isoformat()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    NEWSAPI_BASE_URL,
                    params={
                        "q": query,
                        "from": date,
                        "to": date,
                        "language": "en",
                        "sortBy": "relevancy",
                        "pageSize": 100,
                        "apiKey": api_key,
                    },
                )
                if response.status_code == 429:
                    logger.warning("NewsAPI rate limit hit for date=%s", date)
                    return CollectionResponse(
                        status="partial", records_collected=0, output_path=key
                    )
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.exception("NewsAPI request failed for date=%s", date)
                raise

        data = response.json()
        raw_articles = data.get("articles", [])

        articles = [
            {
                "title": a.get("title", ""),
                "summary": a.get("description", ""),
                "link": a.get("url", ""),
                "published": a.get("publishedAt", ""),
                "source": a.get("source", {}).get("name", "newsapi"),
                "collected_at": collected_at,
            }
            for a in raw_articles
        ]

        jsonl = "\n".join(json.dumps(a) for a in articles)
        self.s3_client.put_json(self.output_bucket, key, jsonl)

        logger.info("Collected %d NewsAPI articles for date=%s", len(articles), date)
        return CollectionResponse(
            status="success", records_collected=len(articles), output_path=key
        )
