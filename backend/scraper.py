import feedparser
from datetime import datetime
from typing import Optional
import logging

from database import insert_article

logger = logging.getLogger(__name__)

RSS_FEEDS: dict[str, list[dict]] = {
    "international": [
        {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/topNews"},
        {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "AP News", "url": "https://rsshub.app/apnews/topics/apf-topnews"},
    ],
    "tech": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "Ars Technica", "url": "http://feeds.arstechnica.com/arstechnica/index"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
    ],
    "finance": [
        {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews"},
        {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss"},
    ],
    "games": [
        {"name": "IGN", "url": "https://feeds.ign.com/ign/all"},
        {"name": "GamesIndustry.biz", "url": "https://www.gamesindustry.biz/feed"},
        {"name": "Game Developer", "url": "https://www.gamedeveloper.com/rss.xml"},
        {"name": "Kotaku", "url": "https://kotaku.com/rss"},
        {"name": "Polygon", "url": "https://www.polygon.com/rss/index.xml"},
    ],
}

BLOCKED_SOURCES = {
    "people's daily", "xinhua", "global times", "ta kung pao", "wen wei po",
    "china daily", "cgtn", "cctv",
}


def _is_blocked(source_name: str) -> bool:
    return any(blocked in source_name.lower() for blocked in BLOCKED_SOURCES)


def _parse_date(entry: feedparser.FeedParserDict) -> str:
    if hasattr(entry, "published"):
        return entry.published
    return datetime.utcnow().isoformat()


def fetch_all() -> int:
    total_new = 0
    fetched_at = datetime.now().isoformat()

    for category, feeds in RSS_FEEDS.items():
        for feed_info in feeds:
            if _is_blocked(feed_info["name"]):
                continue
            try:
                feed = feedparser.parse(feed_info["url"])
                for entry in feed.entries[:20]:
                    url = getattr(entry, "link", None)
                    title = getattr(entry, "title", None)
                    if not url or not title:
                        continue
                    inserted = insert_article(
                        source=feed_info["name"],
                        category=category,
                        title_original=title,
                        url=url,
                        published_at=_parse_date(entry),
                        fetched_at=fetched_at,
                    )
                    if inserted:
                        total_new += 1
            except Exception as e:
                logger.warning(f"Failed to fetch {feed_info['name']}: {e}")

    logger.info(f"Fetched {total_new} new articles")
    return total_new
