"""Week 2: 批次抓取 -> 摘要 -> 去重 -> 存入 SQLite，單筆失敗不中斷整批。"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from fetch import SOURCES, fetch_feed_entries, fetch_article_text
from llm_client import summarize_announcement

load_dotenv()

DB_PATH = Path(__file__).parent / "data" / "announcements.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS announcements (
    url TEXT PRIMARY KEY,
    title TEXT,
    published_date TEXT,
    summary TEXT,
    business_area TEXT,
    risk_level TEXT,
    deadline TEXT,
    fetched_at TEXT,
    source TEXT,
    frameworks TEXT,
    action TEXT,
    status TEXT NOT NULL DEFAULT 'todo'
);
"""

# 資料表建好之後才加的欄位：舊資料庫缺哪個就補哪個。
# status 是使用者在 dashboard 手動設定的處理狀態（todo / in_progress / done / na）：
# pipeline 只用 INSERT OR IGNORE 新增列，reclassify.py 也只 UPDATE 分類欄位，兩者都不會碰 status。
ADDED_COLUMNS = {
    "source": "TEXT DEFAULT 'FCA'",  # 加第二個來源（SEC）前的資料都是 FCA
    "frameworks": "TEXT",  # JSON 陣列：[{"name": ..., "reason": ...}]，name 來自 llm_client.FRAMEWORKS
    "action": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'todo'",
}
STATUSES = ("todo", "in_progress", "done", "na")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(announcements)")}
    for column, definition in ADDED_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE announcements ADD COLUMN {column} {definition}")
    conn.commit()
    return conn


def already_fetched(conn: sqlite3.Connection, url: str) -> bool:
    row = conn.execute("SELECT 1 FROM announcements WHERE url = ?", (url,)).fetchone()
    return row is not None


def process_entry(conn: sqlite3.Connection, entry: dict) -> bool:
    """處理單一筆公告。成功寫入回傳 True，任何一步失敗回傳 False（不拋例外）。"""
    url = entry["link"]
    title = entry["title"]

    text = fetch_article_text(url)
    if not text:
        print(f"[跳過] 抓不到正文：{title} ({url})")
        return False

    result = summarize_announcement(title, text)
    if result is None:
        print(f"[跳過] LLM 摘要解析失敗：{title} ({url})")
        return False

    conn.execute(
        """
        INSERT OR IGNORE INTO announcements
            (url, title, published_date, summary, business_area, risk_level, deadline, fetched_at, source,
             frameworks, action)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            url,
            title,
            entry.get("published"),
            result.get("summary"),
            result.get("business_area"),
            result.get("risk_level"),
            result.get("deadline"),
            datetime.now(timezone.utc).isoformat(),
            entry.get("source"),
            json.dumps(result.get("frameworks", []), ensure_ascii=False),
            result.get("action"),
        ),
    )
    conn.commit()
    return True


def run():
    conn = get_connection()

    new_count = 0
    skip_existing = 0
    skip_error = 0

    for source in SOURCES:
        entries = fetch_feed_entries(source)
        print(f"--- {source['name']} ({source['code']})：{len(entries)} 筆 ---")

        for entry in entries:
            url = entry["link"]
            if already_fetched(conn, url):
                skip_existing += 1
                continue

            try:
                ok = process_entry(conn, entry)
            except Exception as exc:
                print(f"[錯誤] 處理失敗：{entry.get('title')} ({url}) -> {exc}")
                ok = False

            if ok:
                new_count += 1
            else:
                skip_error += 1

    conn.close()
    print(
        f"\n完成。新增 {new_count} 筆，已存在跳過 {skip_existing} 筆，"
        f"處理失敗跳過 {skip_error} 筆。"
    )


if __name__ == "__main__":
    run()
