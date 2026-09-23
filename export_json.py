"""把 SQLite 匯出成前端（GitHub Pages 靜態網站）讀的 JSON。

線上版沒有伺服器可以查資料庫，所以每次 pipeline 跑完就匯出一份完整快照；
frameworks 在資料庫裡是 JSON 字串，這裡先解開成陣列，前端不用再 parse 一次。
"""
import json
from pathlib import Path

from pipeline import get_connection

OUT_PATH = Path(__file__).parent / "data" / "announcements.json"

COLUMNS = [
    "url", "title", "source", "published_date", "summary", "business_area",
    "risk_level", "deadline", "frameworks", "action", "status",
]


def export(out_path: Path = OUT_PATH) -> int:
    conn = get_connection()
    rows = conn.execute(
        f"SELECT {', '.join(COLUMNS)} FROM announcements ORDER BY published_date DESC"
    ).fetchall()
    (last_fetched_at,) = conn.execute("SELECT MAX(fetched_at) FROM announcements").fetchone()
    conn.close()

    announcements = []
    for row in rows:
        item = dict(zip(COLUMNS, row))
        item["frameworks"] = json.loads(item["frameworks"]) if item["frameworks"] else []
        announcements.append(item)

    payload = {
        # 不用「匯出當下的時間」：那樣沒有新公告時 JSON 也會變，排程每天都會多一個空 commit
        "last_fetched_at": last_fetched_at,
        "announcements": announcements,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    return len(announcements)


if __name__ == "__main__":
    print(f"匯出 {export()} 筆 -> {OUT_PATH}")
