"""Week 3: Streamlit dashboard，讀取 SQLite 裡的公告資料。介面文字支援中/英切換。"""
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "data" / "announcements.db"

# 介面文字（chrome）雙語對照。LLM 生成的內容（summary、business_area）本身是中文，不在此翻譯範圍內。
TEXT = {
    "zh": {
        "page_title": "RegTech 法規變動追蹤",
        "title": "RegTech 法規變動追蹤 Dashboard",
        "caption": "資料來源：FCA（Financial Conduct Authority）RSS Feed",
        "metric_total": "追蹤公告總數",
        "metric_high_risk": "高風險公告數",
        "metric_deadline": "含明確期限公告數",
        "sidebar_header": "篩選",
        "risk_filter": "風險等級",
        "area_filter": "受影響業務範圍",
        "subheader": "公告列表（{n} 筆）",
        "lang_toggle": "English",
        "select_hint": "點選上方任一列，查看完整摘要與原文連結",
        "detail_deadline": "期限",
        "detail_deadline_none": "無",
        "detail_link": "查看原文公告",
        "columns": {
            "published_date": "發布日期",
            "title": "標題",
            "risk_level": "風險等級",
            "business_area": "業務範圍",
            "deadline": "期限",
            "summary": "摘要",
            "url": "連結",
        },
    },
    "en": {
        "page_title": "RegTech Monitor",
        "title": "RegTech Regulatory Monitor Dashboard",
        "caption": "Data source: FCA (Financial Conduct Authority) RSS Feed",
        "metric_total": "Total announcements",
        "metric_high_risk": "High-risk announcements",
        "metric_deadline": "With a stated deadline",
        "sidebar_header": "Filters",
        "risk_filter": "Risk level",
        "area_filter": "Business area",
        "subheader": "Announcements ({n})",
        "lang_toggle": "中文",
        "select_hint": "Select a row above to see the full summary and original link",
        "detail_deadline": "Deadline",
        "detail_deadline_none": "None",
        "detail_link": "View original announcement",
        "columns": {
            "published_date": "Published",
            "title": "Title",
            "risk_level": "Risk level",
            "business_area": "Business area",
            "deadline": "Deadline",
            "summary": "Summary",
            "url": "URL",
        },
    },
}

# 風險等級與業務範圍都是固定值（受控詞彙），非自由文字，所以連同介面一起提供英文顯示對照。
# summary 是真正的自由文字生成內容，維持中文、不在此翻譯範圍內。
RISK_LEVEL_DISPLAY = {"en": {"高": "High", "中": "Medium", "低": "Low"}}
BUSINESS_AREA_DISPLAY = {
    "en": {
        "消費者保護與產品行銷": "Consumer Protection & Financial Promotions",
        "洗錢防制與金融犯罪": "AML & Financial Crime",
        "市場行為與交易誠信": "Market Conduct & Trading Integrity",
        "審慎監管與資本要求": "Prudential Regulation & Capital",
        "公司治理與高階人員問責": "Governance & Senior Managers Accountability",
        "資本市場與上市監管": "Capital Markets & Listings",
        "交易申報與市場基礎設施": "Transaction Reporting & Market Infrastructure",
        "監管政策與合規流程": "Regulatory Policy & Compliance Operations",
    }
}


@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM announcements ORDER BY published_date DESC", conn)
    conn.close()
    return df


if "lang" not in st.session_state:
    st.session_state.lang = "zh"

st.set_page_config(page_title=TEXT[st.session_state.lang]["page_title"], layout="wide")

if st.sidebar.toggle(TEXT[st.session_state.lang]["lang_toggle"], value=(st.session_state.lang == "en")):
    st.session_state.lang = "en"
else:
    st.session_state.lang = "zh"

lang = st.session_state.lang
t = TEXT[lang]

df = load_data()

st.title(t["title"])
st.caption(t["caption"])

col1, col2, col3 = st.columns(3)
col1.metric(t["metric_total"], len(df))
col2.metric(t["metric_high_risk"], int((df["risk_level"] == "高").sum()))
col3.metric(t["metric_deadline"], int(df["deadline"].notna().sum()))

st.sidebar.header(t["sidebar_header"])
risk_options = sorted(df["risk_level"].dropna().unique())
area_options = sorted(df["business_area"].dropna().unique())

risk_display = RISK_LEVEL_DISPLAY.get(lang, {})
area_display = BUSINESS_AREA_DISPLAY.get(lang, {})
selected_risk = st.sidebar.multiselect(
    t["risk_filter"], risk_options, default=risk_options,
    format_func=lambda v: risk_display.get(v, v),
)
selected_area = st.sidebar.multiselect(
    t["area_filter"], area_options, default=area_options,
    format_func=lambda v: area_display.get(v, v),
)

filtered = df[df["risk_level"].isin(selected_risk) & df["business_area"].isin(selected_area)]

st.subheader(t["subheader"].format(n=len(filtered)))

# 摘要/連結不進主表格（否則會被標題擠出畫面外）。表格只留「一眼能掃過」的分類欄位，
# 點選某一列後在下方詳細卡片顯示完整摘要與原文連結。
grid_cols = ["risk_level", "business_area", "published_date", "title", "deadline"]
display_df = filtered[grid_cols].copy()
if lang == "en":
    display_df["risk_level"] = display_df["risk_level"].map(lambda v: risk_display.get(v, v))
    display_df["business_area"] = display_df["business_area"].map(lambda v: area_display.get(v, v))
display_df = display_df.rename(columns=t["columns"])

event = st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        t["columns"]["risk_level"]: st.column_config.TextColumn(width="small"),
        t["columns"]["business_area"]: st.column_config.TextColumn(width="medium"),
        t["columns"]["published_date"]: st.column_config.TextColumn(width="medium"),
        t["columns"]["title"]: st.column_config.TextColumn(width="large"),
        t["columns"]["deadline"]: st.column_config.TextColumn(width="small"),
    },
)

selected_rows = event.selection.rows if event and event.selection else []
if selected_rows:
    row = filtered.iloc[selected_rows[0]]
    risk_label = risk_display.get(row["risk_level"], row["risk_level"])
    area_label = area_display.get(row["business_area"], row["business_area"])
    deadline_label = row["deadline"] if pd.notna(row["deadline"]) else t["detail_deadline_none"]

    with st.container(border=True):
        st.markdown(f"#### {row['title']}")
        st.caption(f"{row['published_date']}  ·  {risk_label}  ·  {area_label}  ·  {t['detail_deadline']}: {deadline_label}")
        st.write(row["summary"])
        st.markdown(f"[{t['detail_link']} ↗]({row['url']})")
else:
    st.caption(t["select_hint"])
