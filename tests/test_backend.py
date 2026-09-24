"""後端的幾個關鍵保證（不打網路、不呼叫 LLM）：

    python3 -m unittest discover tests

- 使用者手動設定的 status 不會被 pipeline 或 reclassify 覆蓋
- 舊資料庫會自動補上新欄位
- LLM 回傳的框架名稱會被收斂回固定清單、deadline 只留真實日期
- 排除清單內的網址（FCA 媒體索引頁）不會進入 pipeline
- 同一則 FCA 公告換個分類路徑不會被重複收錄；SEC 同標題的定期報告不會被誤判為重複
"""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import export_json  # noqa: E402
import fetch  # noqa: E402
import llm_client  # noqa: E402
import pipeline  # noqa: E402
import reclassify  # noqa: E402

LLM_RESULT = {
    "summary": "New summary",
    "business_area": "洗錢防制與金融犯罪",
    "risk_level": "高",
    "deadline": None,
    "frameworks": [{"name": "AML (MLRs / BSA)", "reason": "Names the MLRs."}],
    "action": "Review AML controls.",
}
ENTRY = {"link": "https://example.com/a", "title": "A", "published": "2026-09-01T00:00:00+00:00", "source": "FCA"}


class TempDbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        patcher = mock.patch.object(pipeline, "DB_PATH", self.db)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def query(self, sql, *args):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()


class NormalizeFrameworksTest(unittest.TestCase):
    def test_strips_descriptions_drops_unknown_and_duplicates(self):
        raw = [
            {"name": "SM&CR: UK Senior Managers & Certification Regime", "reason": "x"},
            {"name": "SOX"},
            "MAR",
            {"name": "MAR", "reason": "dup"},
            None,
        ]
        self.assertEqual(
            llm_client.normalize_frameworks(raw),
            [{"name": "SM&CR", "reason": "x"}, {"name": "MAR", "reason": None}],
        )

    def test_non_list_becomes_empty(self):
        self.assertEqual(llm_client.normalize_frameworks("MAR"), [])
        self.assertEqual(llm_client.normalize_frameworks(None), [])


class NormalizeDeadlineTest(unittest.TestCase):
    def test_keeps_only_real_calendar_dates(self):
        self.assertEqual(llm_client.normalize_deadline("2027-10-11"), "2027-10-11")
        self.assertEqual(llm_client.normalize_deadline(" 2027-10-11 "), "2027-10-11")
        self.assertIsNone(llm_client.normalize_deadline("60 days following publication in the Federal Register"))
        self.assertIsNone(llm_client.normalize_deadline("2026-02-30"))
        self.assertIsNone(llm_client.normalize_deadline("20261011"))
        self.assertIsNone(llm_client.normalize_deadline(None))


class MigrationTest(TempDbTestCase):
    def test_old_schema_gets_new_columns_with_default_status(self):
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE announcements (url TEXT PRIMARY KEY, title TEXT, published_date TEXT, summary TEXT,"
                     " business_area TEXT, risk_level TEXT, deadline TEXT, fetched_at TEXT)")
        conn.execute("INSERT INTO announcements (url, title) VALUES ('u', 't')")
        conn.commit()
        conn.close()

        pipeline.get_connection().close()
        pipeline.get_connection().close()  # 第二次要是 no-op，不能因為欄位已存在而出錯

        cols = {row[1] for row in self.query("PRAGMA table_info(announcements)")}
        self.assertTrue({"source", "frameworks", "action", "status"} <= cols)
        self.assertEqual(self.query("SELECT source, status FROM announcements"), [("FCA", "todo")])


class StatusPreservationTest(TempDbTestCase):
    def test_pipeline_insert_never_overwrites_status(self):
        with mock.patch.object(pipeline, "fetch_article_text", return_value="text"), \
             mock.patch.object(pipeline, "summarize_announcement", return_value=dict(LLM_RESULT)):
            conn = pipeline.get_connection()
            self.assertTrue(pipeline.process_entry(conn, ENTRY))
            conn.execute("UPDATE announcements SET status = 'done' WHERE url = ?", (ENTRY["link"],))
            conn.commit()
            pipeline.process_entry(conn, ENTRY)  # 同一筆再跑一次（例如排程重跑）
            conn.close()

        row = self.query("SELECT status, frameworks, action FROM announcements")
        self.assertEqual(row[0][0], "done")
        self.assertEqual(json.loads(row[0][1])[0]["name"], "AML (MLRs / BSA)")
        self.assertEqual(row[0][2], "Review AML controls.")

    def test_reclassify_new_fields_only_keeps_status_and_existing_classification(self):
        conn = pipeline.get_connection()
        conn.execute("INSERT INTO announcements (url, title, summary, business_area, risk_level, status)"
                     " VALUES ('u', 't', 'Old summary', '監管政策與合規流程', '中', 'in_progress')")
        conn.commit()
        conn.close()

        with mock.patch.object(reclassify, "fetch_article_text", return_value="text"), \
             mock.patch.object(reclassify, "summarize_announcement", return_value=dict(LLM_RESULT)):
            reclassify.run(new_fields_only=True)

        self.assertEqual(
            self.query("SELECT summary, business_area, risk_level, status, action FROM announcements"),
            [("Old summary", "監管政策與合規流程", "中", "in_progress", "Review AML controls.")],
        )

    def test_full_reclassify_keeps_status(self):
        conn = pipeline.get_connection()
        conn.execute("INSERT INTO announcements (url, title, risk_level, status) VALUES ('u', 't', '中', 'na')")
        conn.commit()
        conn.close()

        with mock.patch.object(reclassify, "fetch_article_text", return_value="text"), \
             mock.patch.object(reclassify, "summarize_announcement", return_value=dict(LLM_RESULT)):
            reclassify.run(new_fields_only=False)

        self.assertEqual(self.query("SELECT risk_level, status FROM announcements"), [("高", "na")])


