#!/usr/bin/env python3
"""
Fetch RSS feeds -> translate with Gemini -> update docs/data.json -> generate docs/index.html
Designed to run as a GitHub Actions job or locally.
"""
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TZ_TAIWAN = timezone(timedelta(hours=8))

DAILY_LIMITS: dict[str, int] = {
    "international": 10,
    "tech": 10,
    "finance": 6,
    "games": 14,
}

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

PROMPT_TEMPLATE = """你是一位繁體中文新聞編輯，同時具備遊戲產業分析師的視角。
請將以下英文新聞標題翻譯成繁體中文，並提供摘要、遊戲業潛在影響分析與重要性分級。

英文標題：{title}

要求：
1. 標題翻譯自然，符合繁體中文新聞慣例
2. 新聞摘要 80 字以內，說明事件重點
3. 遊戲業潛在影響：60 字以內，從遊戲產業大環境角度分析此新聞可能帶來的風險或機會
4. 重要性分級（擇一）：
   - "critical"：重大事件，直接衝擊遊戲產業或市場格局，必看
   - "normal"：值得關注，對產業有間接影響的一般新聞
   - "background"：背景資訊，趨勢性、補充性，重要性較低

請只回覆以下 JSON 格式，不要其他文字：
{{"title_zh": "翻譯後標題", "summary_zh": "新聞重點摘要", "game_impact": "對遊戲業的潛在影響", "importance": "critical|normal|background"}}"""

DATA_PATH = Path("docs/data.json")
HTML_PATH = Path("docs/index.html")
CSS_PATH = Path("docs/app.css")
JS_PATH = Path("docs/app.jsx")

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>國際／日報 · 每日國際新聞策展</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Spectral:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&family=Noto+Serif+TC:wght@400;700&family=Noto+Sans+TC:wght@400;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="app.css?v=__CSS_VER__" />
</head>
<body>
  <div id="root"></div>

  <script src="https://unpkg.com/react@18.3.1/umd/react.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js"></script>
  <script type="text/babel" src="app.jsx?v=__JS_VER__"></script>
</body>
</html>"""


def _today() -> str:
    return datetime.now(TZ_TAIWAN).strftime("%Y-%m-%d")


def _cutoff() -> str:
    return (datetime.now(TZ_TAIWAN) - timedelta(days=7)).strftime("%Y-%m-%d")


def load_data() -> list[dict]:
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return []


def save_data(articles: list[dict]) -> None:
    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_candidates(existing_urls: set[str]) -> dict[str, list[dict]]:
    candidates: dict[str, list[dict]] = {cat: [] for cat in DAILY_LIMITS}
    for category, feeds in RSS_FEEDS.items():
        for feed_info in feeds:
            if any(b in feed_info["name"].lower() for b in BLOCKED_SOURCES):
                continue
            try:
                feed = feedparser.parse(feed_info["url"])
                for entry in feed.entries[:20]:
                    url = getattr(entry, "link", None)
                    title = getattr(entry, "title", None)
                    if not url or not title or url in existing_urls:
                        continue
                    candidates[category].append({
                        "source": feed_info["name"],
                        "category": category,
                        "title_original": title,
                        "url": url,
                        "date": _today(),
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch {feed_info['name']}: {e}")
    return candidates


def select_to_translate(candidates: dict[str, list[dict]], existing: list[dict]) -> list[dict]:
    today = _today()
    today_counts: dict[str, int] = {}
    for a in existing:
        if a.get("date") == today:
            cat = a.get("category", "")
            today_counts[cat] = today_counts.get(cat, 0) + 1

    selected = []
    for cat, limit in DAILY_LIMITS.items():
        remaining = max(0, limit - today_counts.get(cat, 0))
        if remaining > 0:
            selected.extend(candidates.get(cat, [])[:remaining])
    return selected


def translate_articles(articles: list[dict], api_key: str) -> list[dict]:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    result = []
    for article in articles:
        try:
            response = model.generate_content(
                PROMPT_TEMPLATE.format(title=article["title_original"])
            )
            cleaned = re.sub(r"```(?:json)?", "", response.text).strip().rstrip("`").strip()
            data = json.loads(cleaned)
            result.append({
                **article,
                "title_zh": data["title_zh"],
                "summary_zh": data["summary_zh"],
                "game_impact": data.get("game_impact", ""),
                "importance": data.get("importance", "normal"),
            })
            logger.info(f"OK: {data['title_zh'][:40]}")
        except Exception as e:
            logger.warning(f"Failed: {article['url']} — {e}")
    return result


def _asset_hash(path: Path) -> str:
    """Short content hash for cache-busting; stable unless the file changes."""
    if not path.exists():
        return "0"
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


def generate_html() -> None:
    """Write static index.html shell with content-hash cache busting.

    Rewrites only when the rendered HTML changes (i.e. app.css / app.jsx
    changed), so daily news runs don't churn index.html, but a design or
    logic update forces browsers to fetch the new asset immediately.
    """
    HTML_PATH.parent.mkdir(exist_ok=True)
    html = (
        HTML_TEMPLATE
        .replace("__CSS_VER__", _asset_hash(CSS_PATH))
        .replace("__JS_VER__", _asset_hash(JS_PATH))
    )
    if HTML_PATH.exists() and HTML_PATH.read_text(encoding="utf-8") == html:
        return
    HTML_PATH.write_text(html, encoding="utf-8")
    logger.info(f"Generated {HTML_PATH} (css={_asset_hash(CSS_PATH)} js={_asset_hash(JS_PATH)})")


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Try loading from .env for local dev
        env_file = Path(__file__).parent / "backend" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        raise SystemExit(1)

    existing = [a for a in load_data() if a.get("date", "") >= _cutoff()]
    existing_urls = {a["url"] for a in existing}
    logger.info(f"Existing articles: {len(existing)}")

    candidates = fetch_candidates(existing_urls)
    total = sum(len(v) for v in candidates.values())
    logger.info(f"New candidates: {total}")

    to_translate = select_to_translate(candidates, existing)
    logger.info(f"To translate: {len(to_translate)}")

    translated = translate_articles(to_translate, api_key)
    all_articles = existing + translated

    save_data(all_articles)
    generate_html()
    logger.info(f"Done. Total: {len(all_articles)}")


if __name__ == "__main__":
    main()
