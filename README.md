# 🌐 國際新聞中文摘要

自動整合國際主流媒體 RSS，透過 Gemini AI 翻譯成繁體中文摘要。
每小時自動更新，已過濾紅媒與口水新聞。

## 新聞來源

| 類別 | 來源 |
|---|---|
| 國際 | Reuters、BBC World、Al Jazeera、AP News |
| 科技 | TechCrunch、The Verge、Ars Technica、Wired |
| 財經 | Reuters Business、Bloomberg |
| 體育 | BBC Sport、ESPN |
| 遊戲業 | IGN、GamesIndustry.biz、Game Developer、Kotaku、Polygon |

## 快速啟動

### 1. 安裝 Python 套件

```bash
cd backend
pip install -r requirements.txt
```

### 2. 設定 API Key

```bash
# 複製範本
cp .env.example .env

# 編輯 .env，填入你的 Gemini API Key
GEMINI_API_KEY=your_key_here
```

### 3. 啟動

```bash
cd backend
python main.py
```

### 4. 開啟瀏覽器

前往 `http://localhost:8000`

---

## 技術架構

```
RSS 新聞來源 → Python 抓取（feedparser）
            → Gemini API 翻譯摘要
            → SQLite 儲存
            → FastAPI 提供 API
            → 靜態 HTML 前端顯示
```

- **後端**：Python + FastAPI + APScheduler
- **翻譯**：Google Gemini 1.5 Flash
- **資料庫**：SQLite（輕量、零設定）
- **前端**：純 HTML + Tailwind CSS

## API

| 端點 | 說明 |
|---|---|
| `GET /api/news?category=all` | 取得新聞列表 |
| `GET /api/news?category=games` | 篩選分類 |
| `POST /api/refresh` | 手動觸發更新 |
