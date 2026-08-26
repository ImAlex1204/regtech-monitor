"""LLM 摘要分類層——上層只呼叫 summarize_announcement，不需要知道背後用哪家供應商。"""
import os

PROMPT_TEMPLATE = """你是RegTech合規分析助手。根據以下監管公告，回傳純JSON（不要有其他文字）：
{{"summary": "3句話摘要", "business_area": "受影響業務範圍", "risk_level": "高/中/低", "deadline": "期限，若無則為null"}}

標題：{title}
內文：{text}"""


def summarize_announcement(title: str, text: str) -> dict | None:
    provider = os.getenv("LLM_PROVIDER", "gemini")
    prompt = PROMPT_TEMPLATE.format(title=title, text=text)
    if provider == "gemini":
        return _call_gemini(prompt)
    elif provider == "anthropic":
        return _call_anthropic(prompt)
    raise ValueError(f"未知的 LLM_PROVIDER: {provider}")


def _call_gemini(prompt: str, max_retries: int = 3) -> dict | None:
    import time
    from google import genai
    from google.genai import errors

    client = genai.Client()  # 讀 GEMINI_API_KEY
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
            return _parse_json(resp.text)
        except errors.ServerError:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # 1s, 2s, 4s：伺服器暫時過載，指數退避後重試


def _call_anthropic(prompt: str) -> dict | None:
    import anthropic
    client = anthropic.Anthropic()  # 讀 ANTHROPIC_API_KEY
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(resp.content[0].text)


def _parse_json(raw_text: str) -> dict | None:
    import json
    import re

    if raw_text is None:
        return None
    text = raw_text.strip()
    # LLM 有時會無視「不要有其他文字」的指示，把 JSON 包在 ```json ... ``` 裡
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from fetch import fetch_feed_entries, fetch_article_text

    entries = fetch_feed_entries()
    first = entries[0]
    text = fetch_article_text(first["link"])

    print(f"標題：{first['title']}\n")
    result = summarize_announcement(first["title"], text)
    if result is None:
        print("摘要解析失敗")
    else:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
