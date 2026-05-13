#!/usr/bin/env python3
"""
Fetch RSS feeds -> translate with Gemini -> update docs/data.json -> generate docs/index.html
Designed to run as a GitHub Actions job or locally.
"""
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
請將以下英文新聞標題翻譯成繁體中文，並提供摘要與遊戲業潛在影響分析。

英文標題：{title}

要求：
1. 標題翻譯自然，符合繁體中文新聞慣例
2. 新聞摘要 80 字以內，說明事件重點
3. 遊戲業潛在影響：60 字以內，從遊戲產業大環境角度分析此新聞可能帶來的風險或機會

請只回覆以下 JSON 格式，不要其他文字：
{{"title_zh": "翻譯後標題", "summary_zh": "新聞重點摘要", "game_impact": "對遊戲業的潛在影響"}}"""

DATA_PATH = Path("docs/data.json")
HTML_PATH = Path("docs/index.html")

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>國際新聞中文摘要</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;700&family=Noto+Sans+TC:wght@400;500&display=swap" rel="stylesheet">
  <style>
    body { font-family: "Noto Sans TC", sans-serif; }
    h1, h2, .serif { font-family: "Noto Serif TC", serif; }
    .card-hover { transition: transform 0.15s, box-shadow 0.15s; }
    .card-hover:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
    .tab-active { background: #1d4ed8; color: #fff; }
    .tab-inactive { background: #f3f4f6; color: #374151; }
    .tab-inactive:hover { background: #e5e7eb; }
  </style>
</head>
<body class="bg-gray-50 min-h-screen">
  <header class="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
    <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 serif">🌐 國際新聞摘要</h1>
        <p class="text-sm text-gray-400 mt-0.5">每日 06:00 更新 · 含遊戲業潛在影響分析</p>
      </div>
      <span class="text-xs text-gray-400">最後更新：__UPDATED_AT__</span>
    </div>
    <div class="max-w-6xl mx-auto px-4 pb-3 flex gap-2 overflow-x-auto">
      <button onclick="setCategory('all')" data-cat="all" class="cat-btn tab-active px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap">全部</button>
      <button onclick="setCategory('international')" data-cat="international" class="cat-btn tab-inactive px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap">🌍 國際</button>
      <button onclick="setCategory('tech')" data-cat="tech" class="cat-btn tab-inactive px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap">💻 科技</button>
      <button onclick="setCategory('finance')" data-cat="finance" class="cat-btn tab-inactive px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap">📈 財經</button>
      <button onclick="setCategory('games')" data-cat="games" class="cat-btn tab-inactive px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap">🎮 遊戲業</button>
    </div>
    <div class="max-w-6xl mx-auto px-4 pb-3 flex gap-2 overflow-x-auto" id="date-tabs"></div>
  </header>

  <main class="max-w-6xl mx-auto px-4 py-6">
    <div id="news-grid" class="grid gap-4 md:grid-cols-2 lg:grid-cols-3"></div>
    <div id="empty" class="hidden text-center py-20 text-gray-400">
      <p class="text-4xl mb-3">📰</p><p>此日期 / 分類沒有新聞</p>
    </div>
  </main>

  <footer class="text-center text-gray-400 text-xs py-6">
    來源：Reuters · BBC · Al Jazeera · TechCrunch · The Verge · Ars Technica · IGN · GamesIndustry.biz 等<br>
    已過濾紅媒 · 每日精選 40 則 · 保留近 7 天
  </footer>

  <script>
    const ALL_NEWS = __DATA_JSON__;
    const LABELS = { international: "🌍 國際", tech: "💻 科技", finance: "📈 財經", games: "🎮 遊戲業" };
    let currentCategory = "all";
    let currentDate = null;

    function availableDates() {
      return [...new Set(ALL_NEWS.map(a => a.date))].sort().reverse().slice(0, 7);
    }

    function dateLabel(d) {
      const today = new Date().toLocaleDateString("sv-SE");
      const yesterday = new Date(Date.now() - 86400000).toLocaleDateString("sv-SE");
      if (d === today) return "今天";
      if (d === yesterday) return "昨天";
      const [, m, day] = d.split("-");
      return `${parseInt(m)}/${parseInt(day)}`;
    }

    function renderDateTabs() {
      const dates = availableDates();
      if (!currentDate || !dates.includes(currentDate)) currentDate = dates[0] || null;
      document.getElementById("date-tabs").innerHTML = dates.map(d =>
        `<button onclick="setDate('${d}')" data-date="${d}"
          class="date-btn ${d === currentDate ? "tab-active" : "tab-inactive"} px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap">
          ${dateLabel(d)}</button>`
      ).join("");
    }

    function setCategory(cat) {
      currentCategory = cat;
      document.querySelectorAll(".cat-btn").forEach(b => {
        b.className = "cat-btn " + (b.dataset.cat === cat ? "tab-active" : "tab-inactive") + " px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap";
      });
      render();
    }

    function setDate(date) {
      currentDate = date;
      document.querySelectorAll(".date-btn").forEach(b => {
        b.className = "date-btn " + (b.dataset.date === date ? "tab-active" : "tab-inactive") + " px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap";
      });
      render();
    }

    function render() {
      const filtered = ALL_NEWS.filter(a =>
        (!currentDate || a.date === currentDate) &&
        (currentCategory === "all" || a.category === currentCategory)
      );
      const grid = document.getElementById("news-grid");
      const empty = document.getElementById("empty");
      if (!filtered.length) { grid.innerHTML = ""; empty.classList.remove("hidden"); return; }
      empty.classList.add("hidden");
      grid.innerHTML = filtered.map(a => `
        <a href="${a.url}" target="_blank" rel="noopener"
          class="card-hover bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-3 cursor-pointer">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">${LABELS[a.category] || a.category}</span>
            <span class="text-xs text-gray-400">${a.source}</span>
          </div>
          <h2 class="font-bold text-gray-900 leading-snug text-base serif">${a.title_zh || a.title_original}</h2>
          <p class="text-sm text-gray-600 leading-relaxed">${a.summary_zh || ""}</p>
          ${a.game_impact ? `<div class="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            <p class="text-xs font-semibold text-amber-700 mb-0.5">🎮 遊戲業潛在影響</p>
            <p class="text-xs text-amber-800 leading-relaxed">${a.game_impact}</p>
          </div>` : ""}
          <div class="flex items-center justify-between mt-auto pt-2 border-t border-gray-100">
            <span class="text-xs text-gray-400">${a.date}</span>
            <span class="text-xs text-blue-500">閱讀原文 →</span>
          </div>
        </a>`).join("");
    }

    renderDateTabs();
    render();
  </script>
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
            })
            logger.info(f"OK: {data['title_zh'][:40]}")
        except Exception as e:
            logger.warning(f"Failed: {article['url']} — {e}")
    return result


def generate_html(articles: list[dict]) -> None:
    HTML_PATH.parent.mkdir(exist_ok=True)
    updated_at = datetime.now(TZ_TAIWAN).strftime("%Y/%m/%d %H:%M")
    data_json = json.dumps(articles, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json).replace("__UPDATED_AT__", updated_at)
    HTML_PATH.write_text(html, encoding="utf-8")
    logger.info(f"Generated {HTML_PATH} ({len(articles)} articles)")


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
    generate_html(all_articles)
    logger.info(f"Done. Total: {len(all_articles)}")


if __name__ == "__main__":
    main()
