"""Week 3: Streamlit dashboard，讀取 SQLite 裡的公告資料。"""
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "data" / "announcements.db"

st.set_page_config(page_title="RegTech 法規變動追蹤", layout="wide")


@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM announcements ORDER BY published_date DESC", conn)
    conn.close()
    return df


df = load_data()

st.title("RegTech 法規變動追蹤 Dashboard")
st.caption("資料來源：FCA（Financial Conduct Authority）RSS Feed")

col1, col2, col3 = st.columns(3)
col1.metric("追蹤公告總數", len(df))
col2.metric("高風險公告數", int((df["risk_level"] == "高").sum()))
col3.metric("含明確期限公告數", int(df["deadline"].notna().sum()))

st.sidebar.header("篩選")
risk_options = sorted(df["risk_level"].dropna().unique())
area_options = sorted(df["business_area"].dropna().unique())

selected_risk = st.sidebar.multiselect("風險等級", risk_options, default=risk_options)
selected_area = st.sidebar.multiselect("受影響業務範圍", area_options, default=area_options)

filtered = df[df["risk_level"].isin(selected_risk) & df["business_area"].isin(selected_area)]

st.subheader(f"公告列表（{len(filtered)} 筆）")
st.dataframe(
    filtered[["published_date", "title", "risk_level", "business_area", "deadline", "summary", "url"]],
    use_container_width=True,
    hide_index=True,
)
