# RegTech 法規變動追蹤工具 — 技術規格書

追蹤自動化最大 FCA（英國金融行為監管總署，監管公告）。用 LLM 摘要分類，並以 dashboard 呈現的小型 RegTech 專案。目標：4 週內做出一個能發布履歷、GitHub 的完整作品。

## 技術棧總覽

| 項目 | 工具 |
|---|---|
| 資料來源 | FCA RSS feed |
| 抓取 | `requests`、`feedparser`、`beautifulsoup4` |
| 摘要分類 | Gemini API（免費額度，起步）；日後設計成可換 Anthropic API |
| 儲存 | SQLite（Python 內建 `sqlite3`，不需額外套件） |
| 呈現 | `streamlit` |
| 自動化（選配） | GitHub Actions |

---

## 第 0 步：環境架設

```
regtech-monitor/
├── .env                  # 存 API key，不要 commit
├── .gitignore            # 排除 .env, venv/, *.db
├── requirements.txt
├── fetch.py              # Week 1
├── pipeline.py           # Week 2
├── app.py                # Week 3（Streamlit）
└── data/
    └── announcements.db  # SQLite
```

`requirements.txt` 起步版：
```
requests
feedparser
beautifulsoup4
google-genai
streamlit
python-dotenv
```
（`anthropic` 先不裝——等真的要換模型供應商再加，這是 2c 的設計說明）

`.env` 內容：
```
LLM_PROVIDER=gemini
GEMINI_API_KEY=你的key
```

**驗收：** `git init` 完成、venv 啟用、`pip install -r requirements.txt` 成功、`.env` 裡的 `GEMINI_API_KEY` 能被讀到。

---

## 第 1 階段：資料來源（FCA RSS Feed）

- **網址：** `https://www.fca.org.uk/news/rss.xml`（已確認是 FCA 官方在用的真實 feed，其他訊息平台或第三方追蹤站，內容都不是最新）
- **格式：** 標準 RSS 2.0，每個 `<item>` 通常會有 `title`、`link`、`description`、`pubDate`、`guid` 這幾個欄位。**實際上不要憑空假設**——實際用 `feedparser` 抓一次資料，印出第一筆 `entry.keys()` 確認真正拿到哪些欄位，欄位命名可能跟預期不同。
- **禮貌爬蟲原則：** 加上 `User-Agent` header 表明身份，不要短時間內重複抓同一網址。正式排程執行時控制頻率（例如一天一次），這是對公開資料來源基本的禮貌，也是你之後寫 README 時可以提的工程細節。

**額外補充（不是這次要做的，但值得知道）：** FCA 在 2026/8/6 前推出了 Handbook API，把監管規則本身的結構化、更新可訂閱格式，官方公告說明這個 API 就是設計給 RegTech 工具使用的。跟本專案的差異是：Handbook API 給的是現行法規本文，本專案要追蹤的是新聞/公告的即時追蹤（如果之後有第五階段延伸，這是一個很自然的延伸方向，也是履歷上可以講的故事，能凸顯專業的深入細節）。

---

## 第 2 階段：抓取與解析（Week 1）

### 2a. 抓 RSS 條目

用 `feedparser.parse(url)`，回傳的 `feed.entries` 是一個 list，每個 entry 用屬性存取（`entry.title`、`entry.link`、`entry.published`）。

**驗收：** 印出最新 5 筆的標題和連結。

### 2b. 抓單篇內文

用 `requests.get(entry.link)` 拿到 HTML，再用 `BeautifulSoup` 找出正文段落。

**誠實聲明在這裡：** 我沒辦法保證 FCA 網站文章頁面目前確切的 CSS class name（這種細節網站改版就會變），所以我給你一個保守的選擇器，不如給你判斷邏輯：
1. 先試 `soup.find('main')` 或 `soup.find('article')`，多數現代網站的正文會在這兩個標籤之一
2. 如果找不到，退而求其次，抓所有 `<p>` 標籤、串起來當正文（這樣可能夾雜一些選單文字，但丟給 LLM 摘要，LLM 通常能自己過濾掉雜訊）
3. 實際動手前，花 2 分鐘用瀏覽器「檢查元素」看一眼真的頁面 HTML 結構，比猜測更快更準

**驗收：** 給一篇文章，能抓出乾淨可讀的正文（允許有一點雜訊，但主要內容要在）

### 2c. LLM 摘要分類

