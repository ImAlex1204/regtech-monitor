"""一次性工具：prompt 改版後，對資料庫裡既有的公告重新抓正文、重新分類、覆寫結果。
（平常 pipeline.py 靠 url 去重不會重跑舊資料；prompt 改了才需要這支腳本回頭刷新歷史資料。）

    python3 reclassify.py                     # 全部重新分類，覆寫所有 LLM 產生的欄位
    python3 reclassify.py --new-fields-only   # 只補 frameworks/action 還是空的列，既有分類不動

兩種模式都不會碰 status（使用者手動設定的處理狀態）。
--new-fields-only 只挑 frameworks 為 NULL 的列，中途中斷後重跑會從還沒補的地方接著做。
"""
import argparse
import json
from datetime import datetime, timezone

from dotenv import load_dotenv

from fetch import fetch_article_text
from llm_client import summarize_announcement
from pipeline import get_connection

load_dotenv()


def run(new_fields_only: bool):
    conn = get_connection()
    query = "SELECT url, title, risk_level, business_area FROM announcements"
    if new_fields_only:
        query += " WHERE frameworks IS NULL"
    rows = conn.execute(query).fetchall()

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

        frameworks = json.dumps(result.get("frameworks", []), ensure_ascii=False)
        if new_fields_only:
            # 同一次 LLM 呼叫也會重新產生 risk_level/business_area，但這裡刻意不寫回：
            # 既有分類已經人工抽查過，回填新欄位不該讓舊結果跟著漂移。
            conn.execute(
                "UPDATE announcements SET frameworks = ?, action = ? WHERE url = ?",
                (frameworks, result.get("action"), url),
            )
            conn.commit()
            names = [f["name"] for f in result.get("frameworks", [])]
            print(f"[補齊] {names} | {title}")
            updated += 1
            continue

        conn.execute(
            """
            UPDATE announcements
            SET summary = ?, business_area = ?, risk_level = ?, deadline = ?,
                frameworks = ?, action = ?, fetched_at = ?
            WHERE url = ?
            """,
            (
                result.get("summary"),
                result.get("business_area"),
                result.get("risk_level"),
                result.get("deadline"),
                frameworks,
                result.get("action"),
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--new-fields-only", action="store_true", help="只補 frameworks/action 為空的列，不動既有分類")
    run(parser.parse_args().new_fields_only)
