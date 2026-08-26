"""一次性工具：prompt 改版後，對資料庫裡既有的公告重新抓正文、重新分類、覆寫結果。
（平常 pipeline.py 靠 url 去重不會重跑舊資料；prompt 改了才需要這支腳本回頭刷新歷史資料。）"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from fetch import fetch_article_text
from llm_client import summarize_announcement

load_dotenv()

DB_PATH = Path(__file__).parent / "data" / "announcements.db"


def run():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT url, title, risk_level, business_area FROM announcements").fetchall()

    updated = 0
    failed = 0
    for url, title, old_risk, old_area in rows:
        text = fetch_article_text(url)
        if not text:
            print(f"[跳過] 抓不到正文：{title}")
            failed += 1
            continue

        result = summarize_announcement(title, text)
        if result is None:
            print(f"[跳過] LLM 解析失敗：{title}")
            failed += 1
            continue

        conn.execute(
            """
            UPDATE announcements
            SET summary = ?, business_area = ?, risk_level = ?, deadline = ?, fetched_at = ?
            WHERE url = ?
            """,
            (
                result.get("summary"),
                result.get("business_area"),
                result.get("risk_level"),
                result.get("deadline"),
                datetime.now(timezone.utc).isoformat(),
                url,
            ),
        )
        conn.commit()

        changed = (old_risk != result.get("risk_level")) or (old_area != result.get("business_area"))
        marker = "變動" if changed else "相同"
        print(f"[{marker}] {old_risk}->{result.get('risk_level')} | {old_area} -> {result.get('business_area')} | {title}")
        updated += 1

    conn.close()
    print(f"\n完成。更新 {updated} 筆，失敗跳過 {failed} 筆。")


if __name__ == "__main__":
    run()
