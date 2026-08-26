"""LLM 摘要分類層——上層只呼叫 summarize_announcement，不需要知道背後用哪家供應商。"""
import os

# 固定分類清單。原本讓 LLM 自由生成 business_area 導致每篇幾乎都不同分類，
# 篩選器形同虛設；改成強制單選讓分類真的有篩選意義。
BUSINESS_AREAS = [
    "消費者保護與產品行銷",
    "洗錢防制與金融犯罪",
    "市場行為與交易誠信",
    "審慎監管與資本要求",
    "公司治理與高階人員問責",
    "資本市場與上市監管",
    "交易申報與市場基礎設施",
    "監管政策與合規流程",
]

PROMPT_TEMPLATE = """你是RegTech合規分析助手。根據以下監管公告，回傳純JSON（不要有其他文字）：
{{"summary": "3句話摘要", "business_area": "受影響業務範圍", "risk_level": "高/中/低", "deadline": "YYYY-MM-DD 格式的實際日期，若無則為null"}}

summary 規則：用英文撰寫，貼近原文語感，不要翻譯成中文（監管公告原文本身就是英文，直接摘要即可）。

deadline 規則：只能填「YYYY-MM-DD」格式的具體日期，不可填相對時間描述（例如「60 days after publication」「3 months from the hearing date」）。如果原文只給了相對時間、沒有寫出可以直接換算的具體日期，一律回傳 null，不要自己去猜或計算。

business_area 規則：只能從下面清單中「擇一」填入，不可自創、不可合併多個、不可加註說明文字（清單本身是中文分類名稱，照原樣輸出）：
{business_areas}

risk_level 判斷標準：
- 高：有明確截止日期需在期限內完成因應，或直接影響機構的合規義務（例如新規則、執法處分、罰款、禁業、涉及客戶資產安全）
- 中：屬產業趨勢、政策方向、諮詢文件或非強制性指引，應留意但無立即行動壓力
- 低：一般性公告、人事任命、組織消息，對外部機構無直接合規影響

標題：{title}
內文：{text}"""


def summarize_announcement(title: str, text: str) -> dict | None:
    provider = os.getenv("LLM_PROVIDER", "gemini")
    prompt = PROMPT_TEMPLATE.format(
        business_areas="\n".join(f"- {area}" for area in BUSINESS_AREAS),
        title=title,
        text=text,
    )
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
        except errors.ClientError as exc:
            # 429 是免費額度的「每分鐘請求數」限流（多來源後單次批次量變大，更容易撞到）。
            # 這是暫時性問題值得重試；其他 4xx（例如模型名稱打錯的 404）重試沒有意義，直接往上拋。
            if exc.code != 429 or attempt == max_retries - 1:
                raise
            time.sleep(20)


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
    from fetch import SOURCES, fetch_feed_entries, fetch_article_text

    entries = fetch_feed_entries(SOURCES[0])
    first = entries[0]
    text = fetch_article_text(first["link"])

    print(f"標題：{first['title']}\n")
    result = summarize_announcement(first["title"], text)
    if result is None:
        print("摘要解析失敗")
    else:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
