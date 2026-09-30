"""
Exam Center Budget vs Expense Dashboard
Live data source: Google Sheet "Sanjay Jha Report Dashboard" -> "Exam" tab
Sheet must be shared as "Anyone with the link - Viewer" for this to work.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------------------------------------------------
# CONFIG — apna Sheet ID / gid yahan change kar sakte ho
# ----------------------------------------------------------------------
SHEET_ID = "1P8awjtc-dwxCce1WJLDixljqL37yqCxnOe5QZ75_gIw"
GID = "1873962246"  # Exam tab
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

st.set_page_config(page_title="Exam Center Budget Dashboard", layout="wide")

# ----------------------------------------------------------------------
# DATA LOAD
# ----------------------------------------------------------------------
# Normalized (lowercase, spaces/underscores stripped) header -> standard name.
# Handles minor spelling/spacing differences between what we expect and what
# the live sheet actually has (e.g. "Expence" vs "Expense", extra spaces).
HEADER_ALIASES = {
    "uid": "UID",
    "centercode": "Center_Name",          # first "Center Code" column (full name)
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
    return "".join(str(name).lower().split()).replace("_", "")


@st.cache_data(ttl=300)
def load_data():
    raw = pd.read_csv(CSV_URL)
    raw.columns = [str(c).strip() for c in raw.columns]

    new_cols = []
    seen_center_code_name = False
    for col in raw.columns:
        norm = _normalize(col)
        if norm == "centercode":
            # first occurrence = full location name, second = short code
            if not seen_center_code_name:
                new_cols.append("Center_Name")
                seen_center_code_name = True
            else:
                new_cols.append("Center_Code")
        else:
            new_cols.append(HEADER_ALIASES.get(norm, col))
    raw.columns = new_cols

    if "Center_Code" not in raw.columns and "UID" in raw.columns:
        raw["Center_Code"] = raw["UID"].astype(str).str.split().str[0]

    for col in NUMERIC_COLS:
        if col in raw.columns:
            raw[col] = raw[col].astype(str).str.replace(",", "", regex=False).str.strip()
            raw[col] = pd.to_numeric(raw[col], errors="coerce").fillna(0)

    raw = raw.dropna(how="all")
    return raw


try:
    df = load_data()
except Exception as e:
    st.error(f"Google Sheet se data load karne mein dikkat aayi: {e}")
    st.stop()

missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(
        "Ye zaroori column(s) sheet mein nahi mil rahe: "
        f"{', '.join(missing)}.\n\n"
        "Sheet ke actual column headers neeche dikh rahe hain — inhe check "
        "karke app.py ke HEADER_ALIASES dictionary mein sahi naam add karo."
    )
    st.write("Sheet mein mile columns:", list(df.columns))
    st.stop()

if "Budget_Head" in df.columns:
    df = df[df["Budget_Head"].notna()]

if df.empty:
    st.error(
        "Data load nahi ho paya (0 rows). Sheet sharing check karo — "
        "'Anyone with the link - Viewer' set hona chahiye."
    )
    st.stop()

# ----------------------------------------------------------------------
# SIDEBAR FILTERS
# ----------------------------------------------------------------------
st.sidebar.header("Filters")


def multiselect_filter(label, col):
    if col not in df.columns:
        return None
    options = sorted(df[col].dropna().unique().tolist())
    return st.sidebar.multiselect(label, options)


sel_state = multiselect_filter("State", "State")
sel_center = multiselect_filter("Center", "Center_Name")
sel_month = multiselect_filter("Month", "Month")
sel_head = multiselect_filter("Budget Head", "Budget_Head")

filtered = df.copy()
if sel_state:
    filtered = filtered[filtered["State"].isin(sel_state)]
if sel_center:
    filtered = filtered[filtered["Center_Name"].isin(sel_center)]
if sel_month:
    filtered = filtered[filtered["Month"].isin(sel_month)]
if sel_head:
    filtered = filtered[filtered["Budget_Head"].isin(sel_head)]

# ----------------------------------------------------------------------
# HEADER + KPIs
# ----------------------------------------------------------------------
st.title("📊 Exam Center — Budget vs Expense Dashboard")

total_budget = filtered["Budget"].sum()
total_expense = filtered["Expense"].sum()
total_variance = total_budget - total_expense
over_budget_rows = int((filtered["Expense"] > filtered["Budget"]).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Budget", f"₹{total_budget:,.0f}")
c2.metric("Total Expense", f"₹{total_expense:,.0f}")
c3.metric(
    "Net Variance",
    f"₹{total_variance:,.0f}",
    delta=f"{'Saving' if total_variance >= 0 else 'Over Budget'}",
)
c4.metric("Over-Budget Line Items", f"{over_budget_rows} / {len(filtered)}")

st.divider()

# ----------------------------------------------------------------------
# CHARTS
# ----------------------------------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Center-wise Budget vs Expense")
    center_col = "Center_Name" if "Center_Name" in filtered.columns else "Center_Code"
    center_grp = (
        filtered.groupby(center_col)[["Budget", "Expense"]]
        .sum()
        .sort_values("Budget", ascending=False)
        .reset_index()
    )
    fig1 = px.bar(
        center_grp,
        x=center_col,
        y=["Budget", "Expense"],
        barmode="group",
        labels={"value": "Amount (₹)", center_col: "Center", "variable": ""},
    )
    fig1.update_layout(xaxis_tickangle=-30, legend_title_text="")
    st.plotly_chart(fig1, use_container_width=True)

with col_right:
    st.subheader("Expense Share by Budget Head")
    head_grp = (
        filtered.groupby("Budget_Head")["Expense"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    fig2 = px.pie(head_grp, names="Budget_Head", values="Expense", hole=0.4)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Budget vs Expense Variance by Budget Head")
head_var = (
    filtered.groupby("Budget_Head")[["Budget", "Expense"]]
    .sum()
    .reset_index()
)
head_var["Variance"] = head_var["Budget"] - head_var["Expense"]
head_var["Status"] = head_var["Variance"].apply(
    lambda v: "Over Budget" if v < 0 else "Within Budget"
)
fig3 = px.bar(
    head_var.sort_values("Variance"),
    x="Variance",
    y="Budget_Head",
    orientation="h",
    color="Status",
    color_discrete_map={"Over Budget": "#e74c3c", "Within Budget": "#2ecc71"},
)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("State-wise Summary")
if "State" in filtered.columns and filtered["State"].nunique() > 0:
    state_grp = (
        filtered.groupby("State")[["Budget", "Expense"]].sum().reset_index()
    )
    state_grp["Variance"] = state_grp["Budget"] - state_grp["Expense"]
    st.dataframe(state_grp, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------
# DETAIL TABLE
# ----------------------------------------------------------------------
st.subheader("Detailed Data")


def highlight_over_budget(row):
    color = "background-color: #fdecea" if row["Expense"] > row["Budget"] else ""
    return [color] * len(row)


show_cols = [
    c
    for c in [
        "UID", "Center_Name", "Center_Code", "Project_Code", "Month",
        "Budget_Head", "Budget", "Expense", "Approved_Expense",
        "Budget_vs_Expense", "State",
    ]
    if c in filtered.columns
]
st.dataframe(
    filtered[show_cols].style.apply(highlight_over_budget, axis=1),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    f"Live data — auto-refreshes every 5 min from Google Sheet (gid={GID}). "
    f"Last loaded rows: {len(df)}"
)
