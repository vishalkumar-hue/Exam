import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Exam Center Budget Dashboard", layout="wide")

# ---------------- CONFIG: apne Excel ke column names yahan set karo ----------------
COL = {
    "state": "State",
    "centerName": "Center Name",
    "centerCode": "Center Code",
    "projectCode": "Project Code",
    "budgetHead": "Budget Head",
    "month": "Month",
    "budget": "Budget",
    "expense": "Expense",
}
# Detail tab mein default dikhne wale columns (khali chhodo to sab dikhenge)
DEFAULT_COLUMNS = ["Center Name", "Center Code", "Project Code", "Budget Head", "Month", "Budget", "Expense"]
PERIOD_LABEL = ""  # e.g. "FY 2025-26"

TEMPLATE_PATH = Path(__file__).parent / "dashboard_template.html"


def to_num(x):
    try:
        return float(str(x).replace(",", "").replace("₹", "").strip())
    except Exception:
        return 0.0


def build_rows(df):
    rows = []
    for _, r in df.iterrows():
        budget = to_num(r.get(COL["budget"]))
        expense = to_num(r.get(COL["expense"]))
        variance = budget - expense
        rows.append({
            "state": str(r.get(COL["state"], "") or ""),
            "centerName": str(r.get(COL["centerName"], "") or ""),
            "centerCode": str(r.get(COL["centerCode"], "") or ""),
            "projectCode": str(r.get(COL["projectCode"], "") or ""),
            "budgetHead": str(r.get(COL["budgetHead"], "") or ""),
            "month": str(r.get(COL["month"], "") or ""),
            "budget": budget,
            "expense": expense,
            "variance": variance,
            "overBudget": expense > budget,
            "allColumns": {c: ("" if pd.isna(v) else str(v)) for c, v in r.items()},
        })
    return rows


def js_json(obj):
    # "</" ko escape karte hain taaki <script> tag na toote
    return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")


def build_html(df):
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    rows = build_rows(df)
    month_order = list(dict.fromkeys(r["month"] for r in rows if r["month"]))
    all_headers = [str(c) for c in df.columns]
    default_cols = [c for c in DEFAULT_COLUMNS if c in all_headers]

    html = html.replace("__ROWS_JSON__", js_json(rows))
    html = html.replace("__MONTH_ORDER_JSON__", js_json(month_order))
    html = html.replace("__ALL_HEADERS_JSON__", js_json(all_headers))
    html = html.replace("__DEFAULT_COLUMNS_JSON__", js_json(default_cols))
    html = html.replace("__PERIOD_LABEL__", PERIOD_LABEL.replace("'", "\\'"))
    return html


st.title("Exam Center Budget Dashboard")

uploaded = st.file_uploader("Excel / CSV upload karo", type=["xlsx", "xls", "csv"])

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
    missing = [v for v in COL.values() if v not in df.columns]
    if missing:
        st.error(f"Yeh columns file mein nahi mile: {missing}")
        st.write("File ke columns:", list(df.columns))
    else:
        components.html(build_html(df), height=2400, scrolling=True)
else:
    st.info("Dashboard dekhne ke liye file upload karo.")
