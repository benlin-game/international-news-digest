import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import cleanup_old_articles, get_articles, get_available_dates, init_db
from scraper import fetch_all
from translator import translate_pending

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def run_pipeline() -> None:
    logger.info("Pipeline started")
    fetch_all()
    translate_pending()
    deleted = cleanup_old_articles()
    if deleted:
        logger.info(f"Cleaned up {deleted} articles older than 7 days")
    logger.info("Pipeline done")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    run_pipeline()

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_pipeline, "cron", hour=6, minute=0)
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(title="國際新聞中文摘要", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/news")
async def get_news(
    category: Optional[str] = Query(default="all"),
    date: Optional[str] = Query(default=None),
):
    articles = get_articles(category=category, date=date)
    return JSONResponse(content={"articles": articles, "count": len(articles)})


@app.get("/api/dates")
async def get_dates():
    dates = get_available_dates()
    return JSONResponse(content={"dates": dates})


@app.post("/api/refresh")
async def manual_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline)
    return {"message": "更新已開始，約 1-2 分鐘後重新整理頁面即可看到新內容"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
