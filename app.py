import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Exam Center Budget Dashboard", layout="wide")

# ---------------- CONFIG ----------------
SHEET_ID = "1P8awjtc-dwxCce1WJLDixljqL37yqCxnOe5QZ75_gIw"
GID = "1873962246"  # "Exam" tab
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
PERIOD_LABEL = ""  # e.g. "FY 2025-26"
TEMPLATE_PATH = Path(__file__).parent / "dashboard_template.html"

# Har field ke liye possible column names (normalized: lowercase, no spaces/symbols)
CANDIDATES = {
    "state": ["state"],
    "centerName": ["centername", "centrename", "center", "centre", "examcenter", "examcentre", "centername"],
    "centerCode": ["centercode", "centrecode", "code"],
    "projectCode": ["projectcode", "project"],
    "budgetHead": ["budgethead", "head", "expensehead", "budgetheadname"],
    "month": ["month", "monthname", "billingmonth"],
    "budget": ["budget", "budgetamount"],
}
EXPENSE_CANDIDATES = ["expence", "expense", "approvedexpence", "approvedexpense"]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


@st.cache_data(ttl=300, show_spinner="Sheet se data la raha hoon...")
def load_data():
    df = pd.read_csv(CSV_URL)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    return df


def find_col(df, candidates):
    nmap = {norm(c): c for c in df.columns}
    for cand in candidates:
        if cand in nmap:
            return nmap[cand]
    return None


def to_num(x):
    try:
        if pd.isna(x):
            return 0.0
        return float(str(x).replace(",", "").replace("₹", "").strip() or 0)
    except Exception:
        return 0.0


def js_json(obj):
    return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")


def build_html(df, colmap, expense_col):
    def g(r, key):
        c = colmap.get(key)
        if not c:
            return ""
        v = r.get(c)
        return "" if pd.isna(v) else str(v).strip()

    rows = []
    for _, r in df.iterrows():
        budget = to_num(r.get(colmap["budget"]))
        expense = to_num(r.get(expense_col))
        rows.append({
            "state": g(r, "state"),
            "centerName": g(r, "centerName") or g(r, "centerCode"),
            "centerCode": g(r, "centerCode"),
            "projectCode": g(r, "projectCode"),
            "budgetHead": g(r, "budgetHead"),
            "month": g(r, "month"),
            "budget": budget,
            "expense": expense,
            "variance": budget - expense,
            "overBudget": expense > budget,
            "allColumns": {c: ("" if pd.isna(v) else str(v)) for c, v in r.items()},
        })

    month_order = list(dict.fromkeys(r["month"] for r in rows if r["month"]))
    all_headers = [str(c) for c in df.columns]
    default_cols = [colmap[k] for k in ["centerName", "centerCode", "state", "projectCode", "budgetHead", "month", "budget"] if colmap.get(k)]
    if expense_col not in default_cols:
        default_cols.append(expense_col)

    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("__ROWS_JSON__", js_json(rows))
    html = html.replace("__MONTH_ORDER_JSON__", js_json(month_order))
    html = html.replace("__ALL_HEADERS_JSON__", js_json(all_headers))
    html = html.replace("__DEFAULT_COLUMNS_JSON__", js_json(default_cols))
    html = html.replace("__PERIOD_LABEL__", PERIOD_LABEL.replace("'", "\\'"))
    return html


# ---------------- UI ----------------
top1, top2 = st.columns([6, 1])
top1.title("Exam Center Budget Dashboard")
if top2.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

if not TEMPLATE_PATH.exists():
    st.error("dashboard_template.html file app.py ke same folder mein nahi mili.")
    st.stop()

try:
    df = load_data()
except Exception as e:
    st.error("Google Sheet load nahi hui. Sharing 'Anyone with the link – Viewer' hai ya nahi check karo.")
    st.exception(e)
    st.stop()

colmap = {k: find_col(df, v) for k, v in CANDIDATES.items()}

# Expense column options (Expence / Approved Expence)
nmap = {norm(c): c for c in df.columns}
expense_options = [nmap[c] for c in EXPENSE_CANDIDATES if c in nmap]

if not colmap["budget"] or not expense_options:
    st.error("Budget ya Expense column nahi mila.")
    st.write("Sheet ke actual columns:", list(df.columns))
    st.stop()

expense_col = st.sidebar.selectbox("Expense column", expense_options, index=0)

missing_optional = [k for k, v in colmap.items() if not v]
if missing_optional:
    with st.expander("⚠️ Kuch columns auto-detect nahi hue (dashboard phir bhi chalega)"):
        st.write("Nahi mile:", missing_optional)
        st.write("Sheet ke actual columns:", list(df.columns))

components.html(build_html(df, colmap, expense_col), height=2400, scrolling=True)
