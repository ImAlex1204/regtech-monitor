"""Streamlit dashboard，讀取 SQLite 裡的公告資料，比較 FCA（英國）與 SEC（美國）兩個監管機構。
介面文字支援中/英切換。"""
import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# 類別色 1（藍）/ 2（橘），取自驗證過色盲安全性的固定順序調色盤，相鄰兩色的辨識度已通過檢查。
# 這組顏色代表「監管機構」這個維度，整個 dashboard 所有圖表都用同一組對照，讀者只需要學一次。
COLOR_FCA = "#2a78d6"
COLOR_SEC = "#eb6834"
SOURCE_COLOR_SCALE = alt.Scale(domain=["FCA", "SEC"], range=[COLOR_FCA, COLOR_SEC])

DB_PATH = Path(__file__).parent / "data" / "announcements.db"

# 介面文字（chrome）雙語對照。LLM 生成的內容（summary、business_area）本身是中文，不在此翻譯範圍內。
TEXT = {
    "zh": {
        "page_title": "RegTech 法規變動追蹤",
        "title": "RegTech 法規變動追蹤 Dashboard",
        "caption": "資料來源：{sources} RSS Feed",
        "metric_total": "追蹤公告總數",
        "metric_high_risk": "高風險公告數",
        "metric_deadline": "含明確期限公告數",
        "sidebar_header": "篩選",
        "risk_filter": "風險等級",
        "area_filter": "受影響業務範圍",
        "source_filter": "監管機構",
        "subheader": "公告列表（{n} 筆）",
        "lang_toggle": "English",
        "select_hint": "點選上方任一列，查看完整摘要與原文連結",
        "detail_deadline": "期限",
        "detail_deadline_none": "無",
        "detail_link": "查看原文公告",
        "trend_header": "趨勢與分析",
        "compare_header": "依監管機構比較",
        "chart_total_by_source": "每週公告數（依機構）",
        "chart_high_risk_by_source": "每週高風險公告數（依機構）",
        "chart_area_title": "業務範圍分布（依機構）",
        "chart_area_axis": "公告數",
        "deadline_header": "即將到期",
        "deadline_days_left": "剩餘天數",
        "deadline_days_unit": "天",
        "deadline_empty": "目前沒有含明確期限、尚未到期的公告",
        "deadline_link_col": "原文",
        "columns": {
            "published_date": "發布日期",
            "title": "標題",
            "risk_level": "風險等級",
            "business_area": "業務範圍",
            "deadline": "期限",
            "summary": "摘要",
            "url": "連結",
            "source": "監管機構",
        },
    },
    "en": {
        "page_title": "RegTech Monitor",
        "title": "RegTech Regulatory Monitor Dashboard",
        "caption": "Data sources: {sources} RSS feed",
        "metric_total": "Total announcements",
        "metric_high_risk": "High-risk announcements",
        "metric_deadline": "With a stated deadline",
        "sidebar_header": "Filters",
        "risk_filter": "Risk level",
        "area_filter": "Business area",
        "source_filter": "Regulator",
        "subheader": "Announcements ({n})",
        "lang_toggle": "中文",
        "select_hint": "Select a row above to see the full summary and original link",
        "detail_deadline": "Deadline",
        "detail_deadline_none": "None",
        "detail_link": "View original announcement",
        "trend_header": "Trends & Breakdown",
        "compare_header": "By Regulator",
        "chart_total_by_source": "Weekly Announcements by Regulator",
        "chart_high_risk_by_source": "Weekly High-Risk Announcements by Regulator",
        "chart_area_title": "Announcements by Business Area & Regulator",
        "chart_area_axis": "Announcements",
        "deadline_header": "Upcoming Deadlines",
        "deadline_days_left": "Days left",
        "deadline_days_unit": "d",
        "deadline_empty": "No upcoming announcements with a stated deadline",
        "deadline_link_col": "Source",
        "columns": {
            "published_date": "Published",
            "title": "Title",
            "risk_level": "Risk level",
            "business_area": "Business area",
            "deadline": "Deadline",
            "summary": "Summary",
            "url": "URL",
            "source": "Regulator",
        },
    },
}

# 風險等級與業務範圍都是固定值（受控詞彙），非自由文字，所以連同介面一起提供英文顯示對照。
# summary 是真正的自由文字生成內容，維持中文、不在此翻譯範圍內。監管機構代碼（FCA/SEC）
# 兩種語言通用，不需要翻譯對照。
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


def source_kpi_row(sub_df: pd.DataFrame) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric(t["metric_total"], len(sub_df))
    c2.metric(t["metric_high_risk"], int((sub_df["risk_level"] == "高").sum()))
    c3.metric(t["metric_deadline"], int(sub_df["deadline"].notna().sum()))


if "lang" not in st.session_state:
    st.session_state.lang = "zh"

