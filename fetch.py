"""抓多個監管機構的 RSS feed，並解析單篇公告正文。"""
from calendar import timegm
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

# 每個來源只需要代碼、顯示名稱、RSS 網址三樣東西。fetch_article_text 是通用邏輯
# （<main> 標籤 fallback 全部 <p>），FCA 跟 SEC 網站結構完全不同但都適用，不需要每個來源客製。
SOURCES = [
    {
        "code": "FCA", "name": "Financial Conduct Authority (UK)",
        "rss_url": "https://www.fca.org.uk/news/rss.xml",
        # FCA 用自訂日期格式（非 RFC822/ISO），feedparser 認不出來、published_parsed 會是 None，
        # 需要手動解析當備援。時區精確度不重要（只拿來做週彙總），簡化當成 UTC 處理。
        "date_format": "%A, %B %d, %Y - %H:%M",
    },
    {"code": "SEC", "name": "Securities and Exchange Commission (US)", "rss_url": "https://www.sec.gov/news/pressreleases.rss"},
]

USER_AGENT = "RegTech-Monitor-Student-Project/0.1 (contact: imalex1204@gmail.com)"


def fetch_feed_entries(source: dict) -> list[dict]:
    """抓某一個來源的 RSS feed，回傳簡化過的條目 list。

    published 統一轉成 ISO 8601 字串（UTC）——不同機構的 RSS 日期格式差異很大
    （FCA 是自訂的 "Weekday, Month DD, YYYY - HH:MM"，SEC 是標準 RFC822），
    存成同一格式後，下游（dashboard 週彙總）才不用管是哪個來源。
    """
    feed = feedparser.parse(source["rss_url"])
    entries = []
    for e in feed.entries:
        published_parsed = e.get("published_parsed")
        if published_parsed:
            published_iso = datetime.fromtimestamp(timegm(published_parsed), tz=timezone.utc).isoformat()
        elif source.get("date_format") and e.get("published"):
            try:
                published_iso = datetime.strptime(e["published"], source["date_format"]).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                published_iso = None
        else:
            published_iso = None

        entries.append({
            "title": e.get("title"),
            "link": e.get("link"),
            "published": published_iso,
            "guid": e.get("id"),
            "source": source["code"],
        })
    return entries


def fetch_article_text(url: str) -> str | None:
    """抓單篇公告頁面，回傳正文純文字。找不到內容時回傳 None。"""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    container = soup.find("main") or soup.find("article")
    if container is None:
        container = soup

    paragraphs = container.find_all("p")
    text = " ".join(p.get_text(strip=True) for p in paragraphs)
    return text or None


if __name__ == "__main__":
    for source in SOURCES:
        entries = fetch_feed_entries(source)
        print(f"=== {source['name']} ({source['code']})：共 {len(entries)} 筆，最新 3 筆 ===\n")
        for entry in entries[:3]:
            print(f"- {entry['title']}")
            print(f"  {entry['link']}")
            print(f"  發布時間：{entry['published']}\n")

    if entries:
        first = entries[0]
        print("=== 抓取最後一個來源第一筆正文 ===")
        print(f"標題：{first['title']}")
        text = fetch_article_text(first["link"])
        if text:
            print(f"正文長度：{len(text)} 字")
            print(text[:300] + "...")
        else:
            print("抓取失敗或找不到正文")