**為什麼選 Gemini API 而起步：** 你的判斷是對的——Anthropic API 沒有免費額度（不管用哪個模型都是按用量計費，claude.ai 網頁聊天有免費用量，但 API 是不同的）。Google 的 Gemini API 目前是主要供應商裡免費額度、日額度的選擇，不需要信用卡就能拿到 key。`gemini-2.5-flash` 的免費額度大致是每分鐘 10 次、每天數百次請求，這個小專案一天可能只處理個位數到幾十個新公告，額度綽綽有餘。可以不用擔心的是免費額度的請求內容 Google 可能拿來改善模型——因為這裡處理的是公開監管公告，不是敏感資料，這一點可以放心。

**不要寫死模型——用一層薄薄的介面把起來：**

```python
# llm_client.py
import os

PROMPT_TEMPLATE = """你是RegTech合規分析助手。根據以下監管公告，回傳純JSON（不要有其他文字）：
{{"summary": "3句話摘要", "business_area": "受影響業務範圍", "risk_level": "高/中/低", "deadline": "期限，若無則為null"}}

標題：{title}
內文：{text}"""

def summarize_announcement(title: str, text: str) -> dict:
    provider = os.getenv("LLM_PROVIDER", "gemini")
    prompt = PROMPT_TEMPLATE.format(title=title, text=text)
    if provider == "gemini":
        return _call_gemini(prompt)
    elif provider == "anthropic":
        return _call_anthropic(prompt)
    raise ValueError(f"未知的 LLM_PROVIDER: {provider}")

def _call_gemini(prompt: str) -> dict:
    from google import genai
    client = genai.Client()  # 讀 GEMINI_API_KEY
    resp = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)  # 見文末「執行變更紀錄」
    return _parse_json(resp.text)

def _call_anthropic(prompt: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()  # 讀 ANTHROPIC_API_KEY
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(resp.content[0].text)

def _parse_json(raw_text: str) -> dict | None:
    import json
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return None
```

重點是：`pipeline.py`（第 3 階段會寫）永遠只呼叫 `summarize_announcement(title, text)`，完全不需要知道背後用的是 Gemini 還是 Claude。之後想改，只要改 `.env` 裡的 `LLM_PROVIDER=anthropic`（加裝 `pip install anthropic`），其他程式碼一行都不用改。這也是履歷上可以講的一個小亮點（「設計成以 LLM 為抽象層，不綁死單一供應商」）。

**驗收：** 給一篇真實內容，跑完整流程能印出你期望格式給人看的結構化摘要；`_parse_json` 回傳 `None` 時，上層呼叫要能正確跳過而不是讓程式崩潰。

---

## 第 3 階段：批次處理與儲存（Week 2）

### 3a. 資料結構

SQLite 資料表建議欄位：

```sql
CREATE TABLE announcements (
    url TEXT PRIMARY KEY,
    title TEXT,
    published_date TEXT,
    summary TEXT,
    business_area TEXT,
    risk_level TEXT,
    deadline TEXT,
    fetched_at TEXT
);
```

用 `url`（或 RSS 的 `guid`）當 primary key，天然避免去重複。

### 3b. 批次迴圈 + 去重

把 RSS 裡每一筆，先檢查 `url` 是否已經在資料庫裡（`SELECT` 一次，或直接用 `INSERT OR IGNORE INTO ...`，衝突就自動忽略），沒有才走完整流程（呼叫 LLM API），避免重複呼叫 LLM 浪費費用。

### 3c. 錯誤處理

抓取失敗、網路錯誤、頁面結構跟預期不同、LLM 回傳解析失敗，就跳過該筆。印一行 log，不要讓整個批次因為一筆失敗而中斷。

**驗收：** 跑一次產出 10-20 筆結構化資料，重複執行不會產生重複記錄，中途手動製造一個錯誤（例如把連結改成一個壞連結），不會讓整個程式狀態卡死。

---

## 第 4 階段：Dashboard 呈現（Week 3）

用 `streamlit` 讀 SQLite 資料（`pandas.read_sql` 很方便），做一個簡單頁面：

- `st.dataframe()` 顯示主表格
- `st.sidebar.multiselect()` 依 `risk_level` 和 `business_area` 篩選
- 可選：`st.metric()` 顯示「本週高風險公告數」「逾期未處理數」等獨立呈現，讓表格更有分析感

執行方式：`streamlit run app.py`（本機瀏覽器會自動開啟）。

**驗收：** 打開頁面能看到數據、篩選功能正常運作。

---

## 第 5 階段：收尾（選配：自動化）（Week 4）

### 5a. 心臟：README

內容至少包含：
- **問題背景**：為什麼想要這個追蹤工具是有意義的，可以帶你自己在台灣金融業觀察到的真實痛點（連 FCA 自己都在推 API 開放這件事）
- **架構圖**：就是本文件的那張表格
- **如何執行**：安裝步驟、環境變數設定
- **截圖**：Dashboard 畫面

### 5b. 選配：自動排程

