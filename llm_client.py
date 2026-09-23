"""LLM 摘要分類層——上層只呼叫 summarize_announcement，不需要知道背後用哪家供應商。"""
import json
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

# 合規框架固定清單（名稱 -> 涵蓋範圍說明）。經過兩輪、各 81 筆的實測才定案：
# SOX/GDPR/DORA/ISO 27001 零命中刪除；Securities Act/Exchange Act 合併時變成 SEC 萬用標籤，拆開；
# 加 Crypto-asset regime（FCA、SEC 兩邊都有）。說明文字用英文，是實測時驗證過的寫法。
FRAMEWORKS = {
    "Consumer Duty": "UK FCA Consumer Duty (PRIN 2A). Tag only if the text names the Consumer Duty or its outcomes (fair value, consumer understanding, consumer support, products & services).",
    "SM&CR": "UK Senior Managers & Certification Regime. Tag only if the text names SM&CR, the Senior Managers Regime, the Certification Regime, or a specific Senior Manager Function. A generic ban of an individual under 'fit and proper' / FSMA is NOT enough.",
    "MAR": "Market Abuse Regulation (UK MAR / EU MAR): insider dealing, market manipulation, unlawful disclosure of inside information.",
    "MiFID II / UK MiFIR": "MiFID II / UK MiFIR: investment services, trading venues, transaction reporting, best execution.",
    "AML (MLRs / BSA)": "Anti-money-laundering law: UK Money Laundering Regulations 2017 / POCA, US Bank Secrecy Act.",
    "Securities Act": "US Securities Act of 1933: offerings, registration of securities, prospectus disclosure, Section 17(a) antifraud. Requires a specific provision, rule, registration requirement or charge under this Act.",
    "Exchange Act": "US Securities Exchange Act of 1934: exchanges, broker-dealer and municipal advisor registration, periodic reporting, proxy rules, Regulation NMS, Rule 10b-5. Requires a specific provision, rule or charge under this Act.",
    "Advisers Act / Investment Company Act": "US Investment Advisers Act of 1940 / Investment Company Act of 1940: investment advisers (not municipal advisors), registered funds and ETFs.",
    "Dodd-Frank": "US Dodd-Frank Act: security-based swaps (Title VII), whistleblower program, systemic risk.",
    "Crypto-asset regime": "Crypto-asset specific regulation in either jurisdiction: UK cryptoasset regime / cryptoasset registration, US SEC crypto asset rules, tokenized securities relief.",
}

PROMPT_TEMPLATE = """你是RegTech合規分析助手。根據以下監管公告，回傳純JSON（不要有其他文字）：
{{"summary": "3句話摘要", "business_area": "受影響業務範圍", "risk_level": "高/中/低", "deadline": "YYYY-MM-DD 格式的實際日期，若無則為null", "frameworks": [{{"name": "框架名稱", "reason": "一句理由"}}], "action": "一句建議行動"}}

summary 規則：用英文撰寫，貼近原文語感，不要翻譯成中文（監管公告原文本身就是英文，直接摘要即可）。

deadline 規則：只能填「YYYY-MM-DD」格式的具體日期，不可填相對時間描述（例如「60 days after publication」「3 months from the hearing date」）。如果原文只給了相對時間、沒有寫出可以直接換算的具體日期，一律回傳 null，不要自己去猜或計算。

business_area 規則：只能從下面清單中「擇一」填入，不可自創、不可合併多個、不可加註說明文字（清單本身是中文分類名稱，照原樣輸出）：
{business_areas}

risk_level 判斷標準：
- 高：有明確截止日期需在期限內完成因應，或直接影響機構的合規義務（例如新規則、執法處分、罰款、禁業、涉及客戶資產安全）
- 中：屬產業趨勢、政策方向、諮詢文件或非強制性指引，應留意但無立即行動壓力
- 低：一般性公告、人事任命、組織消息，對外部機構無直接合規影響

frameworks 規則（多選，可以是空陣列 []）：
- name 只能從這個清單原樣複製其中一個字串，不可自創、不可合併、不可附加說明：{framework_names}
- 只有在公告明確提到該框架、或提到依該框架制定的具體規則/條文/指控時才標；只是主題相近不算。零個標籤是正常的答案。
- reason 用英文一句話，必須引用或指出原文中提到該框架（或其下規則）的文字，不可只寫「relates to」這類籠統描述。
- 各框架涵蓋範圍：
{framework_descriptions}

action 規則：用英文寫「一句」給金融機構法遵團隊的建議行動，必須具體指出公告裡的義務、受影響對象或日期（例如 "Review transaction reporting processes against the revised UK MiFIR fields before 2027-03-01."），不可寫「Notify the compliance team to assess impact」這種放諸四海皆準的空話。risk_level 為「低」時可以寫 "No action required; for awareness only."

標題：{title}
內文：{text}"""


def summarize_announcement(title: str, text: str) -> dict | None:
    provider = os.getenv("LLM_PROVIDER", "gemini")
    prompt = PROMPT_TEMPLATE.format(
        business_areas="\n".join(f"- {area}" for area in BUSINESS_AREAS),
        framework_names=json.dumps(list(FRAMEWORKS)),
        framework_descriptions="\n".join(f"  - [{name}] {desc}" for name, desc in FRAMEWORKS.items()),
        title=title,
        text=text,
    )
    if provider == "gemini":
        result = _call_gemini(prompt)
    elif provider == "anthropic":
        result = _call_anthropic(prompt)
    else:
        raise ValueError(f"未知的 LLM_PROVIDER: {provider}")
    if result is not None:
        result["frameworks"] = normalize_frameworks(result.get("frameworks"))
    return result


def normalize_frameworks(raw) -> list[dict]:
    """把 LLM 回傳的框架標籤收斂成固定清單內的名稱，清單外的直接丟掉。

    不能只靠 prompt：第一輪實測有 66% 的名稱夾帶了說明文字（"SM&CR: UK Senior Managers ..."），
    所以名稱先切掉冒號後的內容再比對，同一框架重複出現只留第一個。
    """
    if not isinstance(raw, list):
        return []
    tags, seen = [], set()
    for item in raw:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").split(":")[0].strip()
        if name in FRAMEWORKS and name not in seen:
            seen.add(name)
            tags.append({"name": name, "reason": item.get("reason")})
    return tags


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
        model="claude-haiku-4-5-20251001", max_tokens=1000,
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
