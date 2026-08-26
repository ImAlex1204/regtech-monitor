"""Week 1: 抓 FCA RSS feed，並解析單篇公告正文。"""
import feedparser
import requests
from bs4 import BeautifulSoup

FCA_RSS_URL = "https://www.fca.org.uk/news/rss.xml"
USER_AGENT = "RegTech-Monitor-Student-Project/0.1 (contact: imalex1204@gmail.com)"


def fetch_feed_entries(url: str = FCA_RSS_URL) -> list[dict]:
    """抓 RSS feed，回傳簡化過的條目 list。"""
    feed = feedparser.parse(url)
    entries = []
    for e in feed.entries:
        entries.append({
            "title": e.get("title"),
            "link": e.get("link"),
            "published": e.get("published"),
            "guid": e.get("id"),
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
    entries = fetch_feed_entries()
    print(f"共抓到 {len(entries)} 筆公告，顯示最新 5 筆：\n")
    for entry in entries[:5]:
        print(f"- {entry['title']}")
        print(f"  {entry['link']}")
        print(f"  發布時間：{entry['published']}\n")

    if entries:
        first = entries[0]
        print("=== 抓取第一筆正文 ===")
        print(f"標題：{first['title']}")
        text = fetch_article_text(first["link"])
        if text:
            print(f"正文長度：{len(text)} 字")
            print(text[:300] + "...")
        else:
            print("抓取失敗或找不到正文")