用 GitHub Actions 排程（例如每天跑一次），骨架大致是：`schedule` cron trigger → checkout repo → setup Python → 安裝套件 → 跑 `pipeline.py` → 把更新後的 `.db` 或匯出的 CSV commit 回 repo。`LLM_PROVIDER` 和 `GEMINI_API_KEY`（未來若換成 Anthropic 則是 `ANTHROPIC_API_KEY`）存在 GitHub repo 的 Secrets 裡，不要寫死在程式碼或 workflow 檔案裡。

### 5c. 選配：公開部署

把 Streamlit app 部署到 Streamlit Community Cloud（免費），拿到一個公開連結放履歷——比起只放程式碼連結，一個「點下去就能玩」的 live demo 說服力好很多。

**驗收：** 給陌生人的 README，5 分鐘內能理解這個專案在做什麼。為什麼需要、怎麼跑起來。

---

## 驗收標準總表

| 週次 | 產出 | 驗收 |
|---|---|---|
| Week 1 | 完整單篇公告的完整抓取流程 | 印出一筆高品質結構化摘要 |
| Week 2 | 批次處理 + 去重 + 儲存 | 10-20 筆資料，重跑不重複，故意插入錯誤不崩潰 |
| Week 3 | Streamlit dashboard | 本機可瀏覽、篩選正常 |
| Week 4 | README + 潤飾（+ 選配自動化/部署） | 給陌生人 5 分鐘看懂小專案 |

---

## 執行變更紀錄

實際動手做的過程中，若跟本文件原始規劃有出入，在這裡記錄「改了什麼、為什麼改」，方便之後回顧對照。