class DuplicateUrlTest(TempDbTestCase):
    FCA_A = "https://www.fca.org.uk/news/news-stories/fca-opens-investigation-euro-exchange-securities-uk-ltd"
    FCA_B = "https://www.fca.org.uk/news/enforcement-investigations/fca-opens-investigation-euro-exchange-securities-uk-ltd"

    def insert(self, url, source, title="t"):
        conn = pipeline.get_connection()
        conn.execute("INSERT INTO announcements (url, title, source) VALUES (?, ?, ?)", (url, title, source))
        conn.commit()
        conn.close()

    def test_same_story_under_another_fca_section_is_a_duplicate(self):
        self.insert(self.FCA_A, "FCA")
        conn = pipeline.get_connection()
        self.assertEqual(pipeline.find_existing(conn, self.FCA_A, "FCA"), self.FCA_A)
        self.assertEqual(pipeline.find_existing(conn, self.FCA_B, "FCA"), self.FCA_A)
        self.assertEqual(pipeline.find_existing(conn, self.FCA_B + "/", "FCA"), self.FCA_A)
        conn.close()

    def test_recurring_sec_release_with_identical_title_is_not_a_duplicate(self):
        title = "SEC Publishes Updated Market Statistics, Highlighting Increase in IPOs and Proceeds Raised"
        self.insert("https://www.sec.gov/newsroom/press-releases/2026-61-sec-publishes-updated-market-statistics", "SEC", title)
        conn = pipeline.get_connection()
        self.assertIsNone(pipeline.find_existing(
            conn, "https://www.sec.gov/newsroom/press-releases/2026-93-sec-publishes-updated-market-statistics", "SEC"))
        conn.close()

    def test_slug_match_is_scoped_to_the_same_regulator(self):
        self.insert("https://www.fca.org.uk/news/press-releases/joint-statement", "FCA")
        conn = pipeline.get_connection()
        self.assertIsNone(pipeline.find_existing(conn, "https://www.sec.gov/newsroom/joint-statement", "SEC"))
        conn.close()

    def test_run_skips_duplicate_without_calling_the_llm(self):
        self.insert(self.FCA_A, "FCA")
        entry = {"link": self.FCA_B, "title": "t", "published": None, "source": "FCA"}
        fca = {"code": "FCA", "name": "FCA", "rss_url": "x"}
        with mock.patch.object(pipeline, "SOURCES", [fca]), \
             mock.patch.object(pipeline, "fetch_feed_entries", return_value=[entry]), \
             mock.patch.object(pipeline, "summarize_announcement") as llm:
            pipeline.run()
        llm.assert_not_called()
        self.assertEqual(self.query("SELECT url FROM announcements"), [(self.FCA_A,)])


class FeedExclusionTest(unittest.TestCase):
    def test_excluded_urls_never_reach_the_pipeline(self):
        feed = mock.Mock(entries=[
            {"title": "Video", "link": "https://www.fca.org.uk/news/news-stories/video", "published": None},
            {"title": "Real", "link": "https://www.fca.org.uk/news/press-releases/real", "published": None},
        ])
        fca = next(s for s in fetch.SOURCES if s["code"] == "FCA")
        with mock.patch.object(fetch.feedparser, "parse", return_value=feed):
            self.assertEqual([e["title"] for e in fetch.fetch_feed_entries(fca)], ["Real"])


class ExportTest(TempDbTestCase):
    def test_payload_parses_frameworks_and_is_stable(self):
        with mock.patch.object(pipeline, "fetch_article_text", return_value="text"), \
             mock.patch.object(pipeline, "summarize_announcement", return_value=dict(LLM_RESULT)):
            conn = pipeline.get_connection()
            pipeline.process_entry(conn, ENTRY)
            conn.close()

        out = Path(self.tmp.name) / "a.json"
        export_json.export(out)
        first = out.read_text()
        export_json.export(out)
        self.assertEqual(first, out.read_text())  # 沒有新資料時輸出不變，排程才不會產生空 commit

        item = json.loads(first)["announcements"][0]
        self.assertEqual(item["frameworks"], LLM_RESULT["frameworks"])
        self.assertEqual(item["status"], "todo")


if __name__ == "__main__":
    unittest.main()
