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
        "columns": {
            "published_date": "發布日期",
            "title": "標題",
            "risk_level": "風險等級",
            "business_area": "受影響業務範圍",
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

# 風險等級是固定的三個值（受控詞彙），非自由文字，所以連同介面一起提供英文顯示對照。
RISK_LEVEL_DISPLAY = {"en": {"高": "High", "中": "Medium", "低": "Low"}}


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
selected_risk = st.sidebar.multiselect(
    t["risk_filter"], risk_options, default=risk_options,
    format_func=lambda v: risk_display.get(v, v),
)
selected_area = st.sidebar.multiselect(t["area_filter"], area_options, default=area_options)

filtered = df[df["risk_level"].isin(selected_risk) & df["business_area"].isin(selected_area)]

st.subheader(t["subheader"].format(n=len(filtered)))

display_df = filtered[["published_date", "title", "risk_level", "business_area", "deadline", "summary", "url"]].copy()
if lang == "en":
    display_df["risk_level"] = display_df["risk_level"].map(lambda v: risk_display.get(v, v))
display_df = display_df.rename(columns=t["columns"])

st.dataframe(display_df, use_container_width=True, hide_index=True)
