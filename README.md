# 🌐 國際新聞中文摘要

自動整合國際主流媒體 RSS，透過 Gemini AI 翻譯成繁體中文摘要，並附上「遊戲業潛在影響」分析與重要性分級。已過濾紅媒與口水新聞。

線上版：<https://benlin-game.github.io/international-news-digest/>

## 新聞來源

| 類別 | 來源 |
|---|---|
| 國際 | Reuters、BBC World、Al Jazeera、AP News |
| 科技 | TechCrunch、The Verge、Ars Technica、Wired |
| 財經 | Reuters Business、Bloomberg |
| 遊戲業 | IGN、GamesIndustry.biz、Game Developer、Kotaku、Polygon |

## 技術架構

```
RSS 新聞來源 → generate.py 抓取（feedparser）
            → Gemini API 翻譯摘要 + 重要性分級
            → docs/data.json（資料）
            → docs/index.html + app.jsx + app.css（React + Babel standalone 前端）
            → GitHub Pages 托管
```

- **生成**：Python + feedparser + Google Gemini
- **前端**：React 18（in-browser Babel）+ 純 CSS，前端 `fetch('./data.json')` 載入資料
- **托管**：GitHub Pages（靜態）
- **排程**：[cron-job.org](https://cron-job.org) 每天 06:15（台灣時間）打 GitHub API 觸發 `workflow_dispatch`，繞過 GitHub Actions 內建 cron 的不穩定延遲

## 自動更新流程

1. cron-job.org 每天 06:15 觸發 GitHub Actions workflow（`.github/workflows/update.yml`）
2. workflow 執行 `generate.py`：抓 RSS → Gemini 翻譯 → 更新 `docs/data.json`
3. commit & push，GitHub Pages 自動部署

> `index.html` 的 `app.css` / `app.jsx` 引用帶有內容雜湊 `?v=<hash>`，改版時自動失效瀏覽器快取，無需手動強制重整。

## 本機執行

```bash
pip install -r requirements.txt

# 設定 API key（擇一）
export GEMINI_API_KEY=your_key_here   # 或在專案根目錄建立 .env 寫入 GEMINI_API_KEY=...

python generate.py
```

產出會更新 `docs/`，可用任意靜態伺服器預覽：

```bash
cd docs && python -m http.server 8000
# 開啟 http://localhost:8000
```
