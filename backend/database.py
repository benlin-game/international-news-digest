import sqlite3
from typing import Optional


DB_PATH = "news.db"

DAILY_LIMITS: dict[str, int] = {
    "international": 10,
    "tech": 10,
    "finance": 6,
    "games": 14,
}


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            title_original TEXT NOT NULL,
            title_zh TEXT,
            summary_zh TEXT,
            game_industry_impact TEXT,
            url TEXT UNIQUE NOT NULL,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            translated INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    _migrate(conn)
    conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
    if "game_industry_impact" not in existing:
        conn.execute("ALTER TABLE articles ADD COLUMN game_industry_impact TEXT")
        conn.commit()


def insert_article(
    source: str,
    category: str,
    title_original: str,
    url: str,
    published_at: str,
    fetched_at: str,
) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT INTO articles (source, category, title_original, url, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, category, title_original, url, published_at, fetched_at),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_translation(url: str, title_zh: str, summary_zh: str, game_industry_impact: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE articles SET title_zh=?, summary_zh=?, game_industry_impact=?, translated=1 WHERE url=?",
        (title_zh, summary_zh, game_industry_impact, url),
    )
    conn.commit()
    conn.close()


def get_today_category_counts() -> dict[str, int]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT category, COUNT(*) as cnt FROM articles
        WHERE translated=1 AND DATE(fetched_at) = DATE('now', 'localtime')
        GROUP BY category
    """).fetchall()
    conn.close()
    return {row["category"]: row["cnt"] for row in rows}


def get_untranslated_by_category(limits: dict[str, int]) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    result = []
    for category, limit in limits.items():
        if limit <= 0:
            continue
        rows = conn.execute("""
            SELECT * FROM articles
            WHERE translated=0 AND category=?
            ORDER BY fetched_at DESC LIMIT ?
        """, (category, limit)).fetchall()
        result.extend([dict(r) for r in rows])
    conn.close()
    return result


def get_articles(
    category: Optional[str] = None,
    date: Optional[str] = None,
) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    date_expr = f"'{date}'" if date else "DATE('now', 'localtime')"

    if category and category != "all":
        cat_limit = DAILY_LIMITS.get(category, 20)
        rows = conn.execute(
            f"SELECT * FROM articles WHERE translated=1 AND category=? AND DATE(fetched_at)={date_expr} ORDER BY fetched_at DESC LIMIT ?",
            (category, cat_limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    result = []
    for cat, limit in DAILY_LIMITS.items():
        rows = conn.execute(
            f"SELECT * FROM articles WHERE translated=1 AND category=? AND DATE(fetched_at)={date_expr} ORDER BY fetched_at DESC LIMIT ?",
            (cat, limit),
        ).fetchall()
        result.extend([dict(r) for r in rows])
    conn.close()
    result.sort(key=lambda x: x["fetched_at"], reverse=True)
    return result


def get_available_dates() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT DISTINCT DATE(fetched_at) as d FROM articles
        WHERE translated=1 AND DATE(fetched_at) >= DATE('now', 'localtime', '-6 days')
        ORDER BY d DESC
    """).fetchall()
    conn.close()
    return [row[0] for row in rows]


def cleanup_old_articles() -> int:
    conn = sqlite3.connect(DB_PATH)
    result = conn.execute(
        "DELETE FROM articles WHERE DATE(fetched_at) < DATE('now', 'localtime', '-7 days')"
    )
    deleted = result.rowcount
    conn.commit()
    conn.close()
    return deleted