| 日期 | 變更 | 原因 |
|---|---|---|
| 2026-08-24 | `_call_gemini` 的模型從 `gemini-2.5-flash` 改為 `gemini-flash-latest` | 新申請的 API key 屬於「新用戶」帳號，實測 `gemini-2.5-flash` 回傳 404（官方訊息：不再對新用戶開放）。改用 `gemini-flash-latest` 別名，讓程式自動跟隨 Google 當前的穩定版 flash 模型，之後模型再迭代也不用回來改程式碼 |
| 2026-08-24 | `_call_gemini` 加上重試機制（攔截 `google.genai.errors.ServerError`，指數退避重試最多 3 次） | 批次跑 20 筆時遇到 Gemini 伺服器暫時性 503（高負載）錯誤，屬於暫時性問題，值得重試而非直接放棄該筆 |
| 2026-08-24 | `_call_gemini` 的模型再從 `gemini-flash-latest` 改為 `gemini-3.5-flash-lite` | 實測發現 `gemini-flash-latest` 目前指向 `gemini-3.7-flash`，這個（較新／preview 性質）模型的免費額度每天只有 20 次請求，遠低於規格書預期的「每天數百次」，批次測試很快就把額度用光（出現 429 RESOURCE_EXHAUSTED）。改用穩定版的 `gemini-3.5-flash-lite`，實測 19/20 筆成功，額度足夠。Google 目前把免費額度明確數字收進需登入的 AI Studio 儀表板，公開文件查不到，只能實測判斷 |
| 2026-08-24 | `_parse_json` 加上 markdown code fence 去除邏輯（正規表示式剝掉 ` ```json ... ``` `） | Week 2 批次測試 20 筆中有 1 筆解析失敗，重跑同一篇文章 3 次比對後發現：LLM 偶爾（約 1/3 機率）會無視 prompt 裡「不要有其他文字」的指示，把 JSON 包在 markdown code fence 裡，導致 `json.loads` 直接失敗。這是機率性問題，不是特定文章內容造成的 |
| 2026-08-26 | 把本份 spec md 複製一份到 `regtech-monitor/PROJECT_SPEC.md`（repo 內），README 的建置紀錄連結指向這份 repo 內複本，而非外層「RegTech Project」資料夾裡的這份原始工作版本 | git repo 實際上只是 `regtech-monitor/` 子資料夾，外層「RegTech Project」是專案管理用的容器、不會被 push 上 GitHub。若 README 連結指向 repo 外的路徑，陌生人 clone 下來後連結會失效，違背「5 分鐘看懂」的驗收標準。兩份檔案往後可能不同步，這份（外層）是對話中持續維護的工作版本，repo 內複本是發布快照 |
| 2026-08-26 | `.gitignore` 移除 `*.db` 排除規則，改為追蹤 `data/announcements.db` | 原始 `.gitignore` 排除 `*.db`，但第 5 階段選配的 5b（GitHub Actions 排程後要「把更新後的 .db commit 回 repo」）跟 5c（Streamlit Community Cloud 部署，需要 repo 裡本來就有資料，dashboard 才有東西可顯示）兩者都需要 db 被 git 追蹤，兩份規劃互相矛盾。決定追蹤 db，犧牲一點 git history 的乾淨度（binary diff）換取「repo clone 下來就能直接跑 dashboard 看到真實資料」的完整性 |
| 2026-08-26 | 5c 部署到 Streamlit Community Cloud 時**沒有**額外設定任何 Secrets | 原本以為部署也要帶 `GEMINI_API_KEY`，後來確認 `app.py` 只讀本地 `data/announcements.db`，完全不呼叫 LLM API，抓取與分類都在 5b 的排程裡離線完成，dashboard 純粹是唯讀展示層。比原規劃更簡單 |
| 2026-08-26 | `app.py` 加入介面文字中/英切換（sidebar toggle），範圍限定「介面文字」：標題、標籤、metric 名稱、表格欄位名稱、`risk_level` 的三個固定值（高/中/低 ↔ High/Medium/Low）。`summary`、`business_area` 這些 LLM 自由文字生成內容維持中文，不隨介面語言翻譯 | 使用者要求「中英文切換」，原本規劃外的追加需求。先確認範圍（只換介面文字，還是連 LLM 內容都要翻譯），後者需要改 schema、重新分類全部資料，工程量差很多；使用者選擇前者。`risk_level` 雖然是資料庫欄位，但因為是固定 3 個值的受控詞彙（不是自由文字），視為介面顯示的一部分一併翻譯，讓英文模式看起來完整、不會有殘留中文字 |
| 2026-08-26 | `app.py` 主表格改版：欄位順序改為「風險等級／業務範圍／日期／標題／期限」，拿掉 `summary`、`url` 欄位，改成點選列後在下方展開詳細卡片（含完整摘要與原文連結） | 使用者實測發現：篩選器選了風險等級/業務範圍，但表格因為標題欄位過寬，這兩個欄位跟摘要根本被擠出畫面外，篩選完全看不到「為什麼」。改成緊湊表格＋點選展開，兼顧「一眼掃過分類」跟「需要時看完整內容」兩種需求 |
| 2026-08-26 | `llm_client.py` 的 prompt 改版：`business_area` 從自由文字改成強制從固定 8 類清單擇一；`risk_level` 加入具體判準（有截止日期或直接合規義務＝高；產業趨勢/非強制指引＝中；人事/組織消息＝低）。新增 `reclassify.py`，對資料庫既有 21 筆重新抓正文、重新分類、覆寫結果 | 使用者發現 `business_area` 太細碎（21 筆對應 20 種近乎不重複的分類，篩選器形同虛設）。改版後降到 7 種、分布合理。`risk_level` 改版後「高」的筆數其實沒變（13/21），但分類邏輯從「憑感覺」變成「有明確依據」，且逐筆覆核後判斷大致合理（FCA 新聞本身執法/罰款/新規則比重確實高）。使用者確認先接受目前結果，不再進一步把「單一機構執法（非新規則）」下修為中風險 |
| 2026-08-26 | `app.py` 新增 `BUSINESS_AREA_DISPLAY` 英文對照表，英文模式下 `business_area`（篩選標籤、表格欄位、詳細卡片）都跟著翻譯 | 使用者發現英文模式下 `business_area` 仍顯示中文，跟 `risk_level` 已有的翻譯不一致。原因是加中英切換那次 `business_area` 還是自由文字（無法窮舉翻譯），後來才改成固定 8 類清單，但忘記回頭補上英文對照，是一個遺漏而非設計決定 |
| 2026-08-26 | Dashboard 新增三個區塊（原規劃外，使用者提議的深化功能）：①每週公告趨勢折線圖（總數 vs 高風險數，Altair）②業務範圍分布長條圖（Altair，水平長條、依數量排序）③即將到期清單（依 `deadline` 欄位，soonest-first，含剩餘天數與原文連結）。動手前先讀取 dataviz 技能取得配色方法論：折線圖用固定順序類別色第 1、2 色（已驗證色盲安全性的相鄰配對）；長條圖因類別已經在座標軸標示，色彩不需承擔額外辨識任務，改用單一色相 | 使用者主動提出想加視覺化，並邀請一起討論還有什麼更好的建議；我另外提了業務範圍分布圖跟即將到期清單兩個想法，使用者三個都要。實作時抓到兩個 bug：`risk_display`/`area_display` 變數定義寫在使用點之後（NameError，改到 `lang`/`t` 定義後就近初始化解決）；英文模式下「即將到期」表格因為業務範圍英文字串較長，把最右側的原文連結欄位擠出畫面外（比照主表格加 `column_config` 欄寬限制解決） |
