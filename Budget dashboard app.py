"""
Exam Center Budget vs Expense Dashboard — rich Chart.js version
Live data source: Google Sheet "Sanjay Jha Report Dashboard" -> "Exam" tab
Sheet must be shared as "Anyone with the link - Viewer".
"""

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
SHEET_ID = "1P8awjtc-dwxCce1WJLDixljqL37yqCxnOe5QZ75_gIw"
GID = "1873962246"  # Exam tab
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

st.set_page_config(page_title="Exam Center Budget Dashboard", layout="wide")

HEADER_ALIASES = {
    "uid": "UID",
    "centercode": "Center_Name",
    "projectcode": "Project_Code",
    "month": "Month",
    "budgethead": "Budget_Head",
    "budget": "Budget",
    "expence": "Expense",
    "expense": "Expense",
    "approvedexpence": "Approved_Expense",
    "approvedexpense": "Approved_Expense",
    "budgetvsexpence": "Budget_vs_Expense",
    "budgetvsexpense": "Budget_vs_Expense",
    "budgetvsapprovedexpence": "Budget_vs_Approved",
    "budgetvsapprovedexpense": "Budget_vs_Approved",
    "notreletedbudget": "Not_Related_Budget",
    "notrelatedbudget": "Not_Related_Budget",
    "finalbudget": "Final_Budget",
    "state": "State",
    "revenue": "Revenue",
}

NUMERIC_COLS = [
    "Budget", "Expense", "Approved_Expense", "Budget_vs_Expense",
    "Budget_vs_Approved", "Not_Related_Budget", "Final_Budget", "Revenue",
]
REQUIRED_COLS = ["Budget_Head", "Budget", "Expense"]


def _normalize(name: str) -> str:
    # pandas auto-suffixes repeated header names with ".1", ".2", ... when
    # reading a CSV that has the same column header twice (e.g. two
    # "Center Code" columns in the sheet) — strip that suffix before
    # matching, otherwise the 2nd "Center Code" column (-> "Center Code.1")
    # never matches and is left with its raw name, causing a later KeyError.
    s = re.sub(r"\.\d+$", "", str(name))
    return "".join(s.lower().split()).replace("_", "")


