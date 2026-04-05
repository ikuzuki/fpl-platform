"""Collector for football news from RSS feeds.

Collects broadly — the LLM enrichment layer filters for FPL relevance later.
"""

import json
import logging
from datetime import UTC, datetime

import feedparser

from fpl_lib.clients.s3 import S3Client
from fpl_lib.core.responses import CollectionResponse

logger = logging.getLogger(__name__)

RSS_FEEDS: dict[str, str] = {
    "bbc_football": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky_premier_league": "https://www.skysports.com/rss/11661",
    "the_guardian_football": "https://www.theguardian.com/football/premierleague/rss",
}

# Only keep articles mentioning Premier League context
PL_KEYWORDS = {
    "premier league",
    "epl",
    "fpl",
    "arsenal",
    "aston villa",
    "bournemouth",
    "brentford",
    "brighton",
    "chelsea",
    "crystal palace",
    "everton",
    "fulham",
    "ipswich",
    "leicester",
    "liverpool",
    "manchester city",
    "manchester united",
    "man city",
    "man utd",
    "newcastle",
    "nottingham forest",
    "southampton",
    "tottenham",
    "spurs",
    "west ham",
    "wolves",
    "wolverhampton",
}


class NewsCollector:
    """Collects football news from RSS feeds."""

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
                logger.info("[RSS] Parsing %s | url=%s", source, feed_url)
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
                    # Filter for Premier League relevance
                    text = (
                        getattr(entry, "title", "") + " " + getattr(entry, "summary", "")
                    ).lower()
                    if not any(kw in text for kw in PL_KEYWORDS):
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
                logger.info(
                    "[RSS] %s | entries=%d | matched_date=%d",
                    source,
                    len(feed.entries),
                    sum(1 for a in articles if a["source"] == source),
                )
            except Exception:
                logger.exception("[RSS] Failed to parse feed %s", source)

        jsonl = "\n".join(json.dumps(a) for a in articles)
        self.s3_client.put_json(self.output_bucket, key, jsonl)

        logger.info("Collected %d RSS articles for date=%s", len(articles), date)
        return CollectionResponse(
            status="success", records_collected=len(articles), output_path=key
        )
