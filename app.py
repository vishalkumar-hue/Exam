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
COLUMN_MAP = {
    "UID": "UID",
    "Center Code": "Center_Name",          # column B (full location name)
    "Project Code": "Project_Code",
    "Month": "Month",
    "Budget Head": "Budget_Head",
    "Budget": "Budget",
    "Expence": "Expense",
    "Approved Expence": "Approved_Expense",
    "Budget Vs Expence": "Budget_vs_Expense",
    "Budget Vs Approved Expence": "Budget_vs_Approved",
    "Not Releted Budget": "Not_Related_Budget",
    "Final Budget": "Final_Budget",
    "State": "State",
    "Revenue": "Revenue",
}

NUMERIC_COLS = [
    "Budget", "Expense", "Approved_Expense", "Budget_vs_Expense",
    "Budget_vs_Approved", "Not_Related_Budget", "Final_Budget", "Revenue",
]


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_URL)

    # Column N is a second "Center Code" (short code like CB1011) — pandas
    # will auto-suffix duplicate header names as "Center Code.1"
    rename = dict(COLUMN_MAP)
    if "Center Code.1" in df.columns:
        rename["Center Code.1"] = "Center_Code"
    df = df.rename(columns=rename)

    if "Center_Code" not in df.columns:
        # fallback: derive from UID e.g. "CB1011 Dec_25" -> "CB1011"
        df["Center_Code"] = df["UID"].astype(str).str.split().str[0]

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = (
                df[col].astype(str).str.replace(",", "", regex=False).str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.dropna(how="all")
    df = df[df["Budget_Head"].notna()] if "Budget_Head" in df.columns else df
    return df


df = load_data()

if df.empty:
    st.error(
        "Data load nahi ho paya. Sheet sharing check karo — "
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
    center_grp = (
        filtered.groupby("Center_Name")[["Budget", "Expense"]]
        .sum()
        .sort_values("Budget", ascending=False)
        .reset_index()
    )
    fig1 = px.bar(
        center_grp,
        x="Center_Name",
        y=["Budget", "Expense"],
        barmode="group",
        labels={"value": "Amount (₹)", "Center_Name": "Center", "variable": ""},
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
