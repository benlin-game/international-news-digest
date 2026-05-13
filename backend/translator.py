import os
import json
import logging
import re
import google.generativeai as genai

from database import DAILY_LIMITS, get_today_category_counts, get_untranslated_by_category, update_translation

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """你是一位繁體中文新聞編輯，同時具備遊戲產業分析師的視角。
請將以下英文新聞標題翻譯成繁體中文，並提供摘要與遊戲業潛在影響分析。

英文標題：{title}

要求：
1. 標題翻譯自然，符合繁體中文新聞慣例
2. 新聞摘要 80 字以內，說明事件重點
3. 遊戲業潛在影響：60 字以內，從遊戲產業大環境角度分析此新聞可能帶來的風險或機會（即使是非遊戲新聞，也請從遊戲業角度切入）

請只回覆以下 JSON 格式，不要其他文字：
{{"title_zh": "翻譯後標題", "summary_zh": "新聞重點摘要", "game_impact": "對遊戲業的潛在影響"}}"""


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    return json.loads(cleaned)


def translate_pending() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        return 0

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    today_counts = get_today_category_counts()
    remaining = {
        cat: max(0, limit - today_counts.get(cat, 0))
        for cat, limit in DAILY_LIMITS.items()
    }

    total_remaining = sum(remaining.values())
    if total_remaining == 0:
        logger.info("Daily quota reached for all categories")
        return 0

    logger.info(f"Remaining quota: {remaining}")
    articles = get_untranslated_by_category(remaining)
    translated_count = 0

    for article in articles:
        try:
            prompt = PROMPT_TEMPLATE.format(title=article["title_original"])
            response = model.generate_content(prompt)
            data = _extract_json(response.text)
            update_translation(
                url=article["url"],
                title_zh=data["title_zh"],
                summary_zh=data["summary_zh"],
                game_industry_impact=data.get("game_impact", ""),
            )
            translated_count += 1
        except Exception as e:
            logger.warning(f"Translation failed for {article['url']}: {e}")

    logger.info(f"Translated {translated_count} articles")
    return translated_count