@st.cache_data(ttl=300)
def load_data():
    raw = pd.read_csv(CSV_URL)
    raw.columns = [str(c).strip() for c in raw.columns]
    orig_headers = list(raw.columns)

    new_cols = []
    seen_center_code_name = False
    for col in raw.columns:
        norm = _normalize(col)
        if norm == "centercode":
            if not seen_center_code_name:
                new_cols.append("Center_Name")
                seen_center_code_name = True
            else:
                new_cols.append("Center_Code")
        else:
            new_cols.append(HEADER_ALIASES.get(norm, col))

    clean = raw.copy()
    clean.columns = new_cols

    if "Center_Code" not in clean.columns and "UID" in clean.columns:
        clean["Center_Code"] = clean["UID"].astype(str).str.split().str[0]

    for col in NUMERIC_COLS:
        if col in clean.columns:
            clean[col] = (
                clean[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
                .str.strip()
            )
            clean[col] = pd.to_numeric(clean[col], errors="coerce").fillna(0)

    clean = clean.dropna(how="all")
    return raw, clean, orig_headers


try:
    raw_df, df, orig_headers = load_data()
except Exception as e:
    st.error(f"Google Sheet se data load karne mein dikkat aayi: {e}")
    st.stop()

missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(
        "Ye zaroori column(s) sheet mein nahi mil rahe: "
        f"{', '.join(missing)}.\n\n"
        "Sheet ke actual column headers neeche dikh rahe hain — inhe check "
        "karke app ke HEADER_ALIASES dictionary mein sahi naam add karo."
    )
    st.write("Sheet mein mile columns:", list(df.columns))
    st.stop()

if "Budget_Head" in df.columns:
    mask = df["Budget_Head"].notna()
    df = df[mask].reset_index(drop=True)
    raw_df = raw_df[mask.values].reset_index(drop=True)

if df.empty:
    st.error(
        "Data load nahi ho paya (0 rows). Sheet sharing check karo — "
        "'Anyone with the link - Viewer' set hona chahiye."
    )
    st.stop()

# ----------------------------------------------------------------------
# Build row-level records for the JS dashboard
# ----------------------------------------------------------------------
def month_sort_key(m):
    for fmt in ("%b_%y", "%B_%y", "%b-%y", "%b_%Y", "%B_%Y"):
        try:
            return datetime.strptime(str(m), fmt)
        except Exception:
            continue
    return datetime.max


months = (
    sorted(df["Month"].dropna().unique().tolist(), key=month_sort_key)
    if "Month" in df.columns
    else []
)

center_col = "Center_Name" if "Center_Name" in df.columns else "Center_Code"

rows = []
for i, r in df.iterrows():
    budget = float(r.get("Budget", 0) or 0)
    expense = float(r.get("Expense", 0) or 0)
    variance = budget - expense
    util_pct = (expense / budget * 100) if budget else 0
    all_cols = {h: (None if pd.isna(v) else v) for h, v in raw_df.iloc[i].items()}
    rows.append({
        "uid": str(r.get("UID", "")),
        "centerName": str(r.get(center_col, "")),
        "centerCode": str(r.get("Center_Code", "")),
        "projectCode": str(r.get("Project_Code", "")),
        "month": str(r.get("Month", "")),
        "budgetHead": str(r.get("Budget_Head", "")),
        "budget": budget,
        "expense": expense,
        "approvedExpense": float(r.get("Approved_Expense", 0) or 0),
        "budgetVsExpense": float(r.get("Budget_vs_Expense", 0) or 0),
        "budgetVsApproved": float(r.get("Budget_vs_Approved", 0) or 0),
        "finalBudget": float(r.get("Final_Budget", 0) or 0),
        "state": str(r.get("State", "")),
        "revenue": float(r.get("Revenue", 0) or 0),
        "variance": variance,
        "utilizationPct": util_pct,
        "overBudget": bool(expense > budget),
        "allColumns": all_cols,
    })

DEFAULT_COLUMNS = [c for c in orig_headers if c][:10]

# ----------------------------------------------------------------------
# Quick text-level insights shown above the interactive dashboard
# ----------------------------------------------------------------------
total_budget = df["Budget"].sum()
total_expense = df["Expense"].sum()
total_variance = total_budget - total_expense
over_budget_count = int((df["Expense"] > df["Budget"]).sum())
utilization = (total_expense / total_budget * 100) if total_budget else 0

head_grp = df.groupby("Budget_Head")[["Budget", "Expense"]].sum()
head_grp["Variance"] = head_grp["Budget"] - head_grp["Expense"]
worst_head = head_grp["Variance"].idxmin() if not head_grp.empty else "-"
best_head = head_grp["Variance"].idxmax() if not head_grp.empty else "-"

center_grp = df.groupby(center_col)[["Budget", "Expense"]].sum()
center_grp["Variance"] = center_grp["Budget"] - center_grp["Expense"]
worst_center = center_grp["Variance"].idxmin() if not center_grp.empty else "-"
best_center = center_grp["Variance"].idxmax() if not center_grp.empty else "-"

state_grp = (
    df.groupby("State")[["Budget", "Expense"]].sum() if "State" in df.columns else pd.DataFrame()
)

st.title("📊 Exam Center — Budget vs Expense Dashboard")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Budget", f"₹{total_budget:,.0f}")
c2.metric("Total Expense", f"₹{total_expense:,.0f}")
c3.metric("Net Variance", f"₹{total_variance:,.0f}")
c4.metric("Utilization", f"{utilization:.0f}%")
c5.metric("Over-Budget Items", f"{over_budget_count} / {len(df)}")

st.info(
    f"**Sabse zyada over-budget Budget Head:** {worst_head}  |  "
    f"**Sabse zyada saving wala Budget Head:** {best_head}\n\n"
    f"**Sabse zyada over-budget Center:** {worst_center}  |  "
    f"**Sabse zyada saving wala Center:** {best_center}"
    + (
        f"\n\n**States covered:** {', '.join(state_grp.index.astype(str))}"
        if not state_grp.empty
        else ""
    )
)

# ----------------------------------------------------------------------
# Render the interactive Chart.js dashboard
# ----------------------------------------------------------------------
template_path = Path(__file__).parent / "assets" / "exam_dashboard_template.html"
html = template_path.read_text(encoding="utf-8")
html = html.replace("__ROWS_JSON__", json.dumps(rows))
html = html.replace("__MONTH_ORDER_JSON__", json.dumps(months))
html = html.replace("__ALL_HEADERS_JSON__", json.dumps(orig_headers))
html = html.replace("__DEFAULT_COLUMNS_JSON__", json.dumps(DEFAULT_COLUMNS))
period_label = f"{months[0]} – {months[-1]}" if len(months) > 1 else (months[0] if months else "")
html = html.replace("__PERIOD_LABEL__", period_label)

components.html(html, height=2600, scrolling=True)

st.caption(f"Live data — auto-refreshes every 5 min from Google Sheet (gid={GID}).")