st.set_page_config(page_title=TEXT[st.session_state.lang]["page_title"], layout="wide")

if st.sidebar.toggle(TEXT[st.session_state.lang]["lang_toggle"], value=(st.session_state.lang == "en")):
    st.session_state.lang = "en"
else:
    st.session_state.lang = "zh"

lang = st.session_state.lang
t = TEXT[lang]
risk_display = RISK_LEVEL_DISPLAY.get(lang, {})
area_display = BUSINESS_AREA_DISPLAY.get(lang, {})

df = load_data()
df["published_dt"] = pd.to_datetime(df["published_date"], errors="coerce")
df["deadline_dt"] = pd.to_datetime(df["deadline"], errors="coerce")
# published_date 存的是機器好處理的 ISO 字串（跨來源統一格式），畫面上另外顯示人類好讀的版本。
df["published_display"] = df["published_dt"].dt.strftime("%Y-%m-%d %H:%M").fillna(df["published_date"])
# deadline 是 LLM 自由文字生成，偶爾不遵守「只給具體日期」的指示、混入「60 days after...」這種相對描述。
# 顯示層防禦：只顯示能成功解析成日期的值，parse 失敗（含這種相對描述）一律當作沒有期限處理，不顯示原始亂碼文字。
df["deadline_display"] = df["deadline_dt"].dt.strftime("%Y-%m-%d")
# 主表格放摘要「預覽」（截斷），讓使用者掃過整批篩選結果時就看得到分類依據的梗概，
# 不用每一列都點開；完整全文仍在點選展開的詳細卡片裡。
df["summary_preview"] = df["summary"].fillna("").apply(lambda s: s if len(s) <= 90 else s[:90] + "…")

st.title(t["title"])
st.caption(t["caption"].format(sources="、".join(sorted(df["source"].dropna().unique())) if lang == "zh" else ", ".join(sorted(df["source"].dropna().unique()))))

col1, col2, col3 = st.columns(3)
col1.metric(t["metric_total"], len(df))
col2.metric(t["metric_high_risk"], int((df["risk_level"] == "高").sum()))
col3.metric(t["metric_deadline"], int(df["deadline"].notna().sum()))

st.subheader(t["trend_header"])
st.markdown(f"**{t['compare_header']}**")

source_codes = sorted(df["source"].dropna().unique())
kpi_cols = st.columns(len(source_codes))
for col, code in zip(kpi_cols, source_codes):
    with col:
        st.caption(code)
        source_kpi_row(df[df["source"] == code])

weekly_by_source = (
    df.dropna(subset=["published_dt"])
    .groupby(["source", pd.Grouper(key="published_dt", freq="W")])
    .agg(total=("url", "count"), high_risk=("risk_level", lambda s: (s == "高").sum()))
    .reset_index()
)

trend_col1, trend_col2 = st.columns(2)
with trend_col1:
    total_trend = (
        alt.Chart(weekly_by_source)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("published_dt:T", title=None, axis=alt.Axis(format="%b %d")),
            y=alt.Y("total:Q", title=None),
            color=alt.Color("source:N", scale=SOURCE_COLOR_SCALE, legend=alt.Legend(title=None)),
            tooltip=["published_dt:T", "source:N", "total:Q"],
        )
        .properties(height=260, title=t["chart_total_by_source"])
    )
    st.altair_chart(total_trend, use_container_width=True)

with trend_col2:
    high_risk_trend = (
        alt.Chart(weekly_by_source)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("published_dt:T", title=None, axis=alt.Axis(format="%b %d")),
            y=alt.Y("high_risk:Q", title=None),
            color=alt.Color("source:N", scale=SOURCE_COLOR_SCALE, legend=alt.Legend(title=None)),
            tooltip=["published_dt:T", "source:N", "high_risk:Q"],
        )
        .properties(height=260, title=t["chart_high_risk_by_source"])
    )
    st.altair_chart(high_risk_trend, use_container_width=True)

area_by_source = df.groupby(["business_area", "source"]).size().reset_index(name="count")
if lang == "en":
    area_by_source["business_area"] = area_by_source["business_area"].map(lambda v: area_display.get(v, v))

area_chart = (
    alt.Chart(area_by_source)
    .mark_bar()
    .encode(
        y=alt.Y("business_area:N", sort=alt.EncodingSortField(field="count", op="sum", order="descending"), title=None),
        x=alt.X("count:Q", title=t["chart_area_axis"]),
        yOffset="source:N",
        color=alt.Color("source:N", scale=SOURCE_COLOR_SCALE, legend=alt.Legend(title=None)),
        tooltip=["business_area:N", "source:N", "count:Q"],
    )
    .properties(height=320, title=t["chart_area_title"])
)
st.altair_chart(area_chart, use_container_width=True)

