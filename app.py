"""Week 3: Streamlit dashboard，讀取 SQLite 裡的公告資料。介面文字支援中/英切換。"""
import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# 類別色 1（藍）/ 2（橘），取自驗證過色盲安全性的固定順序調色盤，相鄰兩色的辨識度已通過檢查。
COLOR_TOTAL = "#2a78d6"
COLOR_HIGH_RISK = "#eb6834"
COLOR_BAR = "#2a78d6"

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
        "trend_header": "趨勢與分析",
        "chart_weekly_title": "每週公告趨勢",
        "chart_total": "公告總數",
        "chart_high_risk": "高風險公告數",
        "chart_week_axis": "週別",
        "chart_area_title": "業務範圍分布",
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
        "trend_header": "Trends & Breakdown",
        "chart_weekly_title": "Weekly Announcement Trend",
        "chart_total": "Total",
        "chart_high_risk": "High-risk",
        "chart_week_axis": "Week",
        "chart_area_title": "Announcements by Business Area",
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
risk_display = RISK_LEVEL_DISPLAY.get(lang, {})
area_display = BUSINESS_AREA_DISPLAY.get(lang, {})

df = load_data()

st.title(t["title"])
st.caption(t["caption"])

col1, col2, col3 = st.columns(3)
col1.metric(t["metric_total"], len(df))
col2.metric(t["metric_high_risk"], int((df["risk_level"] == "高").sum()))
col3.metric(t["metric_deadline"], int(df["deadline"].notna().sum()))

# published_date 是 feedparser 給的人類可讀字串（例："Wednesday, August 5, 2026 - 11:32"），
# 圖表需要真正的日期型別才能依週彙總。
df["published_dt"] = pd.to_datetime(df["published_date"], format="%A, %B %d, %Y - %H:%M", errors="coerce")

st.subheader(t["trend_header"])

weekly = (
    df.dropna(subset=["published_dt"])
    .set_index("published_dt")
    .resample("W")
    .agg(total=("url", "count"), high_risk=("risk_level", lambda s: (s == "高").sum()))
    .reset_index()
)
weekly_long = weekly.melt(
    id_vars="published_dt", value_vars=["total", "high_risk"],
    var_name="series", value_name="count",
)
series_label = {"total": t["chart_total"], "high_risk": t["chart_high_risk"]}
weekly_long["series"] = weekly_long["series"].map(series_label)

trend_chart = (
    alt.Chart(weekly_long)
    .mark_line(point=True, strokeWidth=2)
    .encode(
        x=alt.X("published_dt:T", title=None, axis=alt.Axis(format="%b %d")),
        y=alt.Y("count:Q", title=None),
        color=alt.Color(
            "series:N",
            scale=alt.Scale(domain=[t["chart_total"], t["chart_high_risk"]], range=[COLOR_TOTAL, COLOR_HIGH_RISK]),
            legend=alt.Legend(title=None),
        ),
        tooltip=[alt.Tooltip("published_dt:T", title=t["chart_week_axis"]), "series:N", "count:Q"],
    )
    .properties(height=280, title=t["chart_weekly_title"])
)
st.altair_chart(trend_chart, use_container_width=True)

area_counts = df["business_area"].value_counts().reset_index()
area_counts.columns = ["business_area", "count"]
if lang == "en":
    area_counts["business_area"] = area_counts["business_area"].map(lambda v: area_display.get(v, v))

area_chart = (
    alt.Chart(area_counts)
    .mark_bar(color=COLOR_BAR, cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
    .encode(
        x=alt.X("count:Q", title=t["chart_area_axis"]),
        y=alt.Y("business_area:N", sort="-x", title=None),
        tooltip=["business_area:N", "count:Q"],
    )
    .properties(height=280, title=t["chart_area_title"])
)
st.altair_chart(area_chart, use_container_width=True)

st.subheader(t["deadline_header"])
df["deadline_dt"] = pd.to_datetime(df["deadline"], errors="coerce")
today = pd.Timestamp.now().normalize()
upcoming = df[df["deadline_dt"].notna() & (df["deadline_dt"] >= today)].sort_values("deadline_dt").copy()

if upcoming.empty:
    st.caption(t["deadline_empty"])
else:
    upcoming[t["deadline_days_left"]] = (upcoming["deadline_dt"] - today).dt.days.map(lambda d: f"{d} {t['deadline_days_unit']}")
    upcoming["_risk_display"] = upcoming["risk_level"].map(lambda v: risk_display.get(v, v)) if lang == "en" else upcoming["risk_level"]
    upcoming["_area_display"] = upcoming["business_area"].map(lambda v: area_display.get(v, v)) if lang == "en" else upcoming["business_area"]

    upcoming_display = upcoming[["deadline", t["deadline_days_left"], "_risk_display", "_area_display", "title", "url"]].rename(
        columns={
            "deadline": t["columns"]["deadline"],
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
            t["columns"]["risk_level"]: st.column_config.TextColumn(width="small"),
            t["columns"]["business_area"]: st.column_config.TextColumn(width="medium"),
            t["columns"]["title"]: st.column_config.TextColumn(width="large"),
            t["deadline_link_col"]: st.column_config.LinkColumn(width="small", display_text="↗"),
        },
    )

st.sidebar.header(t["sidebar_header"])
risk_options = sorted(df["risk_level"].dropna().unique())
area_options = sorted(df["business_area"].dropna().unique())

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