st.subheader(t["deadline_header"])
today = pd.Timestamp.now().normalize()
upcoming = df[df["deadline_dt"].notna() & (df["deadline_dt"] >= today)].sort_values(["source", "deadline_dt"]).copy()

if upcoming.empty:
    st.caption(t["deadline_empty"])
else:
    upcoming[t["deadline_days_left"]] = (upcoming["deadline_dt"] - today).dt.days.map(lambda d: f"{d} {t['deadline_days_unit']}")
    upcoming["_risk_display"] = upcoming["risk_level"].map(lambda v: risk_display.get(v, v)) if lang == "en" else upcoming["risk_level"]
    upcoming["_area_display"] = upcoming["business_area"].map(lambda v: area_display.get(v, v)) if lang == "en" else upcoming["business_area"]

    upcoming_display = upcoming[["deadline_display", t["deadline_days_left"], "source", "_risk_display", "_area_display", "title", "url"]].rename(
        columns={
            "deadline_display": t["columns"]["deadline"],
            "source": t["columns"]["source"],
            "_risk_display": t["columns"]["risk_level"],
            "_area_display": t["columns"]["business_area"],
            "title": t["columns"]["title"],
            "url": t["deadline_link_col"],
        }
    )
    st.dataframe(
        upcoming_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            t["columns"]["deadline"]: st.column_config.TextColumn(width="small"),
            t["deadline_days_left"]: st.column_config.TextColumn(width="small"),
            t["columns"]["source"]: st.column_config.TextColumn(width="small"),
            t["columns"]["risk_level"]: st.column_config.TextColumn(width="small"),
            t["columns"]["business_area"]: st.column_config.TextColumn(width="medium"),
            t["columns"]["title"]: st.column_config.TextColumn(width="large"),
            t["deadline_link_col"]: st.column_config.LinkColumn(width="small", display_text="↗"),
        },
    )

st.sidebar.header(t["sidebar_header"])
risk_options = sorted(df["risk_level"].dropna().unique())
area_options = sorted(df["business_area"].dropna().unique())
source_options = sorted(df["source"].dropna().unique())

selected_source = st.sidebar.multiselect(t["source_filter"], source_options, default=source_options)
selected_risk = st.sidebar.multiselect(
    t["risk_filter"], risk_options, default=risk_options,
    format_func=lambda v: risk_display.get(v, v),
)
selected_area = st.sidebar.multiselect(
    t["area_filter"], area_options, default=area_options,
    format_func=lambda v: area_display.get(v, v),
)

filtered = df[
    df["source"].isin(selected_source)
    & df["risk_level"].isin(selected_risk)
    & df["business_area"].isin(selected_area)
].sort_values(["source", "published_dt"], ascending=[True, False])

st.subheader(t["subheader"].format(n=len(filtered)))

# 摘要/連結不進主表格（否則會被標題擠出畫面外）。表格只留「一眼能掃過」的分類欄位，
# 點選某一列後在下方詳細卡片顯示完整摘要與原文連結。
grid_cols = ["source", "risk_level", "business_area", "published_display", "title", "summary_preview", "deadline_display"]
display_df = filtered[grid_cols].copy()
if lang == "en":
    display_df["risk_level"] = display_df["risk_level"].map(lambda v: risk_display.get(v, v))
    display_df["business_area"] = display_df["business_area"].map(lambda v: area_display.get(v, v))
display_df = display_df.rename(columns={
    **t["columns"],
    "published_display": t["columns"]["published_date"],
    "deadline_display": t["columns"]["deadline"],
    "summary_preview": t["columns"]["summary"],
})

event = st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        t["columns"]["source"]: st.column_config.TextColumn(width="small"),
        t["columns"]["risk_level"]: st.column_config.TextColumn(width="small"),
        t["columns"]["business_area"]: st.column_config.TextColumn(width="medium"),
        t["columns"]["published_date"]: st.column_config.TextColumn(width="medium"),
        t["columns"]["title"]: st.column_config.TextColumn(width="medium"),
        t["columns"]["summary"]: st.column_config.TextColumn(width="large"),
        t["columns"]["deadline"]: st.column_config.TextColumn(width="small"),
    },
)

selected_rows = event.selection.rows if event and event.selection else []
if selected_rows:
    row = filtered.iloc[selected_rows[0]]
    risk_label = risk_display.get(row["risk_level"], row["risk_level"])
    area_label = area_display.get(row["business_area"], row["business_area"])
    deadline_label = row["deadline_display"] if pd.notna(row["deadline_display"]) else t["detail_deadline_none"]

    with st.container(border=True):
        st.markdown(f"#### {row['title']}")
        st.caption(f"{row['source']}  ·  {row['published_display']}  ·  {risk_label}  ·  {area_label}  ·  {t['detail_deadline']}: {deadline_label}")
        st.write(row["summary"])
        st.markdown(f"[{t['detail_link']} ↗]({row['url']})")
else:
    st.caption(t["select_hint"])
