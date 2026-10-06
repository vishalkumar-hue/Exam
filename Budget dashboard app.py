"""
Exam Center Budget vs Expense Dashboard  (v4)
Live data source: Google Sheet "Sanjay Jha Report Dashboard"
   - Infra  -> "Exam" tab (gid=1873962246)
   - APK    -> "APK" tab  (fetched by tab name)
Sheet must be shared as "Anyone with the link - Viewer".

v4 changes:
  1. Division switch at the top: Infra / APK (same analysis + charts for both)
  2. Heading shows the selected division

v3 changes:
  1. Clicking a center in the heatmap expands its details (rent, bills, all heads) right below that row, with All / month buttons
  2. "Utilization % by Center" chart now also shows Expense / Budget
  3. Comparison tab has a "Center-wise Cost Comparison" chart (Rent, Electricity, Water, Internet, DG ...)
"""

import json
import re
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

SHEET_ID = "1P8awjtc-dwxCce1WJLDixljqL37yqCxnOe5QZ75_gIw"
BASE = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

SOURCES = {
    "Infra": f"{BASE}/export?format=csv&gid=1873962246",          # Exam tab
    "APK":   f"{BASE}/gviz/tq?tqx=out:csv&sheet={quote('APK')}",  # APK tab (by name)
}

DASHBOARD_TEMPLATE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Exam Center Budget Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-datalabels/2.2.0/chartjs-plugin-datalabels.min.js"></script>
<style>
  :root{
    --bg:#0b1220; --panel:#121b2e; --panel-2:#17233a; --border:#223252;
    --text:#e7ecf5; --muted:#8ea0c2; --gold:#d9a441; --teal:#33b8a8;
    --coral:#e0665f; --violet:#8b7ee8; --grid:rgba(255,255,255,0.06);
  }
  *{box-sizing:border-box;}
  body{margin:0; font-family:'Segoe UI', Arial, sans-serif; background:var(--bg); color:var(--text);}
  .wrap{max-width:1360px; margin:0 auto; padding:28px 24px 60px;}
  .topbar{display:flex; align-items:flex-end; justify-content:space-between; border-bottom:1px solid var(--border); padding-bottom:18px; margin-bottom:22px; flex-wrap:wrap; gap:10px;}
  .topbar h1{font-size:22px; margin:0; font-weight:700;}
  .topbar h1 span{color:var(--gold);}
  .topbar .sub{color:var(--muted); font-size:12.5px; margin-top:4px;}
  .topbar-right{display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap;}
  .topsel-wrap label{font-size:10.5px; color:var(--muted); display:block; margin-bottom:3px;}
  .topsel{background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:7px 8px; font-size:12.5px; font-family:inherit;}
  .kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:14px; margin-bottom:22px;}
  .kpi{background:linear-gradient(160deg, var(--panel), var(--panel-2)); border:1px solid var(--border); border-radius:10px; padding:16px 18px;}
  .kpi .label{font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:0.6px;}
  .kpi .value{font-size:21px; font-weight:700; margin-top:6px; word-break:break-word;}
  .kpi .delta{font-size:11.5px; margin-top:4px;}
  .up{color:var(--teal);} .down{color:var(--coral);} .muted{color:var(--muted);}
  .note{font-size:12px; color:var(--muted); margin:-4px 0 14px;}
  .filters{display:flex; gap:10px; margin-bottom:10px; flex-wrap:wrap;}
  .filter-bar-wrap{border:1px solid var(--border); border-radius:10px; background:var(--panel); padding:14px 16px 6px; margin-bottom:20px;}
  .filter-bar-head{display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;}
  .filter-bar-head h4{margin:0; font-size:12.5px; color:var(--muted); text-transform:uppercase; letter-spacing:0.6px;}
  .clear-btn{background:transparent; border:1px solid var(--border); color:var(--muted); border-radius:6px; padding:5px 10px; font-size:11.5px; cursor:pointer; font-family:inherit;}
  .clear-btn:hover{color:var(--coral); border-color:var(--coral);}
  .export-btn{display:inline-flex; align-items:center; gap:6px; background:var(--panel-2); border:1px solid var(--border); color:var(--gold); border-radius:6px; padding:6px 12px; font-size:11.5px; font-weight:600; cursor:pointer; font-family:inherit; margin-bottom:10px;}
  .export-btn:hover{border-color:var(--gold); background:rgba(217,164,65,0.1);}
  .theme-picker{position:relative;}
  .theme-btn{display:flex; align-items:center; gap:7px; background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:7px 12px; font-size:12.5px; cursor:pointer; font-family:inherit;}
  .theme-btn:hover{border-color:var(--gold);}
  .theme-btn .dot{width:10px; height:10px; border-radius:50%; background:var(--gold); box-shadow:0 0 5px var(--gold);}
  .theme-panel{display:none; position:absolute; top:calc(100% + 6px); right:0; z-index:30; background:var(--panel-2); border:1px solid var(--border); border-radius:8px; width:190px; padding:8px; box-shadow:0 8px 24px rgba(0,0,0,0.45);}
  .theme-panel.open{display:block;}
  .theme-option{display:flex; align-items:center; gap:9px; font-size:12.5px; padding:7px 8px; border-radius:6px; cursor:pointer; color:var(--text);}
  .theme-option:hover{background:rgba(255,255,255,0.05);}
  .theme-option.selected{background:rgba(217,164,65,0.15); color:var(--gold); font-weight:600;}
  .theme-option .swatch{width:16px; height:16px; border-radius:50%; border:1px solid rgba(255,255,255,0.15); flex:none;}
  .multiselect{position:relative; min-width:170px; margin-bottom:10px;}
  .multiselect label{font-size:11.5px; color:var(--muted); display:block; margin-bottom:4px;}
  .ms-btn{width:100%; text-align:left; background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:7px 10px; font-size:13px; cursor:pointer; font-family:inherit; position:relative; padding-right:24px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
  .ms-btn::after{content:'▾'; position:absolute; right:9px; top:50%; transform:translateY(-50%); color:var(--muted); font-size:10px;}
  .ms-btn.active{border-color:var(--gold); color:var(--gold);}
  .ms-panel{display:none; position:absolute; top:calc(100% + 4px); left:0; z-index:20; background:var(--panel-2); border:1px solid var(--border); border-radius:8px; width:250px; max-height:290px; padding:8px; box-shadow:0 8px 24px rgba(0,0,0,0.4);}
  .ms-panel.open{display:block;}
  .ms-search{width:100%; background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:5px; padding:6px 8px; font-size:12.5px; margin-bottom:6px;}
  .ms-actions{display:flex; gap:8px; margin-bottom:6px; flex-wrap:wrap;}
  .ms-actions button{flex:1; background:transparent; border:1px solid var(--border); color:var(--muted); border-radius:5px; padding:4px 6px; font-size:11px; cursor:pointer; font-family:inherit; min-width:56px;}
  .ms-actions button:hover{color:var(--gold); border-color:var(--gold);}
  .ms-list{max-height:180px; overflow-y:auto;}
  .ms-option{display:flex; align-items:center; gap:7px; font-size:12.5px; padding:4px 3px; border-radius:4px; cursor:pointer;}
  .ms-option:hover{background:rgba(255,255,255,0.04);}
  .ms-option input{margin:0; accent-color:var(--gold);}
  .ms-option span{overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
  .tabbar{display:flex; gap:6px; margin-bottom:22px; border-bottom:1px solid var(--border); flex-wrap:wrap;}
  .tabbtn{background:transparent; border:none; color:var(--muted); font-size:13.5px; font-weight:600; padding:10px 14px; cursor:pointer; border-bottom:2px solid transparent; font-family:inherit;}
  .tabbtn:hover{color:var(--text);}
  .tabbtn.active{color:var(--gold); border-bottom:2px solid var(--gold);}
  .tabpage{display:none;} .tabpage.active{display:block;}
  .search-row{display:flex; gap:10px; margin-bottom:14px; align-items:flex-start; flex-wrap:wrap;}
  .search-row input[type=text]{background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:7px 10px; font-size:13px; min-width:220px;}
  tr.row-bad td{background:rgba(224,102,95,0.07);}
  .scroll-table{max-height:560px; overflow:auto;}
  .scroll-table table{position:relative;}
  .scroll-table thead th{position:sticky; top:0; background:var(--panel); z-index:1; white-space:nowrap;}
  .grid{display:grid; grid-template-columns:1.3fr 1fr; gap:16px; margin-bottom:16px;}
  .grid.even{grid-template-columns:1fr 1fr;}
  .card{background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:16px 18px; margin-bottom:16px;}
  .grid .card{margin-bottom:0;}
  .card h3{margin:0 0 12px; font-size:13.5px; color:var(--text); font-weight:600; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;}
  .card h3 .tag{font-size:10.5px; color:var(--muted); font-weight:400;}
  .chart-box{position:relative; height:300px;} .chart-box.tall{height:380px;}
  table{width:100%; border-collapse:collapse; font-size:12.5px;}
  th,td{padding:7px 6px; text-align:left; border-bottom:1px solid var(--grid);}
  th{color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase;}
  tr:hover td{background:rgba(255,255,255,0.02);}
  .num{text-align:right; font-variant-numeric:tabular-nums;}
  .heat td.hc{text-align:center; font-variant-numeric:tabular-nums; min-width:62px;}
  .pill{padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; white-space:nowrap;}
  .pill.good{background:rgba(51,184,168,0.15); color:var(--teal);}
  .pill.bad{background:rgba(224,102,95,0.15); color:var(--coral);}
  .pill.mid{background:rgba(217,164,65,0.15); color:var(--gold);}
  .live-dot{display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--teal); margin-right:6px; box-shadow:0 0 6px var(--teal); animation:pulse 1.6s infinite;}
  @keyframes pulse{0%{opacity:1;}50%{opacity:0.35;}100%{opacity:1;}}
  .cmp-controls select{background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:7px 10px; font-size:13px;}
  .cmp-controls label{font-size:11.5px; color:var(--muted); display:block; margin-bottom:4px;}
  .cmp-controls .cmp-field{display:flex; flex-direction:column;}
  .topn-input{background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:5px; padding:3px 7px; font-size:11.5px; width:58px; text-align:center; font-family:inherit;}
  .topn-input:focus{outline:none; border-color:var(--gold);}
  /* --- v3: heatmap click -> center detail --- */
  .hm-row{cursor:pointer;}
  .hm-row:hover td.hm-name{color:var(--gold);}
  .hm-name::after{content:' ▸'; color:var(--muted); font-size:10px;}
  tr.hm-selected td.hm-name{color:var(--gold); font-weight:700; box-shadow:inset 3px 0 0 var(--gold);}
  tr.hm-selected td.hm-name::after{content:' ▾'; color:var(--gold);}
  tr.hm-detail td{background:var(--panel-2) !important; padding:12px 14px; white-space:normal; border-bottom:2px solid var(--gold);}
  .hm-mbtns{display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px;}
  .hm-mbtn{background:transparent; border:1px solid var(--border); color:var(--muted); border-radius:6px; padding:4px 11px; font-size:11.5px; cursor:pointer; font-family:inherit;}
  .hm-mbtn:hover{color:var(--gold); border-color:var(--gold);}
  .hm-mbtn.active{background:rgba(217,164,65,0.15); color:var(--gold); border-color:var(--gold); font-weight:700;}
  .hm-chips{display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px;}
  .hm-chips:last-child{margin-bottom:0;}
  .hm-chip{background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:7px 11px; min-width:118px;}
  .hm-chip.tot{border-color:var(--teal);} .hm-chip.key{border-color:var(--gold);} .hm-chip.bad{border-color:var(--coral);}
  .hm-chip-l{font-size:10.5px; color:var(--muted);}
  .hm-chip-v{font-size:14px; font-weight:700; margin-top:2px;}
  .hm-chip-s{font-size:10.5px; color:var(--muted); margin-top:1px;}
  .cc-max{color:var(--gold); font-weight:700;}
  @media (max-width:980px){ .grid,.grid.even{grid-template-columns:1fr;} }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <h1>APK<span>&amp;</span>Infra · <span>__DIV_TITLE__</span></h1>
      <div class="sub"><span class="live-dot"></span>Exam Center Ops · Budget, Expense, Approvals &amp; Revenue (Live)</div>
    </div>
    <div class="topbar-right">
      <div class="sub" id="periodLabel"></div>
      <div class="topsel-wrap"><label>Budget basis</label>
        <select class="topsel" id="basisB"><option value="final">Final (incl. additional)</option><option value="base">Base budget only</option></select></div>
      <div class="topsel-wrap"><label>Expense basis</label>
        <select class="topsel" id="basisE"><option value="booked">Booked expense</option><option value="approved">Approved only</option></select></div>
      <div class="theme-picker">
        <button type="button" class="theme-btn" id="themeBtn"><span class="dot" id="themeDot"></span><span id="themeBtnLabel">Theme</span></button>
        <div class="theme-panel" id="themePanel"></div>
      </div>
    </div>
  </div>

  <div class="filter-bar-wrap">
    <div class="filter-bar-head">
      <h4>Filters (apply across all tabs)</h4>
      <button class="clear-btn" id="clearFiltersBtn">Clear all</button>
    </div>
    <div class="filters" id="filterBar"></div>
  </div>

  <div class="tabbar">
    <button class="tabbtn active" data-tab="overview">Overview</button>
    <button class="tabbtn" data-tab="monthly">Monthly Trend</button>
    <button class="tabbtn" data-tab="centers">Centers</button>
    <button class="tabbtn" data-tab="heads">Cost Heads</button>
    <button class="tabbtn" data-tab="revenue">Revenue &amp; Margin</button>
    <button class="tabbtn" data-tab="approvals">Approvals</button>
    <button class="tabbtn" data-tab="alerts">Over-Budget Alerts</button>
    <button class="tabbtn" data-tab="comparison">Comparison</button>
    <button class="tabbtn" data-tab="detail">All Line Items</button>
  </div>

  <!-- OVERVIEW -->
  <div id="tab-overview" class="tabpage active">
    <div class="kpis" id="kpiRow"></div>
    <div class="grid">
      <div class="card"><h3>Monthly Budget vs Expense <span class="tag">bars = ₹, line = utilization % · annual items excluded</span></h3>
        <div class="chart-box tall"><canvas id="ovMonthly"></canvas></div></div>
      <div class="card"><h3>Expense by Cost Type <span class="tag">click a slice to drill down</span></h3>
        <div class="chart-box tall"><canvas id="ovType"></canvas></div></div>
    </div>
    <div class="grid even" style="margin-top:16px;">
      <div class="card"><h3>Top Centers: Budget vs Expense <span class="tag">Top <input type="text" class="topn-input" id="topNCenter" value="10"> by budget</span></h3>
        <div class="chart-box tall"><canvas id="ovCenter"></canvas></div></div>
      <div class="card"><h3>State-wise Budget vs Expense <span class="tag">click a bar to drill down</span></h3>
        <div class="chart-box tall"><canvas id="ovState"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;">
      <h3>Center Summary <span class="tag" id="centerTableTag"></span></h3>
      <div class="scroll-table"><table id="centerTable">
        <thead><tr><th>Center</th><th>State</th><th class="num">Lines</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Variance</th><th class="num">Util %</th><th class="num">Over-Budget Lines</th><th class="num">Pending Approval</th></tr></thead>
        <tbody></tbody></table></div>
    </div>
  </div>

  <!-- MONTHLY -->
  <div id="tab-monthly" class="tabpage">
    <div class="kpis" id="monthlyKpiRow"></div>
    <div class="note" id="monthlyNote"></div>
    <div class="grid">
      <div class="card"><h3>Expense Mix by Month <span class="tag">stacked by cost type · dashed line = budget</span></h3>
        <div class="chart-box tall"><canvas id="monthlyStack"></canvas></div></div>
      <div class="card"><h3>Utilization % &amp; Over-Budget Lines <span class="tag">per month</span></h3>
        <div class="chart-box tall"><canvas id="monthlyUtil"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Monthly Table <span class="tag" id="monthlyTableTag"></span></h3>
      <div class="scroll-table"><table id="monthlyTable">
        <thead><tr><th>Month</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Variance</th><th class="num">Util %</th><th class="num">MoM Expense Δ</th><th class="num">Over-Budget Lines</th><th class="num">Pending Approval</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- CENTERS -->
  <div id="tab-centers" class="tabpage">
    <div class="kpis" id="centersKpiRow"></div>
    <div class="grid even">
      <div class="card"><h3>Utilization % by Center <span class="tag">Top <input type="text" class="topn-input" id="topNCenterTab" value="15"> by budget · label = Util % · Expense / Budget · green ≤80%, gold ≤100%, red &gt;100%</span></h3>
        <div class="chart-box tall"><canvas id="centerUtil"></canvas></div></div>
      <div class="card"><h3>Cost Mix by Center <span class="tag">expense, stacked by cost type</span></h3>
        <div class="chart-box tall"><canvas id="centerMix"></canvas></div></div>
    </div>

    <div class="card" style="margin-top:16px;"><h3>Center × Month Utilization Heatmap <span class="tag">annual items excluded · click a center to see its rent, bills and heads below the row</span></h3>
      <div class="scroll-table"><table id="heatTable" class="heat"><thead></thead><tbody></tbody></table></div>

    </div>

    <div class="card"><h3>Center Analysis <span class="tag" id="centerAnalysisTableTag"></span></h3>
      <div class="search-row"><input type="text" id="centerSearch" placeholder="Search center..."></div>
      <div class="scroll-table"><table id="centerAnalysisTable">
        <thead><tr><th>Center</th><th>State</th><th class="num">Lines</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Variance</th><th class="num">Util %</th><th class="num">Over-Budget Lines</th><th class="num">Pending Approval</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- HEADS -->
  <div id="tab-heads" class="tabpage">
    <div class="kpis" id="headsKpiRow"></div>
    <div class="card"><h3>Cost Type Summary <span class="tag">Fixed / Utilities / Operations / One-time</span></h3>
      <div class="scroll-table"><table id="typeTable">
        <thead><tr><th>Cost Type</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Variance</th><th class="num">Util %</th><th class="num">Share of Expense</th></tr></thead>
        <tbody></tbody></table></div></div>
    <div class="grid even">
      <div class="card"><h3>Budget vs Expense by Head <span class="tag">sorted by budget</span></h3>
        <div class="chart-box" id="headBEBox"><canvas id="headBE"></canvas></div></div>
      <div class="card"><h3>Variance by Head <span class="tag">red = over budget, green = within budget</span></h3>
        <div class="chart-box" id="headVarBox"><canvas id="headVar"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Cost Head Analysis <span class="tag" id="headTableTag"></span></h3>
      <div class="scroll-table"><table id="headTable">
        <thead><tr><th>Budget Head</th><th>Cost Type</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Variance</th><th class="num">Util %</th><th class="num">Over-Budget Lines</th><th>Status</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- REVENUE -->
  <div id="tab-revenue" class="tabpage">
    <div class="note" id="revNote"></div>
    <div class="kpis" id="revKpiRow"></div>
    <div class="grid even">
      <div class="card"><h3>Monthly Revenue vs Expense <span class="tag">line = margin %</span></h3>
        <div class="chart-box tall"><canvas id="revMonthly"></canvas></div></div>
      <div class="card"><h3>Center-wise Revenue vs Expense</h3>
        <div class="chart-box tall"><canvas id="revCenter"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Revenue &amp; Margin Table <span class="tag" id="revTableTag"></span></h3>
      <div class="scroll-table"><table id="revTable">
        <thead><tr><th>Center</th><th>Month</th><th class="num">Revenue</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Net Surplus</th><th class="num">Margin %</th><th class="num">Expense % of Revenue</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- APPROVALS -->
  <div id="tab-approvals" class="tabpage">
    <div class="kpis" id="apprKpiRow"></div>
    <div class="grid even">
      <div class="card"><h3>Approved vs Pending by Month</h3>
        <div class="chart-box tall"><canvas id="apprMonthly"></canvas></div></div>
      <div class="card"><h3>Pending Approval by Center <span class="tag">top 12</span></h3>
        <div class="chart-box tall"><canvas id="apprCenter"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Lines Pending Approval <span class="tag" id="apprTableTag"></span></h3>
      <div class="search-row"><input type="text" id="apprSearch" placeholder="Search center, head, month..."></div>
      <div class="scroll-table"><table id="apprTable">
        <thead><tr><th>Center</th><th>Budget Head</th><th>Month</th><th class="num">Booked Expense</th><th class="num">Approved</th><th class="num">Pending</th><th class="num">Approved %</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- ALERTS -->
  <div id="tab-alerts" class="tabpage">
    <div class="kpis" id="alertsKpiRow"></div>
    <div class="grid even">
      <div class="card"><h3>Worst Over-Budget Lines <span class="tag">click a bar to filter table</span></h3>
        <div class="chart-box tall"><canvas id="alertsChart"></canvas></div></div>
      <div class="card"><h3>Overspend by Budget Head <span class="tag">top 12</span></h3>
        <div class="chart-box tall"><canvas id="alertsHead"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Repeat Offenders <span class="tag" id="repeatTableTag">over budget in 2+ months</span></h3>
      <div class="scroll-table"><table id="repeatTable">
        <thead><tr><th>Center</th><th>Budget Head</th><th class="num">Months Over</th><th class="num">Total Overspend</th><th class="num">Avg / Month</th><th>Months</th></tr></thead>
        <tbody></tbody></table></div></div>
    <div class="card"><h3>All Over-Budget Lines <span class="tag" id="alertsTableTag"></span></h3>
      <div class="search-row"><input type="text" id="alertsSearch" placeholder="Search center, head, month..."></div>
      <div class="scroll-table"><table id="alertsTable">
        <thead><tr><th>Center</th><th>Budget Head</th><th>Month</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Overspend</th><th>Type</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- COMPARISON -->
  <div id="tab-comparison" class="tabpage">
    <div class="card"><h3>Comparison Mode <span class="tag">compare 2+ centers, heads, cost types, states or months</span></h3>
      <div class="search-row cmp-controls">
        <div class="cmp-field"><label for="cmpDimension">Compare by</label>
          <select id="cmpDimension">
            <option value="centerName">Center</option><option value="budgetHead">Budget Head</option>
            <option value="costType">Cost Type</option><option value="state">State</option><option value="month">Month</option>
          </select></div>
        <div class="cmp-field multiselect" style="min-width:260px;"><label>Groups to compare</label>
          <button type="button" class="ms-btn" id="cmpGroupsBtn">Select groups</button>
          <div class="ms-panel" id="cmpGroupsPanel">
            <input type="text" class="ms-search" id="cmpGroupsSearch" placeholder="Search...">
            <div class="ms-actions"><button type="button" id="cmpGroupsAll">Select all</button><button type="button" id="cmpGroupsClear">Clear</button></div>
            <div class="ms-list" id="cmpGroupsList"></div></div></div>
      </div></div>
    <div class="kpis" id="cmpKpiRow"></div>
    <div class="grid">
      <div class="card"><h3>Budget, Expense &amp; Variance <span class="tag">₹</span></h3><div class="chart-box tall"><canvas id="cmpChart"></canvas></div></div>
      <div class="card"><h3>Utilization % <span class="tag">per group</span></h3><div class="chart-box tall"><canvas id="cmpUtil"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Comparison Table <span class="tag" id="cmpTableTag"></span></h3>
      <div class="scroll-table"><table id="cmpTable">
        <thead><tr><th>Group</th><th class="num">Budget</th><th class="num">Expense</th><th class="num">Expense Δ% vs first</th><th class="num">Variance</th><th class="num">Util %</th></tr></thead>
        <tbody></tbody></table></div></div>

    <!-- v3: CENTER-WISE COST COMPARISON (rent / bills) -->
    <div class="card" style="margin-top:16px;"><h3>Center-wise Cost Comparison <span class="tag" id="ccTag">rent, bills — center vs center</span></h3>
      <div class="search-row cmp-controls">
        <div class="cmp-field multiselect" style="min-width:260px;"><label>Budget heads to compare</label>
          <button type="button" class="ms-btn" id="ccHeadsBtn">Select heads</button>
          <div class="ms-panel" id="ccHeadsPanel">
            <input type="text" class="ms-search" id="ccHeadsSearch" placeholder="Search head...">
            <div class="ms-actions"><button type="button" id="ccHeadsRent">Rent</button><button type="button" id="ccHeadsBills">Bills</button><button type="button" id="ccHeadsBoth">Rent+Bills</button><button type="button" id="ccHeadsAll">All</button><button type="button" id="ccHeadsClear">Clear</button></div>
            <div class="ms-list" id="ccHeadsList"></div></div></div>
        <div class="cmp-field"><label for="ccMetric">Value</label>
          <select id="ccMetric"><option value="expense">Expense (amount paid)</option><option value="budget">Budget</option></select></div>
        <div class="cmp-field"><label for="ccLayout">Chart layout</label>
          <select id="ccLayout"><option value="stacked">Stacked (total in one bar)</option><option value="grouped">Side-by-side</option></select></div>
        <div class="cmp-field"><label for="ccSort">Sort centers by</label>
          <select id="ccSort"><option value="total">Total (high → low)</option><option value="name">Center name</option></select></div>
      </div>
      <div class="note">Rent = "Building Rent" head · Bills = Electricity, DG Running Cost, Water Bill, Internet. The Month / State / Center filters above also apply here.</div>
      <div class="kpis" id="ccKpiRow"></div>
      <div class="chart-box" id="ccBox"><canvas id="ccChart"></canvas></div>
      <div style="margin-top:14px;">
        <div class="scroll-table"><table id="ccTable"><thead></thead><tbody></tbody></table></div>
      </div>
    </div>
  </div>

  <!-- DETAIL -->
  <div id="tab-detail" class="tabpage">
    <div class="kpis" id="detailKpiRow"></div>
    <div class="card"><h3>All Line Items <span class="tag" id="detailTableTag"></span></h3>
      <div class="search-row">
        <input type="text" id="detailSearch" placeholder="Search anything...">
        <label style="font-size:12px;"><input type="checkbox" id="overOnly"> Over-budget only</label>
        <label style="font-size:12px;"><input type="checkbox" id="withinOnly"> Within-budget only</label>
        <div class="multiselect" style="min-width:190px;"><label>Columns</label>
          <button type="button" class="ms-btn" id="detailColsBtn">Select columns</button>
          <div class="ms-panel" id="detailColsPanel">
            <input type="text" class="ms-search" id="detailColsSearch" placeholder="Search columns...">
            <div class="ms-actions"><button type="button" id="detailColsAll">All</button><button type="button" id="detailColsClear">Clear</button><button type="button" id="detailColsDefault">Default</button></div>
            <div class="ms-list" id="detailColsList"></div></div></div>
      </div>
      <div class="scroll-table"><table id="detailTable"><thead id="detailTableHead"></thead><tbody></tbody></table></div></div>
  </div>
</div>

<script>
const ROWS = __ROWS_JSON__;
const REV = __REV_JSON__;
const MONTH_ORDER = __MONTH_ORDER_JSON__;
const NON_MONTHLY = __NON_MONTHLY_JSON__;
const RAW_HEADERS = __RAW_HEADERS_JSON__;

// ---------------- helpers ----------------
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const sum = (rows, f) => rows.reduce((a, r) => a + (f(r) || 0), 0);
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const cut = (s, n) => String(s).length > n ? String(s).slice(0, n - 1) + '…' : String(s);
const fmtCr = v => {
  if (v === null || v === undefined || isNaN(v)) return '-';
  const abs = Math.abs(v);
  if (abs >= 1e7) return '₹' + (v/1e7).toFixed(2) + ' Cr';
  if (abs >= 1e5) return '₹' + (v/1e5).toFixed(2) + ' L';
  return '₹' + Math.round(v).toLocaleString('en-IN');
};
const fmtRs = v => '₹' + Math.round(v || 0).toLocaleString('en-IN');
const fmtNum = v => Number(v).toLocaleString('en-IN');
const fmtPct = v => (isNaN(v) ? '-' : Math.round(v) + '%');
const pill = u => `<span class="pill ${u<=80?'good':u<=100?'mid':'bad'}">${fmtPct(u)}</span>`;
function parseTopN(value){
  const v = String(value ?? '').trim().toLowerCase();
  if (v === '' || v === 'all' || v === '0') return Infinity;
  const n = parseInt(v, 10);
  return (isNaN(n) || n <= 0) ? Infinity : n;
}
function kpis(id, items){
  const row = $(id); row.innerHTML = '';
  items.forEach(it => {
    const d = document.createElement('div'); d.className = 'kpi';
    d.innerHTML = `<div class="label">${it.label}</div><div class="value">${it.value}</div>` + (it.delta ? `<div class="delta ${it.cls||''}">${it.delta}</div>` : '');
    row.appendChild(d);
  });
}
const fillBody = (id, html) => { document.querySelector('#' + id + ' tbody').innerHTML = html; };
const setTag = (id, t) => { $(id).textContent = t; };
function boxH(canvasId, h){ $(canvasId).parentElement.style.height = h + 'px'; }

// ---------------- CSV export ----------------
function csvEscapeCell(text){ const t = String(text ?? ''); return /[",\n]/.test(t) ? '"' + t.replace(/"/g,'""') + '"' : t; }
function tableToCSV(table){
  const lines = [];
  const headRow = table.querySelector('thead tr');
  if (headRow) lines.push(Array.from(headRow.children).map(th => csvEscapeCell(th.textContent.trim())).join(','));
  table.querySelectorAll('tbody tr:not(.hm-detail)').forEach(tr => lines.push(Array.from(tr.children).map(td => csvEscapeCell(td.textContent.trim())).join(',')));
  return lines.join('\r\n');
}
function downloadCSV(filename, csv){
  const blob = new Blob(['\ufeff' + csv], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
}
const EXPORTABLE_TABLES = [
  ['centerTable','center-summary'],['monthlyTable','monthly-trend'],['centerAnalysisTable','center-analysis'],['heatTable','center-month-heatmap'],
  ['ccTable','center-cost-comparison'],
  ['typeTable','cost-type-summary'],['headTable','cost-head-analysis'],['revTable','revenue-margin'],['apprTable','pending-approvals'],
  ['repeatTable','repeat-offenders'],['alertsTable','over-budget-alerts'],['cmpTable','comparison'],['detailTable','all-line-items']
];
function addExportButtons(){
  EXPORTABLE_TABLES.forEach(([id, name]) => {
    const table = $(id); if (!table) return;
    const wrapper = table.closest('.scroll-table');
    if (!wrapper || wrapper.parentNode.querySelector('.export-btn[data-for="'+id+'"]')) return;
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'export-btn'; btn.dataset.for = id; btn.textContent = '⬇ Export CSV (Excel)';
    btn.addEventListener('click', () => downloadCSV(name + '-' + new Date().toISOString().slice(0,10) + '.csv', tableToCSV(table)));
    wrapper.parentNode.insertBefore(btn, wrapper);
  });
}

// ---------------- chart defaults ----------------
let currentDatalabelColor = '#e7ecf5';
Chart.defaults.color = '#8ea0c2';
Chart.defaults.font.family = "'Segoe UI', Arial, sans-serif";
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.register(ChartDataLabels);
Chart.defaults.set('plugins.datalabels', { display: false });
const COLORS = { gold:'#d9a441', teal:'#33b8a8', coral:'#e0665f', violet:'#8b7ee8', blue:'#4f8bd0' };
const PALETTE = ['#d9a441','#33b8a8','#e0665f','#8b7ee8','#4f8bd0','#5cc96a','#e0a8d0','#e0d05f','#6fa8e0','#c98b5c','#8adfd4','#b98ae0'];
const TYPES = ['Fixed','Utilities','Operations','One-time / Capex'];
const TYPE_COL = {'Fixed':'#4f8bd0','Utilities':'#33b8a8','Operations':'#d9a441','One-time / Capex':'#8b7ee8'};
const BAR_B = 'rgba(79,139,208,0.55)', BAR_E = 'rgba(217,164,65,0.75)';
const charts = {};
function mk(id, cfg){ if (charts[id]) charts[id].destroy(); charts[id] = new Chart($(id), cfg); return charts[id]; }
const dlab = (o = {}) => ({display:true, clip:false, color:currentDatalabelColor, font:{size:9,weight:'600'}, anchor:'end', align:'right', formatter:v=>fmtCr(v), ...o});
const utilCol = u => u <= 80 ? COLORS.teal : (u <= 100 ? COLORS.gold : COLORS.coral);

// ---------------- basis + metrics ----------------
let BASIS_B = 'final', BASIS_E = 'booked';
const B = r => BASIS_B === 'final' ? r.finalBudget : r.budget;
const E = r => BASIS_E === 'approved' ? r.approved : r.expense;
const isOver = r => E(r) > B(r) + 0.5;
const isUnb = r => B(r) <= 0 && E(r) > 0.5;
const overAmt = r => E(r) - B(r);
const isMonthly = r => !NON_MONTHLY.includes(r.month);
const MORD = new Map(MONTH_ORDER.map((m,i) => [m,i]));
const ord = k => MORD.has(k) ? MORD.get(k) : 999;
const byMonth = (a,b) => ord(a.key) - ord(b.key);
const sortBudget = (a,b) => b.Budget - a.Budget;
const by = f => r => r[f];
const STATE_OF = {}, HEAD_TYPE = {};
ROWS.forEach(r => { STATE_OF[r.centerName] = r.state; HEAD_TYPE[r.budgetHead] = r.costType; });

// rent / bill head groups (names come from classify_head in Python)
const RENT_HEADS = ['Building Rent'];
const BILL_HEADS = ['Electricity','DG Running Cost','Water Bill','Internet'];

function agg(rows, keyFn){
  const m = new Map();
  rows.forEach(r => {
    const k = keyFn(r) || '(blank)';
    let g = m.get(k);
    if (!g){ g = {key:k, Budget:0, Expense:0, Approved:0, Pending:0, Count:0, Over:0, OverAmt:0}; m.set(k, g); }
    g.Budget += B(r); g.Expense += E(r); g.Approved += r.approved; g.Pending += r.pending; g.Count++;
    if (isOver(r)){ g.Over++; g.OverAmt += overAmt(r); }
  });
  return [...m.values()].map(g => ({...g, Variance: g.Budget - g.Expense, UtilPct: g.Budget > 0 ? g.Expense / g.Budget * 100 : 0}));
}

// ---------------- filters ----------------
const FILTER_DEFS = [
  {key:'state', label:'State'},
  {key:'centerName', label:'Center'},
  {key:'month', label:'Month', order: MONTH_ORDER},
  {key:'costType', label:'Cost Type'},
  {key:'budgetHead', label:'Budget Head'},
];
const activeFilters = {};
FILTER_DEFS.forEach(f => activeFilters[f.key] = new Set());
function uniqueValues(field, order){
  const vals = Array.from(new Set(ROWS.map(r => r[field]).filter(v => v !== null && v !== undefined && v !== '')));
  if (order && order.length) vals.sort((a,b) => ord(a) - ord(b)); else vals.sort();
  return vals;
}
function triggerFilterChange(){ const a = document.querySelector('.tabpage.active'); renderTab(a ? a.id : 'tab-overview'); }
function renderTab(t){
  if (t === 'tab-overview') renderOverview();
  else if (t === 'tab-monthly') renderMonthly();
  else if (t === 'tab-centers') renderCenters();
  else if (t === 'tab-heads') renderHeads();
  else if (t === 'tab-revenue') renderRevenue();
  else if (t === 'tab-approvals') renderApprovals();
  else if (t === 'tab-alerts') renderAlerts();
  else if (t === 'tab-comparison') populateCmpGroups();
  else if (t === 'tab-detail') renderDetail();
}
function buildFilterBar(){
  const bar = $('filterBar'); bar.innerHTML = '';
  FILTER_DEFS.forEach(f => {
    const values = uniqueValues(f.key, f.order);
    const wrap = document.createElement('div'); wrap.className = 'multiselect';
    wrap.innerHTML = `<label>${f.label}</label><button type="button" class="ms-btn" id="msbtn_${f.key}">All</button>
      <div class="ms-panel" id="mspanel_${f.key}"><input type="text" class="ms-search" placeholder="Search...">
      <div class="ms-actions"><button type="button" class="ms-all">Select all</button><button type="button" class="ms-clear">Clear</button></div><div class="ms-list"></div></div>`;
    bar.appendChild(wrap);
    const listEl = wrap.querySelector('.ms-list'), btn = wrap.querySelector('.ms-btn'), panel = wrap.querySelector('.ms-panel');
    values.forEach(v => {
      const row = document.createElement('label'); row.className = 'ms-option';
      const cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = v;
      const span = document.createElement('span'); span.textContent = v; span.title = v;
      row.appendChild(cb); row.appendChild(span); listEl.appendChild(row);
    });
    btn.addEventListener('click', e => { e.stopPropagation(); document.querySelectorAll('.ms-panel.open').forEach(p => { if (p !== panel) p.classList.remove('open'); }); panel.classList.toggle('open'); });
    panel.addEventListener('click', e => e.stopPropagation());
    wrap.querySelector('.ms-search').addEventListener('input', e => {
      const term = e.target.value.toLowerCase();
      listEl.querySelectorAll('.ms-option').forEach(o => { o.style.display = o.textContent.toLowerCase().includes(term) ? '' : 'none'; });
    });
    wrap.querySelector('.ms-all').addEventListener('click', () => { listEl.querySelectorAll('.ms-option').forEach(o => { if (o.style.display !== 'none') o.querySelector('input').checked = true; }); applyMultiSelect(f.key, listEl, btn); });
    wrap.querySelector('.ms-clear').addEventListener('click', () => { listEl.querySelectorAll('input').forEach(c => c.checked = false); applyMultiSelect(f.key, listEl, btn); });
    listEl.addEventListener('change', () => applyMultiSelect(f.key, listEl, btn));
  });
}
function applyMultiSelect(key, listEl, btn){
  const checked = Array.from(listEl.querySelectorAll('input:checked')).map(c => c.value);
  activeFilters[key] = new Set(checked);
  btn.textContent = checked.length === 0 ? 'All' : (checked.length === 1 ? checked[0] : checked.length + ' selected');
  btn.classList.toggle('active', checked.length > 0);
  triggerFilterChange();
}
document.addEventListener('click', () => {
  document.querySelectorAll('.ms-panel.open').forEach(p => p.classList.remove('open'));
  document.querySelectorAll('.theme-panel.open').forEach(p => p.classList.remove('open'));
});
$('clearFiltersBtn').addEventListener('click', () => {
  FILTER_DEFS.forEach(f => {
    activeFilters[f.key] = new Set();
    const p = $('mspanel_' + f.key); if (p) p.querySelectorAll('input[type=checkbox]').forEach(c => c.checked = false);
    const b = $('msbtn_' + f.key); if (b){ b.textContent = 'All'; b.classList.remove('active'); }
  });
  triggerFilterChange();
});
function rowMatches(row, ignore = []){
  return FILTER_DEFS.every(f => {
    if (ignore.includes(f.key)) return true;
    const s = activeFilters[f.key];
    return !s || s.size === 0 || s.has(String(row[f.key] ?? ''));
  });
}
const getFilteredRows = () => ROWS.filter(r => rowMatches(r));
function drillFilter(key, value){
  if (value === undefined || value === null || value === '') return;
  activeFilters[key] = new Set([value]);
  const listEl = document.querySelector('#mspanel_' + key + ' .ms-list'), btn = $('msbtn_' + key);
  if (listEl) listEl.querySelectorAll('input').forEach(c => { c.checked = (c.value === value); });
  if (btn){ btn.textContent = value; btn.classList.add('active'); }
  document.querySelector('.tabbtn[data-tab="detail"]').click();
}
$('basisB').addEventListener('change', e => { BASIS_B = e.target.value; triggerFilterChange(); });
$('basisE').addEventListener('change', e => { BASIS_E = e.target.value; triggerFilterChange(); });

// ---------------- reusable charts ----------------
function beChart(id, a, horizontal, drill){
  const labels = a.map(x => x.key);
  mk(id, {type:'bar', data:{labels: a.map(x => cut(x.key, horizontal ? 30 : 14)), datasets:[
      {label:'Budget', data:a.map(x => x.Budget), backgroundColor:BAR_B, borderRadius:5},
      {label:'Expense', data:a.map(x => x.Expense), backgroundColor:BAR_E, borderRadius:5}]},
    options:{indexAxis: horizontal ? 'y' : 'x', responsive:true, maintainAspectRatio:false, layout:{padding: horizontal ? {right:62} : {top:18}},
      plugins:{legend:{position:'bottom'}, datalabels: dlab(horizontal ? {} : {align:'top'}), tooltip:{callbacks:{title: it => labels[it[0].dataIndex], label: c => c.dataset.label + ': ' + fmtRs(c.parsed[horizontal ? 'x' : 'y'])}}},
      onClick:(evt, els) => { if (els.length && drill) drillFilter(drill, labels[els[0].index]); }}});
}
function monthlyCombo(id, rows){
  const a = agg(rows.filter(isMonthly), by('month')).sort(byMonth);
  const labels = a.map(x => x.key);
  mk(id, {data:{labels, datasets:[
      {type:'bar', label:'Budget', data:a.map(x => x.Budget), backgroundColor:BAR_B, borderRadius:5, yAxisID:'y', datalabels:dlab({align:'top'})},
      {type:'bar', label:'Expense', data:a.map(x => x.Expense), backgroundColor:BAR_E, borderRadius:5, yAxisID:'y', datalabels:dlab({align:'top'})},
      {type:'line', label:'Utilization %', data:a.map(x => x.UtilPct), borderColor:COLORS.teal, backgroundColor:COLORS.teal, tension:0.35, yAxisID:'y1', pointRadius:4, datalabels:dlab({align:'top', color:COLORS.teal, formatter:v => Math.round(v) + '%'})}]},
    options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false}, layout:{padding:{top:20}},
      scales:{y:{position:'left', title:{display:true, text:'₹'}}, y1:{position:'right', grid:{display:false}, title:{display:true, text:'Utilization %'}, min:0}},
      plugins:{legend:{position:'bottom'}},
      onClick:(evt, els) => { if (els.length) drillFilter('month', labels[els[0].index]); }}});
}
function centerRow(c){
  return `<tr><td>${esc(c.key)}</td><td>${esc(STATE_OF[c.key] || '')}</td><td class="num">${c.Count}</td><td class="num">${fmtCr(c.Budget)}</td><td class="num">${fmtCr(c.Expense)}</td><td class="num">${fmtCr(c.Variance)}</td><td class="num">${pill(c.UtilPct)}</td><td class="num">${c.Over}</td><td class="num">${fmtCr(c.Pending)}</td></tr>`;
}

// ---------------- OVERVIEW ----------------
let topNCenter = 10;
function renderOverview(){
  const rows = getFilteredRows();
  const tb = sum(rows, B), te = sum(rows, E), tp = sum(rows, r => r.pending), over = rows.filter(isOver).length, util = tb > 0 ? te / tb * 100 : 0;
  kpis('kpiRow', [
    {label:'Total Budget', value:fmtCr(tb), delta: BASIS_B === 'final' ? 'final (incl. additional)' : 'base budget', cls:'muted'},
    {label:'Total Expense', value:fmtCr(te), delta: BASIS_E === 'approved' ? 'approved only' : 'booked', cls:'muted'},
    {label:'Net Variance', value:fmtCr(tb - te), delta: tb >= te ? 'Saving' : 'Over Budget', cls: tb >= te ? 'up' : 'down'},
    {label:'Utilization %', value:fmtPct(util), delta: util > 100 ? 'over-utilized' : 'on track', cls: util > 100 ? 'down' : 'up'},
    {label:'Pending Approval', value:fmtCr(tp), delta:'booked, not yet approved', cls: tp > 0 ? 'down' : 'up'},
    {label:'Over-Budget Lines', value:fmtNum(over) + ' / ' + fmtNum(rows.length), cls: over > 0 ? 'down' : 'up'},
  ]);
  monthlyCombo('ovMonthly', rows);
  const t = agg(rows, by('costType')).sort((a,b) => b.Expense - a.Expense);
  mk('ovType', {type:'doughnut', data:{labels:t.map(x => x.key), datasets:[{data:t.map(x => x.Expense), backgroundColor:t.map(x => TYPE_COL[x.key] || COLORS.gold), borderWidth:2, borderColor:cssv('--panel')}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'bottom'}, datalabels:dlab({anchor:'center', align:'center', font:{size:10,weight:'700'}})},
      onClick:(evt, els) => { if (els.length) drillFilter('costType', t[els[0].index].key); }}});
  const c = agg(rows, by('centerName')).sort(sortBudget);
  const n = topNCenter === Infinity ? c.length : topNCenter;
  boxH('ovCenter', Math.max(380, Math.min(n, c.length) * 34 + 60));
  beChart('ovCenter', c.slice(0, n), true, 'centerName');
  beChart('ovState', agg(rows, by('state')).sort(sortBudget), false, 'state');
  fillBody('centerTable', c.slice(0, n).map(centerRow).join(''));
  setTag('centerTableTag', Math.min(n, c.length) + ' of ' + c.length + ' centers');
}
const onTopN = e => { topNCenter = parseTopN(e.target.value); renderOverview(); };
$('topNCenter').addEventListener('input', onTopN); $('topNCenter').addEventListener('change', onTopN);

// ---------------- MONTHLY ----------------
function renderMonthly(){
  const rows = getFilteredRows(), m = rows.filter(isMonthly), ann = rows.filter(r => !isMonthly(r));
  const a = agg(m, by('month')).sort(byMonth);
  const te = sum(a, x => x.Expense), tb = sum(a, x => x.Budget);
  const peak = [...a].sort((x,y) => y.Expense - x.Expense)[0];
  const ub = [...a].filter(x => x.Budget > 0);
  const lo = [...ub].sort((x,y) => x.UtilPct - y.UtilPct)[0], hi = [...ub].sort((x,y) => y.UtilPct - x.UtilPct)[0];
  kpis('monthlyKpiRow', [
    {label:'Total Budget', value:fmtCr(tb)}, {label:'Total Expense', value:fmtCr(te)},
    {label:'Avg Monthly Expense', value: a.length ? fmtCr(te / a.length) : '-'},
    {label:'Peak Expense Month', value: peak ? peak.key + ' (' + fmtCr(peak.Expense) + ')' : '-'},
    {label:'Lowest Utilization', value: lo ? lo.key + ' (' + fmtPct(lo.UtilPct) + ')' : '-'},
    {label:'Highest Utilization', value: hi ? hi.key + ' (' + fmtPct(hi.UtilPct) + ')' : '-'},
  ]);
  $('monthlyNote').textContent = ann.length ? `Annual / non-monthly items (${[...new Set(ann.map(r => r.month))].join(', ')}) are not included in the monthly view — Budget ${fmtCr(sum(ann, B))}, Expense ${fmtCr(sum(ann, E))}.` : '';
  const labels = a.map(x => x.key);
  const tm = new Map(); m.forEach(r => { const k = r.month + '|' + r.costType; tm.set(k, (tm.get(k) || 0) + E(r)); });
  mk('monthlyStack', {data:{labels, datasets:[
      ...TYPES.map(t => ({type:'bar', label:t, data:labels.map(l => tm.get(l + '|' + t) || 0), backgroundColor:TYPE_COL[t], stack:'e'})),
      {type:'line', label:'Budget', data:a.map(x => x.Budget), borderColor:cssv('--text'), backgroundColor:cssv('--text'), borderDash:[6,4], pointRadius:3, tension:0.2, datalabels:dlab({align:'top', formatter:v => fmtCr(v)})}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, interaction:{mode:'index', intersect:false},
      scales:{x:{stacked:true}, y:{stacked:true, title:{display:true, text:'₹'}}}, plugins:{legend:{position:'bottom'}},
      onClick:(evt, els) => { if (els.length) drillFilter('month', labels[els[0].index]); }}});
  mk('monthlyUtil', {data:{labels, datasets:[
      {type:'bar', label:'Over-Budget Lines', data:a.map(x => x.Over), backgroundColor:'rgba(224,102,95,0.65)', borderRadius:5, yAxisID:'y', datalabels:dlab({align:'top', formatter:v => v})},
      {type:'line', label:'Utilization %', data:a.map(x => x.UtilPct), borderColor:COLORS.teal, backgroundColor:COLORS.teal, tension:0.35, yAxisID:'y1', pointRadius:4, datalabels:dlab({align:'top', color:COLORS.teal, formatter:v => Math.round(v) + '%'})}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, interaction:{mode:'index', intersect:false},
      scales:{y:{position:'left', title:{display:true, text:'Lines over budget'}, beginAtZero:true}, y1:{position:'right', grid:{display:false}, min:0, title:{display:true, text:'Utilization %'}}},
      plugins:{legend:{position:'bottom'}}}});
  fillBody('monthlyTable', a.map((x, i) => {
    const p = i > 0 ? a[i-1] : null, d = p && p.Expense ? (x.Expense - p.Expense) / Math.abs(p.Expense) * 100 : null;
    const dh = d === null ? '-' : `<span class="${d <= 0 ? 'up' : 'down'}">${d >= 0 ? '+' : ''}${Math.round(d)}%</span>`;
    return `<tr><td>${esc(x.key)}</td><td class="num">${fmtCr(x.Budget)}</td><td class="num">${fmtCr(x.Expense)}</td><td class="num">${fmtCr(x.Variance)}</td><td class="num">${pill(x.UtilPct)}</td><td class="num">${dh}</td><td class="num">${x.Over}</td><td class="num">${fmtCr(x.Pending)}</td></tr>`;
  }).join(''));
  setTag('monthlyTableTag', a.length + ' months');
}

// ---------------- CENTERS ----------------
let centerSearchTerm = '', topNCenterTab = 15;
let openCenters = new Map();   // centers expanded in the heatmap (center -> selected month)
function renderCenters(){
  const rows = getFilteredRows();
  const all = agg(rows, by('centerName')).sort(sortBudget);
  const tb = sum(all, x => x.Budget), te = sum(all, x => x.Expense);
  kpis('centersKpiRow', [
    {label:'Total Centers', value:fmtNum(all.length)}, {label:'Total Budget', value:fmtCr(tb)}, {label:'Total Expense', value:fmtCr(te)},
    {label:'Blended Utilization', value:fmtPct(tb > 0 ? te / tb * 100 : 0)},
    {label:'Centers Over Budget', value:fmtNum(all.filter(x => x.Expense > x.Budget).length) + ' / ' + fmtNum(all.length), cls:'down'},
  ]);
  const n = topNCenterTab === Infinity ? all.length : topNCenterTab;
  const top = all.slice(0, n);
  boxH('centerUtil', Math.max(380, top.length * 28 + 60)); boxH('centerMix', Math.max(380, top.length * 28 + 60));
  const u = [...top].sort((a,b) => b.UtilPct - a.UtilPct);
  // v3: label shows Util % along with Expense / Budget
  mk('centerUtil', {type:'bar', data:{labels:u.map(x => cut(x.key, 30)), datasets:[{label:'Utilization %', data:u.map(x => x.UtilPct), backgroundColor:u.map(x => utilCol(x.UtilPct)), borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:200}},
      plugins:{legend:{display:false},
        datalabels:dlab({formatter:(v, ctx) => Math.round(v) + '%  ·  ' + fmtCr(u[ctx.dataIndex].Expense) + ' / ' + fmtCr(u[ctx.dataIndex].Budget)}),
        tooltip:{callbacks:{title:it => u[it[0].dataIndex].key, label:c => 'Utilization: ' + Math.round(c.parsed.x) + '%', afterLabel:c => ['Budget: ' + fmtRs(u[c.dataIndex].Budget), 'Expense: ' + fmtRs(u[c.dataIndex].Expense), 'Variance: ' + fmtRs(u[c.dataIndex].Variance)]}}},
      onClick:(evt, els) => { if (els.length) drillFilter('centerName', u[els[0].index].key); }}});
  const cm = new Map(); rows.forEach(r => { const k = r.centerName + '|' + r.costType; cm.set(k, (cm.get(k) || 0) + E(r)); });
  mk('centerMix', {type:'bar', data:{labels:top.map(x => cut(x.key, 30)), datasets:TYPES.map(t => ({label:t, data:top.map(x => cm.get(x.key + '|' + t) || 0), backgroundColor:TYPE_COL[t], stack:'e'}))},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, scales:{x:{stacked:true}, y:{stacked:true}},
      plugins:{legend:{position:'bottom'}, tooltip:{callbacks:{title:it => top[it[0].dataIndex].key, label:c => c.dataset.label + ': ' + fmtRs(c.parsed.x)}}},
      onClick:(evt, els) => { if (els.length) drillFilter('centerName', top[els[0].index].key); }}});
  renderHeat(rows, all);
  renderCenterAnalysis(all);
}
function renderHeat(rows, all){
  const mr = rows.filter(isMonthly);
  const months = [...new Set(mr.map(r => r.month))].sort((a,b) => ord(a) - ord(b));
  const cm = new Map(); mr.forEach(r => { const k = r.centerName + '|' + r.month; let g = cm.get(k); if (!g){ g = {b:0,e:0}; cm.set(k, g); } g.b += B(r); g.e += E(r); });
  const bg = u => u <= 80 ? 'rgba(51,184,168,0.18)' : (u <= 100 ? 'rgba(217,164,65,0.25)' : 'rgba(224,102,95,0.38)');
  document.querySelector('#heatTable thead').innerHTML = '<tr><th>Center</th>' + months.map(m => `<th class="num" style="text-align:center">${esc(m)}</th>`).join('') + '<th class="num" style="text-align:center">Overall</th></tr>';
  fillBody('heatTable', all.map(c => {
    const cells = months.map(m => {
      const g = cm.get(c.key + '|' + m);
      if (!g || g.b <= 0) return `<td class="hc muted">${g && g.e > 0 ? fmtCr(g.e) : '-'}</td>`;
      const u = g.e / g.b * 100;
      return `<td class="hc" style="background:${bg(u)}" title="${fmtRs(g.e)} of ${fmtRs(g.b)}">${fmtPct(u)}</td>`;
    }).join('');
    return `<tr class="hm-row${openCenters.has(c.key) ? ' hm-selected' : ''}" data-center="${esc(c.key)}"><td class="hm-name" title="Click to see this center's details below">${esc(c.key)}</td>${cells}<td class="hc" style="background:${bg(c.UtilPct)};font-weight:700">${fmtPct(c.UtilPct)}</td></tr>`
      + (openCenters.has(c.key) ? `<tr class="hm-detail" data-center="${esc(c.key)}"><td colspan="${months.length + 2}">${centerDetailHtml(c.key, openCenters.get(c.key))}</td></tr>` : '');
  }).join(''));
}

// ---- v3: click a center in the heatmap -> rent / bills / heads shown below that row (All or a single month) ----
function centerDetailHtml(name, month){
  month = month || 'All';
  const all = getFilteredRows().filter(r => r.centerName === name);
  if (!all.length) return '<span class="muted">No data for this center under the current filters.</span>';
  const mlist = [...new Set(all.map(r => r.month))].sort((a,b) => ord(a) - ord(b));
  if (month !== 'All' && !mlist.includes(month)) month = 'All';
  const rows = month === 'All' ? all : all.filter(r => r.month === month);
  const heads = agg(rows, by('budgetHead')).sort((a,b) => b.Expense - a.Expense);
  const part = list => { const x = rows.filter(r => list.includes(r.budgetHead)); return [sum(x, E), sum(x, B)]; };
  const [rentE, rentB] = part(RENT_HEADS), [billE, billB] = part(BILL_HEADS);
  const chip = (label, e, b, cls) => `<div class="hm-chip ${cls || ''}"><div class="hm-chip-l">${esc(label)}</div><div class="hm-chip-v">${fmtCr(e)}</div><div class="hm-chip-s">Budget ${fmtCr(b)}</div></div>`;
  const btns = '<div class="hm-mbtns">' + ['All', ...mlist].map(m => `<button type="button" class="hm-mbtn${m === month ? ' active' : ''}" data-month="${esc(m)}">${esc(m)}</button>`).join('') + '</div>';
  return btns
    + '<div class="hm-chips">'
    + chip('Total Expense' + (month === 'All' ? '' : ' · ' + month), sum(rows, E), sum(rows, B), 'tot')
    + chip('Rent', rentE, rentB, 'key')
    + chip('Bills (Elec + DG + Water + Internet)', billE, billB, 'key')
    + '</div><div class="hm-chips">'
    + heads.map(x => chip(x.key, x.Expense, x.Budget, x.Expense > x.Budget + 0.5 ? 'bad' : '')).join('')
    + '</div>';
}
$('heatTable').addEventListener('click', e => {
  const mb = e.target.closest('button.hm-mbtn');
  if (mb){
    const dtr = mb.closest('tr.hm-detail'); if (!dtr) return;
    const name = dtr.dataset.center;
    openCenters.set(name, mb.dataset.month);
    dtr.firstElementChild.innerHTML = centerDetailHtml(name, mb.dataset.month);
    return;
  }
  const tr = e.target.closest('tr.hm-row'); if (!tr) return;
  const name = tr.dataset.center, nxt = tr.nextElementSibling;
  if (openCenters.has(name)){
    openCenters.delete(name); tr.classList.remove('hm-selected');
    if (nxt && nxt.classList.contains('hm-detail')) nxt.remove();
  } else {
    openCenters.set(name, 'All'); tr.classList.add('hm-selected');
    const d = document.createElement('tr'); d.className = 'hm-detail'; d.dataset.center = name;
    const td = document.createElement('td'); td.colSpan = tr.children.length; td.innerHTML = centerDetailHtml(name, 'All');
    d.appendChild(td); tr.after(d);
  }
});

// ---- v3: center-wise cost comparison (rent / bills / any head) ----
let ccSelected = new Set();
function updateCcBtn(){
  const n = ccSelected.size, b = $('ccHeadsBtn');
  b.textContent = n === 0 ? 'Select heads' : (n === 1 ? [...ccSelected][0] : n + ' heads selected');
  b.classList.toggle('active', n > 0);
}
function buildCcHeadsPanel(){
  const all = uniqueValues('budgetHead');
  const def = all.filter(h => RENT_HEADS.includes(h) || BILL_HEADS.includes(h));
  ccSelected = new Set(def.length ? def : all.slice(0, 3));
  const l = $('ccHeadsList'); l.innerHTML = '';
  all.forEach(h => {
    const row = document.createElement('label'); row.className = 'ms-option';
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = h; cb.checked = ccSelected.has(h);
    const sp = document.createElement('span'); sp.textContent = h; sp.title = h;
    row.appendChild(cb); row.appendChild(sp); l.appendChild(row);
  });
  updateCcBtn();
}
const readCc = () => { ccSelected = new Set(Array.from(document.querySelectorAll('#ccHeadsList input:checked')).map(c => c.value)); updateCcBtn(); renderCostCompare(); };
const setCc = list => { document.querySelectorAll('#ccHeadsList input').forEach(c => { c.checked = list.includes(c.value); }); readCc(); };
$('ccHeadsBtn').addEventListener('click', e => { e.stopPropagation(); document.querySelectorAll('.ms-panel.open').forEach(p => { if (p.id !== 'ccHeadsPanel') p.classList.remove('open'); }); $('ccHeadsPanel').classList.toggle('open'); });
$('ccHeadsPanel').addEventListener('click', e => e.stopPropagation());
$('ccHeadsSearch').addEventListener('input', e => { const t = e.target.value.toLowerCase(); document.querySelectorAll('#ccHeadsList .ms-option').forEach(o => { o.style.display = o.textContent.toLowerCase().includes(t) ? '' : 'none'; }); });
$('ccHeadsRent').addEventListener('click', () => setCc(RENT_HEADS));
$('ccHeadsBills').addEventListener('click', () => setCc(BILL_HEADS));
$('ccHeadsBoth').addEventListener('click', () => setCc([...RENT_HEADS, ...BILL_HEADS]));
$('ccHeadsAll').addEventListener('click', () => { document.querySelectorAll('#ccHeadsList .ms-option').forEach(o => { if (o.style.display !== 'none') o.querySelector('input').checked = true; }); readCc(); });
$('ccHeadsClear').addEventListener('click', () => { document.querySelectorAll('#ccHeadsList input').forEach(c => c.checked = false); readCc(); });
$('ccHeadsList').addEventListener('change', readCc);
['ccMetric','ccLayout','ccSort'].forEach(id => $(id).addEventListener('change', renderCostCompare));

function renderCostCompare(){
  const metric = $('ccMetric').value, st = $('ccLayout').value === 'stacked', sortBy = $('ccSort').value;
  const val = r => metric === 'budget' ? B(r) : E(r);
  const mLabel = metric === 'budget' ? 'Budget' : 'Expense';
  const all = getFilteredRows(), cm = new Map(), ht = new Map();
  all.forEach(r => { if (!cm.has(r.centerName)) cm.set(r.centerName, {}); });
  all.filter(r => ccSelected.has(r.budgetHead)).forEach(r => {
    const g = cm.get(r.centerName), v = val(r);
    g[r.budgetHead] = (g[r.budgetHead] || 0) + v;
    ht.set(r.budgetHead, (ht.get(r.budgetHead) || 0) + v);
  });
  const heads = [...ccSelected].sort((a,b) => (ht.get(b) || 0) - (ht.get(a) || 0));
  const cs = [...cm.entries()].map(([key, g]) => ({key, g, total: heads.reduce((s, h) => s + (g[h] || 0), 0)}));
  if (sortBy === 'name') cs.sort((a,b) => a.key.localeCompare(b.key)); else cs.sort((a,b) => b.total - a.total);

  if (!heads.length || !cs.length){
    $('ccKpiRow').innerHTML = '';
    if (charts.ccChart){ charts.ccChart.destroy(); delete charts.ccChart; }
    $('ccTable').querySelector('thead').innerHTML = '';
    fillBody('ccTable', '<tr><td class="muted">Select at least one budget head above.</td></tr>');
    setTag('ccTag', 'rent, bills — center vs center');
    return;
  }
  const grand = sum(cs, c => c.total);
  const withVal = cs.filter(c => c.total > 0);
  const hi = [...cs].sort((a,b) => b.total - a.total)[0];
  const lo = [...withVal].sort((a,b) => a.total - b.total)[0];
  kpis('ccKpiRow', [
    {label:'Total ' + mLabel, value:fmtCr(grand), delta: heads.length + ' head(s) selected', cls:'muted'},
    {label:'Centers', value:fmtNum(cs.length)},
    {label:'Avg per Center', value:fmtCr(grand / cs.length)},
    {label:'Highest', value:cut(hi.key, 26), delta:fmtCr(hi.total), cls:'down'},
    {label:'Lowest (non-zero)', value: lo ? cut(lo.key, 26) : '-', delta: lo ? fmtCr(lo.total) : '', cls:'up'},
  ]);
  setTag('ccTag', mLabel + ' · ' + cs.length + ' centers · ' + heads.length + ' heads · click a bar to drill down');

  const h = st ? cs.length * 30 + 90 : cs.length * (heads.length * 15 + 16) + 90;
  boxH('ccChart', Math.max(380, h));
  const thr = Math.max(...cs.map(c => c.total)) * 0.08;
  mk('ccChart', {type:'bar', data:{
      labels: cs.map(c => cut(c.key, 30) + '  (' + fmtCr(c.total) + ')'),
      datasets: heads.map((hd, i) => ({label:hd, data:cs.map(c => c.g[hd] || 0), backgroundColor:PALETTE[i % PALETTE.length], borderRadius:3, ...(st ? {stack:'s'} : {})}))},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right: st ? 10 : 62}},
      scales:{x:{stacked:st, title:{display:true, text:'₹ ' + mLabel}}, y:{stacked:st, ticks:{autoSkip:false}}},
      plugins:{legend:{position:'bottom'},
        datalabels: st ? dlab({anchor:'center', align:'center', display:c => c.dataset.data[c.dataIndex] > thr, formatter:v => fmtCr(v)})
                       : dlab({display:c => c.dataset.data[c.dataIndex] > 0, formatter:v => fmtCr(v)}),
        tooltip:{callbacks:{title:it => cs[it[0].dataIndex].key, label:c => c.dataset.label + ': ' + fmtRs(c.parsed.x), footer:it => st ? 'Total: ' + fmtRs(sum(it, x => x.parsed.x)) : ''}}},
      onClick:(evt, els) => { if (els.length) drillFilter('centerName', cs[els[0].index].key); }}});

  const mx = {}; heads.forEach(hd => { mx[hd] = Math.max(...cs.map(c => c.g[hd] || 0)); });
  $('ccTable').querySelector('thead').innerHTML = '<tr><th>Center</th>' + heads.map(hd => `<th class="num">${esc(hd)}</th>`).join('') + '<th class="num">Total</th><th class="num">Share %</th></tr>';
  fillBody('ccTable',
    cs.map(c => `<tr><td>${esc(c.key)}</td>` + heads.map(hd => {
      const v = c.g[hd] || 0;
      return `<td class="num${v > 0 && v === mx[hd] ? ' cc-max' : ''}">${v > 0 ? fmtCr(v) : '-'}</td>`;
    }).join('') + `<td class="num"><b>${fmtCr(c.total)}</b></td><td class="num">${grand > 0 ? fmtPct(c.total / grand * 100) : '-'}</td></tr>`).join('')
    + `<tr style="font-weight:700"><td>Total</td>` + heads.map(hd => `<td class="num">${fmtCr(ht.get(hd) || 0)}</td>`).join('') + `<td class="num">${fmtCr(grand)}</td><td class="num">100%</td></tr>`);
}

function renderCenterAnalysis(all){
  const term = centerSearchTerm.trim().toLowerCase();
  const f = term ? all.filter(c => c.key.toLowerCase().includes(term) || (STATE_OF[c.key] || '').toLowerCase().includes(term)) : all;
  fillBody('centerAnalysisTable', f.map(centerRow).join(''));
  setTag('centerAnalysisTableTag', f.length + ' of ' + all.length + ' centers');
}
$('centerSearch').addEventListener('input', e => { centerSearchTerm = e.target.value; renderCenterAnalysis(agg(getFilteredRows(), by('centerName')).sort(sortBudget)); });
const onTopNTab = e => { topNCenterTab = parseTopN(e.target.value); renderCenters(); };
$('topNCenterTab').addEventListener('input', onTopNTab); $('topNCenterTab').addEventListener('change', onTopNTab);

// ---------------- COST HEADS ----------------
function renderHeads(){
  const rows = getFilteredRows();
  const a = agg(rows, by('budgetHead')).sort(sortBudget);
  const tb = sum(a, x => x.Budget), te = sum(a, x => x.Expense);
  const worst = [...a].sort((x,y) => x.Variance - y.Variance)[0], big = [...a].sort((x,y) => y.Expense - x.Expense)[0];
  const types = agg(rows, by('costType')).sort((x,y) => y.Expense - x.Expense);
  const fixed = types.find(t => t.key === 'Fixed');
  kpis('headsKpiRow', [
    {label:'Budget Heads', value:fmtNum(a.length)}, {label:'Total Budget', value:fmtCr(tb)}, {label:'Total Expense', value:fmtCr(te)},
    {label:'Largest Expense Head', value: big ? cut(big.key, 26) : '-', delta: big ? fmtCr(big.Expense) : '', cls:'muted'},
    {label:'Most Over-Budget Head', value: worst && worst.Variance < 0 ? cut(worst.key, 26) : '-', delta: worst && worst.Variance < 0 ? fmtCr(Math.abs(worst.Variance)) + ' over' : '', cls:'down'},
    {label:'Fixed-Cost Share', value: fixed && te > 0 ? fmtPct(fixed.Expense / te * 100) : '-', delta:'rent, security, housekeeping...', cls:'muted'},
  ]);
  fillBody('typeTable', types.map(t => `<tr><td>${esc(t.key)}</td><td class="num">${fmtCr(t.Budget)}</td><td class="num">${fmtCr(t.Expense)}</td><td class="num">${fmtCr(t.Variance)}</td><td class="num">${pill(t.UtilPct)}</td><td class="num">${te > 0 ? fmtPct(t.Expense / te * 100) : '-'}</td></tr>`).join(''));
  const h = Math.max(380, a.length * 34 + 60); boxH('headBE', h); boxH('headVar', h);
  beChart('headBE', a, true, 'budgetHead');
  const v = [...a].sort((x,y) => x.Variance - y.Variance), vl = v.map(x => x.key);
  mk('headVar', {type:'bar', data:{labels:v.map(x => cut(x.key, 30)), datasets:[{label:'Variance', data:v.map(x => x.Variance), backgroundColor:v.map(x => x.Variance < 0 ? COLORS.coral : COLORS.teal), borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}},
      plugins:{legend:{display:false}, datalabels:dlab(), tooltip:{callbacks:{title:it => vl[it[0].dataIndex]}}}, scales:{x:{title:{display:true, text:'Budget − Expense (₹)'}}},
      onClick:(evt, els) => { if (els.length) drillFilter('budgetHead', vl[els[0].index]); }}});
  fillBody('headTable', a.map(x => `<tr><td>${esc(x.key)}</td><td>${esc(HEAD_TYPE[x.key] || '')}</td><td class="num">${fmtCr(x.Budget)}</td><td class="num">${fmtCr(x.Expense)}</td><td class="num">${fmtCr(x.Variance)}</td><td class="num">${pill(x.UtilPct)}</td><td class="num">${x.Over}</td><td><span class="pill ${x.Variance < 0 ? 'bad' : 'good'}">${x.Variance < 0 ? 'Over Budget' : 'Within Budget'}</span></td></tr>`).join(''));
  setTag('headTableTag', a.length + ' heads');
}

// ---------------- REVENUE & MARGIN ----------------
function revData(){
  const f = r => ['state','centerName','month'].every(k => { const s = activeFilters[k]; return s.size === 0 || s.has(String(r[k] ?? '')); });
  const em = new Map();
  ROWS.filter(r => rowMatches(r, ['costType','budgetHead'])).forEach(r => {
    const k = r.centerName + '||' + r.month; let g = em.get(k); if (!g){ g = {e:0,b:0}; em.set(k, g); } g.e += E(r); g.b += B(r);
  });
  return REV.filter(f).map(x => {
    const g = em.get(x.centerName + '||' + x.month) || {e:0,b:0};
    return {...x, expense:g.e, budget:g.b, net:x.revenue - g.e, margin: x.revenue ? (x.revenue - g.e) / x.revenue * 100 : 0};
  }).sort((a,b) => ord(a.month) - ord(b.month) || a.centerName.localeCompare(b.centerName));
}
function renderRevenue(){
  const d = revData();
  const centers = new Set(d.map(x => x.centerName));
  $('revNote').textContent = `Revenue is available only for center-months where the Revenue column is filled in the sheet (currently: ${REV.length ? [...new Set(REV.map(x => x.centerName))].join(', ') : 'none'}). Expense and margin are calculated from the total expense of the same center-month.`;
  const tr = sum(d, x => x.revenue), te = sum(d, x => x.expense), net = tr - te;
  kpis('revKpiRow', [
    {label:'Total Revenue', value:fmtCr(tr)}, {label:'Expense (same center-months)', value:fmtCr(te)},
    {label:'Net Surplus', value:fmtCr(net), cls: net >= 0 ? 'up' : 'down', delta: net >= 0 ? 'profit' : 'loss'},
    {label:'Margin %', value: tr > 0 ? fmtPct(net / tr * 100) : '-'}, {label:'Expense % of Revenue', value: tr > 0 ? fmtPct(te / tr * 100) : '-'},
    {label:'Centers / Months', value: centers.size + ' / ' + new Set(d.map(x => x.month)).size},
  ]);
  const bm = new Map(); d.forEach(x => { let g = bm.get(x.month); if (!g){ g = {key:x.month, rev:0, exp:0}; bm.set(x.month, g); } g.rev += x.revenue; g.exp += x.expense; });
  const m = [...bm.values()].sort((a,b) => ord(a.key) - ord(b.key));
  mk('revMonthly', {data:{labels:m.map(x => x.key), datasets:[
      {type:'bar', label:'Revenue', data:m.map(x => x.rev), backgroundColor:'rgba(51,184,168,0.65)', borderRadius:5, yAxisID:'y', datalabels:dlab({align:'top'})},
      {type:'bar', label:'Expense', data:m.map(x => x.exp), backgroundColor:BAR_E, borderRadius:5, yAxisID:'y', datalabels:dlab({align:'top'})},
      {type:'line', label:'Margin %', data:m.map(x => x.rev ? (x.rev - x.exp) / x.rev * 100 : 0), borderColor:COLORS.violet, backgroundColor:COLORS.violet, tension:0.3, yAxisID:'y1', pointRadius:4, datalabels:dlab({align:'top', color:COLORS.violet, formatter:v => Math.round(v) + '%'})}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, interaction:{mode:'index', intersect:false},
      scales:{y:{position:'left', title:{display:true, text:'₹'}}, y1:{position:'right', grid:{display:false}, title:{display:true, text:'Margin %'}}}, plugins:{legend:{position:'bottom'}}}});
  const bc = new Map(); d.forEach(x => { let g = bc.get(x.centerName); if (!g){ g = {key:x.centerName, rev:0, exp:0}; bc.set(x.centerName, g); } g.rev += x.revenue; g.exp += x.expense; });
  const c = [...bc.values()].sort((a,b) => b.rev - a.rev);
  mk('revCenter', {type:'bar', data:{labels:c.map(x => cut(x.key, 22)), datasets:[
      {label:'Revenue', data:c.map(x => x.rev), backgroundColor:'rgba(51,184,168,0.65)', borderRadius:5},
      {label:'Expense', data:c.map(x => x.exp), backgroundColor:BAR_E, borderRadius:5}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, plugins:{legend:{position:'bottom'}, datalabels:dlab({align:'top'}), tooltip:{callbacks:{title:it => c[it[0].dataIndex].key}}},
      onClick:(evt, els) => { if (els.length) drillFilter('centerName', c[els[0].index].key); }}});
  fillBody('revTable', d.map(x => `<tr><td>${esc(x.centerName)}</td><td>${esc(x.month)}</td><td class="num">${fmtCr(x.revenue)}</td><td class="num">${fmtCr(x.budget)}</td><td class="num">${fmtCr(x.expense)}</td><td class="num"><span class="${x.net >= 0 ? 'up' : 'down'}">${fmtCr(x.net)}</span></td><td class="num">${fmtPct(x.margin)}</td><td class="num">${x.revenue ? fmtPct(x.expense / x.revenue * 100) : '-'}</td></tr>`).join(''));
  setTag('revTableTag', d.length + ' center-months');
}

// ---------------- APPROVALS ----------------
let apprSearchTerm = '';
function renderApprovals(){
  const rows = getFilteredRows();
  const booked = sum(rows, r => r.expense), appr = sum(rows, r => r.approved), pend = sum(rows, r => r.pending), pl = rows.filter(r => r.pending > 0.5);
  kpis('apprKpiRow', [
    {label:'Booked Expense', value:fmtCr(booked)}, {label:'Approved', value:fmtCr(appr), cls:'up'},
    {label:'Pending Approval', value:fmtCr(pend), cls: pend > 0 ? 'down' : 'up'},
    {label:'Approved %', value: booked > 0 ? fmtPct(appr / booked * 100) : '-'}, {label:'Lines Pending', value:fmtNum(pl.length) + ' / ' + fmtNum(rows.length)},
  ]);
  const a = agg(rows.filter(isMonthly), by('month')).sort(byMonth);
  mk('apprMonthly', {type:'bar', data:{labels:a.map(x => x.key), datasets:[
      {label:'Approved', data:a.map(x => x.Approved), backgroundColor:'rgba(51,184,168,0.7)', stack:'a'},
      {label:'Pending', data:a.map(x => x.Pending), backgroundColor:'rgba(224,102,95,0.75)', stack:'a'}]},
    options:{responsive:true, maintainAspectRatio:false, scales:{x:{stacked:true}, y:{stacked:true, title:{display:true, text:'₹'}}}, plugins:{legend:{position:'bottom'}},
      onClick:(evt, els) => { if (els.length) drillFilter('month', a[els[0].index].key); }}});
  const c = agg(rows, by('centerName')).filter(x => x.Pending > 0.5).sort((x,y) => y.Pending - x.Pending).slice(0, 12);
  mk('apprCenter', {type:'bar', data:{labels:c.map(x => cut(x.key, 30)), datasets:[{label:'Pending', data:c.map(x => x.Pending), backgroundColor:COLORS.coral, borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}}, plugins:{legend:{display:false}, datalabels:dlab(), tooltip:{callbacks:{title:it => c[it[0].dataIndex].key}}},
      onClick:(evt, els) => { if (els.length) drillFilter('centerName', c[els[0].index].key); }}});
  renderApprTable(pl);
}
function renderApprTable(pl){
  const term = apprSearchTerm.trim().toLowerCase();
  const f = pl.filter(r => !term || [r.centerName, r.budgetHead, r.month].some(v => String(v || '').toLowerCase().includes(term))).sort((a,b) => b.pending - a.pending);
  fillBody('apprTable', f.map(r => `<tr><td>${esc(r.centerName)}</td><td>${esc(r.budgetHead)}</td><td>${esc(r.month)}</td><td class="num">${fmtRs(r.expense)}</td><td class="num">${fmtRs(r.approved)}</td><td class="num down">${fmtRs(r.pending)}</td><td class="num">${r.expense ? fmtPct(r.approved / r.expense * 100) : '-'}</td></tr>`).join(''));
  setTag('apprTableTag', f.length + ' lines');
}
$('apprSearch').addEventListener('input', e => { apprSearchTerm = e.target.value; renderApprTable(getFilteredRows().filter(r => r.pending > 0.5)); });

// ---------------- ALERTS ----------------
let alertsSearchTerm = '';
function renderAlerts(){
  const rows = getFilteredRows(), over = rows.filter(isOver), unb = over.filter(isUnb);
  const byHead = agg(over, by('budgetHead')).sort((a,b) => b.OverAmt - a.OverAmt), byCenter = agg(over, by('centerName')).sort((a,b) => b.OverAmt - a.OverAmt);
  kpis('alertsKpiRow', [
    {label:'Over-Budget Lines', value:fmtNum(over.length) + ' / ' + fmtNum(rows.length), cls:'down'},
    {label:'Total Overspend', value:fmtCr(sum(over, overAmt)), cls:'down'},
    {label:'Unbudgeted Spend', value:fmtCr(sum(unb, E)), delta:unb.length + ' lines with ₹0 budget', cls:'down'},
    {label:'Worst Budget Head', value: byHead[0] ? cut(byHead[0].key, 26) : '-', delta: byHead[0] ? fmtCr(byHead[0].OverAmt) : '', cls:'down'},
    {label:'Worst Center', value: byCenter[0] ? cut(byCenter[0].key, 26) : '-', delta: byCenter[0] ? fmtCr(byCenter[0].OverAmt) : '', cls:'down'},
  ]);
  const top = [...over].sort((a,b) => overAmt(b) - overAmt(a)).slice(0, 25);
  const lab = r => r.centerShort + ' · ' + r.budgetHead;
  mk('alertsChart', {type:'bar', data:{labels:top.map(r => cut(lab(r), 36)), datasets:[{label:'Overspend', data:top.map(overAmt), backgroundColor:top.map(r => isUnb(r) ? COLORS.gold : COLORS.coral), borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}},
      plugins:{legend:{display:false}, datalabels:dlab(), tooltip:{callbacks:{title:it => lab(top[it[0].dataIndex]) + ' (' + top[it[0].dataIndex].month + ')'}}}, scales:{y:{ticks:{autoSkip:false, font:{size:9}}}},
      onClick:(evt, els) => { if (!els.length) return; alertsSearchTerm = top[els[0].index].centerShort; $('alertsSearch').value = alertsSearchTerm; renderAlertsTable(); $('alertsTable').scrollIntoView({behavior:'smooth', block:'start'}); }}});
  boxH('alertsChart', Math.max(380, top.length * 22 + 60));
  const h = byHead.slice(0, 12);
  mk('alertsHead', {type:'bar', data:{labels:h.map(x => cut(x.key, 30)), datasets:[{label:'Overspend', data:h.map(x => x.OverAmt), backgroundColor:COLORS.coral, borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}}, plugins:{legend:{display:false}, datalabels:dlab(), tooltip:{callbacks:{title:it => h[it[0].dataIndex].key}}},
      onClick:(evt, els) => { if (els.length) drillFilter('budgetHead', h[els[0].index].key); }}});
  const rp = new Map();
  over.forEach(r => { const k = r.centerName + '||' + r.budgetHead; let g = rp.get(k); if (!g){ g = {c:r.centerName, h:r.budgetHead, months:new Set(), amt:0}; rp.set(k, g); } g.months.add(r.month); g.amt += overAmt(r); });
  const rep = [...rp.values()].filter(g => g.months.size >= 2).sort((a,b) => b.amt - a.amt).slice(0, 60);
  fillBody('repeatTable', rep.map(g => `<tr><td>${esc(g.c)}</td><td>${esc(g.h)}</td><td class="num">${g.months.size}</td><td class="num down">${fmtCr(g.amt)}</td><td class="num">${fmtCr(g.amt / g.months.size)}</td><td>${esc([...g.months].sort((a,b) => ord(a) - ord(b)).join(', '))}</td></tr>`).join(''));
  setTag('repeatTableTag', rep.length + ' center-head pairs (over budget in 2+ months)');
  renderAlertsTable();
}
function renderAlertsTable(){
  const term = alertsSearchTerm.trim().toLowerCase();
  const rows = getFilteredRows().filter(isOver).filter(r => !term || [r.centerName, r.budgetHead, r.month, r.projectCode].some(v => String(v || '').toLowerCase().includes(term))).sort((a,b) => overAmt(b) - overAmt(a));
  fillBody('alertsTable', rows.map(r => `<tr class="row-bad"><td>${esc(r.centerName)}</td><td>${esc(r.budgetHead)}</td><td>${esc(r.month)}</td><td class="num">${fmtRs(B(r))}</td><td class="num">${fmtRs(E(r))}</td><td class="num">${fmtRs(overAmt(r))}</td><td><span class="pill ${isUnb(r) ? 'mid' : 'bad'}">${isUnb(r) ? 'Unbudgeted' : 'Over Budget'}</span></td></tr>`).join(''));
  setTag('alertsTableTag', rows.length + ' lines');
}
$('alertsSearch').addEventListener('input', e => { alertsSearchTerm = e.target.value; renderAlertsTable(); });

// ---------------- COMPARISON ----------------
let cmpSelected = new Set();
function populateCmpGroups(){
  const dim = $('cmpDimension').value, rows = getFilteredRows(), a = agg(rows, by(dim));
  const sorted = [...a]; if (dim === 'month') sorted.sort(byMonth); else sorted.sort(sortBudget);
  const values = sorted.map(x => x.key);
  const keep = new Set(values.filter(v => cmpSelected.has(v)));
  if (keep.size === 0 && values.length) [...a].sort(sortBudget).slice(0, 3).forEach(x => keep.add(x.key));
  cmpSelected = keep;
  const listEl = $('cmpGroupsList'); listEl.innerHTML = '';
  values.forEach(v => {
    const row = document.createElement('label'); row.className = 'ms-option';
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = v; cb.checked = cmpSelected.has(v);
    const span = document.createElement('span'); span.textContent = v; span.title = v;
    row.appendChild(cb); row.appendChild(span); listEl.appendChild(row);
  });
  updateCmpBtn(); renderComparison(); renderCostCompare();
}
function updateCmpBtn(){ const n = cmpSelected.size, b = $('cmpGroupsBtn'); b.textContent = n === 0 ? 'Select groups' : (n === 1 ? [...cmpSelected][0] : n + ' groups selected'); b.classList.toggle('active', n > 0); }
const readCmp = () => { cmpSelected = new Set(Array.from(document.querySelectorAll('#cmpGroupsList input:checked')).map(c => c.value)); updateCmpBtn(); renderComparison(); };
$('cmpGroupsBtn').addEventListener('click', e => { e.stopPropagation(); document.querySelectorAll('.ms-panel.open').forEach(p => { if (p.id !== 'cmpGroupsPanel') p.classList.remove('open'); }); $('cmpGroupsPanel').classList.toggle('open'); });
$('cmpGroupsPanel').addEventListener('click', e => e.stopPropagation());
$('cmpGroupsSearch').addEventListener('input', e => { const t = e.target.value.toLowerCase(); document.querySelectorAll('#cmpGroupsList .ms-option').forEach(o => { o.style.display = o.textContent.toLowerCase().includes(t) ? '' : 'none'; }); });
$('cmpGroupsAll').addEventListener('click', () => { document.querySelectorAll('#cmpGroupsList .ms-option').forEach(o => { if (o.style.display !== 'none') o.querySelector('input').checked = true; }); readCmp(); });
$('cmpGroupsClear').addEventListener('click', () => { document.querySelectorAll('#cmpGroupsList input').forEach(c => c.checked = false); readCmp(); });
$('cmpGroupsList').addEventListener('change', readCmp);
$('cmpDimension').addEventListener('change', () => { cmpSelected = new Set(); populateCmpGroups(); });
function renderComparison(){
  const dim = $('cmpDimension').value, rows = getFilteredRows();
  const map = new Map(agg(rows, by(dim)).map(a => [a.key, a]));
  const sel = [...cmpSelected]; if (dim === 'month') sel.sort((a,b) => ord(a) - ord(b)); else sel.sort();
  const g = sel.map(k => map.get(k) || {key:k, Budget:0, Expense:0, Variance:0, UtilPct:0});
  if (g.length){
    const best = [...g].sort((a,b) => a.UtilPct - b.UtilPct)[0], worst = [...g].sort((a,b) => b.UtilPct - a.UtilPct)[0];
    kpis('cmpKpiRow', [
      {label:'Groups Selected', value:fmtNum(g.length)}, {label:'Combined Budget', value:fmtCr(sum(g, x => x.Budget))}, {label:'Combined Expense', value:fmtCr(sum(g, x => x.Expense))},
      {label:'Lowest Utilization', value:cut(best.key, 22) + ' (' + fmtPct(best.UtilPct) + ')'}, {label:'Highest Utilization', value:cut(worst.key, 22) + ' (' + fmtPct(worst.UtilPct) + ')'},
    ]);
  } else $('cmpKpiRow').innerHTML = '';
  mk('cmpChart', {type:'bar', data:{labels:['Budget','Expense','Variance'], datasets:g.map((x, i) => ({label:cut(x.key, 28), data:[x.Budget, x.Expense, x.Variance], backgroundColor:PALETTE[i % PALETTE.length], borderRadius:5}))},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, plugins:{legend:{position:'bottom'}, datalabels:dlab({align:'top'})}}});
  mk('cmpUtil', {type:'bar', data:{labels:g.map(x => cut(x.key, 16)), datasets:[{label:'Utilization %', data:g.map(x => x.UtilPct), backgroundColor:g.map(x => utilCol(x.UtilPct)), borderRadius:5}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, plugins:{legend:{display:false}, datalabels:dlab({align:'top', formatter:v => Math.round(v) + '%'}), tooltip:{callbacks:{title:it => g[it[0].dataIndex].key}}}}});
  const base = g[0];
  fillBody('cmpTable', g.map((x, i) => {
    let dh = '-';
    if (i === 0) dh = '<span class="muted">baseline</span>';
    else if (base && base.Expense){ const d = (x.Expense - base.Expense) / Math.abs(base.Expense) * 100; dh = `<span class="${d <= 0 ? 'up' : 'down'}">${d >= 0 ? '+' : ''}${Math.round(d)}%</span>`; }
    return `<tr><td>${esc(x.key)}</td><td class="num">${fmtCr(x.Budget)}</td><td class="num">${fmtCr(x.Expense)}</td><td class="num">${dh}</td><td class="num">${fmtCr(x.Variance)}</td><td class="num">${pill(x.UtilPct)}</td></tr>`;
  }).join(''));
  setTag('cmpTableTag', g.length + ' groups');
}

// ---------------- DETAIL ----------------
const statusHtml = r => isUnb(r) ? '<span class="pill mid">Unbudgeted</span>' : (isOver(r) ? '<span class="pill bad">Over Budget</span>' : '<span class="pill good">Within Budget</span>');
const DCOLS = [
  {id:'centerName', label:'Center', get:r => r.centerName}, {id:'state', label:'State', get:r => r.state}, {id:'month', label:'Month', get:r => r.month},
  {id:'budgetHead', label:'Budget Head', get:r => r.budgetHead}, {id:'costType', label:'Cost Type', get:r => r.costType},
  {id:'budget', label:'Base Budget', get:r => fmtRs(r.budget)}, {id:'additional', label:'Additional Budget', get:r => fmtRs(r.additional)}, {id:'finalBudget', label:'Final Budget', get:r => fmtRs(r.finalBudget)},
  {id:'expense', label:'Expense (Booked)', get:r => fmtRs(r.expense)}, {id:'approved', label:'Approved', get:r => fmtRs(r.approved)}, {id:'pending', label:'Pending Approval', get:r => fmtRs(r.pending)},
  {id:'variance', label:'Variance', get:r => fmtRs(B(r) - E(r))}, {id:'util', label:'Util %', get:r => B(r) > 0 ? fmtPct(E(r) / B(r) * 100) : '-'},
  {id:'_status', label:'Status', html:true, get:statusHtml}, {id:'projectCode', label:'Project Code', get:r => r.projectCode}, {id:'uid', label:'UID', get:r => r.uid},
];
RAW_HEADERS.forEach(h => DCOLS.push({id:'raw:' + h, label:'Sheet: ' + h, get:r => r.raw[h]}));
const DEFAULT_DCOLS = ['centerName','state','month','budgetHead','costType','finalBudget','expense','approved','pending','variance','util','_status'];
let detailSel = new Set(DEFAULT_DCOLS), detailSearchTerm = '', detailOver = false, detailWithin = false;
function buildDetailColsPanel(){
  const l = $('detailColsList'); l.innerHTML = '';
  DCOLS.forEach(c => {
    const row = document.createElement('label'); row.className = 'ms-option';
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = c.id; cb.checked = detailSel.has(c.id);
    const sp = document.createElement('span'); sp.textContent = c.label; row.appendChild(cb); row.appendChild(sp); l.appendChild(row);
  });
  updateDetailBtn();
}
function updateDetailBtn(){ const n = detailSel.size, b = $('detailColsBtn'); b.textContent = n === 0 ? 'Select columns' : n + ' columns selected'; b.classList.toggle('active', n > 0); }
const readDetailCols = () => { detailSel = new Set(Array.from(document.querySelectorAll('#detailColsList input:checked')).map(c => c.value)); updateDetailBtn(); renderDetailTable(); };
$('detailColsBtn').addEventListener('click', e => { e.stopPropagation(); document.querySelectorAll('.ms-panel.open').forEach(p => { if (p.id !== 'detailColsPanel') p.classList.remove('open'); }); $('detailColsPanel').classList.toggle('open'); });
$('detailColsPanel').addEventListener('click', e => e.stopPropagation());
$('detailColsSearch').addEventListener('input', e => { const t = e.target.value.toLowerCase(); document.querySelectorAll('#detailColsList .ms-option').forEach(o => { o.style.display = o.textContent.toLowerCase().includes(t) ? '' : 'none'; }); });
$('detailColsAll').addEventListener('click', () => { document.querySelectorAll('#detailColsList .ms-option').forEach(o => { if (o.style.display !== 'none') o.querySelector('input').checked = true; }); readDetailCols(); });
$('detailColsClear').addEventListener('click', () => { document.querySelectorAll('#detailColsList input').forEach(c => c.checked = false); readDetailCols(); });
$('detailColsDefault').addEventListener('click', () => { document.querySelectorAll('#detailColsList input').forEach(c => { c.checked = DEFAULT_DCOLS.includes(c.value); }); readDetailCols(); });
$('detailColsList').addEventListener('change', readDetailCols);
function renderDetail(){
  const rows = getFilteredRows(), over = rows.filter(isOver).length;
  kpis('detailKpiRow', [
    {label:'Total Line Items', value:fmtNum(rows.length)}, {label:'Over-Budget', value:fmtNum(over), cls:'down'}, {label:'Within Budget', value:fmtNum(rows.length - over), cls:'up'},
    {label:'Total Budget', value:fmtCr(sum(rows, B))}, {label:'Total Expense', value:fmtCr(sum(rows, E))},
  ]);
  renderDetailTable();
}
function renderDetailTable(){
  const cols = DCOLS.filter(c => detailSel.has(c.id));
  $('detailTableHead').innerHTML = '<tr>' + cols.map(c => `<th>${esc(c.label)}</th>`).join('') + '</tr>';
  const term = detailSearchTerm.trim().toLowerCase();
  const rows = getFilteredRows().filter(r => {
    if (detailOver && !isOver(r)) return false;
    if (detailWithin && isOver(r)) return false;
    if (!term) return true;
    return [r.centerName, r.state, r.month, r.budgetHead, r.costType, r.projectCode, r.uid, ...Object.values(r.raw)].some(v => String(v ?? '').toLowerCase().includes(term));
  });
  fillBody('detailTable', rows.map(r => `<tr class="${isOver(r) ? 'row-bad' : ''}">` + cols.map(c => `<td>${c.html ? c.get(r) : esc(c.get(r))}</td>`).join('') + '</tr>').join(''));
  setTag('detailTableTag', rows.length + ' of ' + ROWS.length + ' items');
}
$('detailSearch').addEventListener('input', e => { detailSearchTerm = e.target.value; renderDetailTable(); });
$('overOnly').addEventListener('change', e => { detailOver = e.target.checked; if (detailOver){ detailWithin = false; $('withinOnly').checked = false; } renderDetailTable(); });
$('withinOnly').addEventListener('change', e => { detailWithin = e.target.checked; if (detailWithin){ detailOver = false; $('overOnly').checked = false; } renderDetailTable(); });

// ---------------- tabs ----------------
document.querySelectorAll('.tabbtn').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tabbtn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tabpage').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  const id = 'tab-' + btn.dataset.tab; $(id).classList.add('active'); renderTab(id);
}));

// ---------------- themes ----------------
const THEMES = {
  dark:    { name:'Dark (Default)', bg:'#0b1220', panel:'#121b2e', panel2:'#17233a', border:'#223252', text:'#e7ecf5', muted:'#8ea0c2', gold:'#d9a441', teal:'#33b8a8', coral:'#e0665f', violet:'#8b7ee8', grid:'rgba(255,255,255,0.06)', swatch:'#0b1220' },
  midnight:{ name:'Midnight Blue',  bg:'#03060d', panel:'#0b1424', panel2:'#101d34', border:'#1c2b47', text:'#dbe6ff', muted:'#6f83ab', gold:'#e0b45a', teal:'#3fd0c0', coral:'#ef6f68', violet:'#9d8ff2', grid:'rgba(255,255,255,0.05)', swatch:'#0b1a33' },
  forest:  { name:'Forest Green',   bg:'#0b120e', panel:'#121f18', panel2:'#182a21', border:'#25402f', text:'#e6f2ea', muted:'#83a692', gold:'#d9a441', teal:'#4fbf8b', coral:'#e0665f', violet:'#8b7ee8', grid:'rgba(255,255,255,0.06)', swatch:'#163523' },
  light:   { name:'Light',          bg:'#f4f6fb', panel:'#ffffff', panel2:'#eef1f8', border:'#d7deea', text:'#1b2434', muted:'#5b6b85', gold:'#b9791f', teal:'#128a7d', coral:'#c23f38', violet:'#6a5acd', grid:'rgba(0,0,0,0.07)', swatch:'#f4f6fb' },
};
const THEME_ORDER = ['dark','midnight','forest','light'];
const THEME_STORAGE_KEY = 'examBudgetDashboardTheme';
function applyTheme(name, skipRerender){
  const t = THEMES[name] || THEMES.dark, root = document.documentElement.style;
  root.setProperty('--bg', t.bg); root.setProperty('--panel', t.panel); root.setProperty('--panel-2', t.panel2); root.setProperty('--border', t.border);
  root.setProperty('--text', t.text); root.setProperty('--muted', t.muted); root.setProperty('--gold', t.gold); root.setProperty('--teal', t.teal);
  root.setProperty('--coral', t.coral); root.setProperty('--violet', t.violet); root.setProperty('--grid', t.grid);
  Chart.defaults.color = t.muted; Chart.defaults.borderColor = t.grid; currentDatalabelColor = t.text;
  const dot = $('themeDot'), label = $('themeBtnLabel');
  if (dot){ dot.style.background = t.gold; dot.style.boxShadow = '0 0 5px ' + t.gold; }
  if (label) label.textContent = t.name;
  document.querySelectorAll('.theme-option').forEach(el => el.classList.toggle('selected', el.dataset.theme === name));
  try { localStorage.setItem(THEME_STORAGE_KEY, name); } catch(e) {}
  if (!skipRerender) triggerFilterChange();
}
function buildThemePanel(){
  const panel = $('themePanel'); panel.innerHTML = '';
  THEME_ORDER.forEach(key => {
    const t = THEMES[key], row = document.createElement('div'); row.className = 'theme-option'; row.dataset.theme = key;
    row.innerHTML = `<span class="swatch" style="background:${t.swatch}"></span><span>${t.name}</span>`;
    row.addEventListener('click', () => { applyTheme(key); panel.classList.remove('open'); });
    panel.appendChild(row);
  });
}
$('themeBtn').addEventListener('click', e => { e.stopPropagation(); document.querySelectorAll('.ms-panel.open').forEach(p => p.classList.remove('open')); $('themePanel').classList.toggle('open'); });
$('themePanel').addEventListener('click', e => e.stopPropagation());

buildThemePanel();
let savedTheme = 'dark';
try { savedTheme = localStorage.getItem(THEME_STORAGE_KEY) || 'dark'; } catch(e) {}
applyTheme(savedTheme, true);
buildFilterBar();
buildDetailColsPanel();
buildCcHeadsPanel();
addExportButtons();
$('periodLabel').textContent = '__PERIOD_LABEL__';
renderOverview();
</script>
</body>
</html>
"""

st.set_page_config(page_title="Exam Center Budget Dashboard", layout="wide")

st.markdown(
    """
    <style>
        header[data-testid="stHeader"] { display: none !important; }
        div[data-testid="stToolbar"] { display: none !important; }
        div[data-testid="stDecoration"] { display: none !important; }
        div[data-testid="stStatusWidget"] { display: none !important; }
        .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; margin-top: 0rem !important; }
        div[data-testid="stAppViewContainer"] { padding-top: 0rem !important; }
        div[data-testid="stMainBlockContainer"] { padding-top: 0rem !important; }
        div[data-testid="stRadio"] { padding: 10px 24px 0; }
        iframe { display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Column mapping
# ----------------------------------------------------------------------
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
    # pandas suffixes repeated headers with ".1" -> strip before matching
    s = re.sub(r"\.\d+$", "", str(name))
    return "".join(s.lower().split()).replace("_", "")


@st.cache_data(ttl=300)
def load_data(url: str):
    raw = pd.read_csv(url)
    raw.columns = [str(c).strip() for c in raw.columns]
    orig_headers = list(raw.columns)

    new_cols, seen_center = [], False
    for col in raw.columns:
        norm = _normalize(col)
        if norm == "centercode":
            if not seen_center:
                new_cols.append("Center_Name")
                seen_center = True
            else:
                new_cols.append("Center_Code")
        else:
            new_cols.append(HEADER_ALIASES.get(norm, col))

    clean = raw.copy()
    clean.columns = new_cols

    for col in NUMERIC_COLS:
        if col in clean.columns:
            clean[col] = (
                clean[col].astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
                .str.strip()
            )
            clean[col] = pd.to_numeric(clean[col], errors="coerce").fillna(0)

    clean = clean.dropna(how="all")
    return raw, clean, orig_headers


# ----------------------------------------------------------------------
# Cleaning helpers (budget-head names, center names, states)
# ----------------------------------------------------------------------
CAPEX_RE = re.compile(r"beautification|webcam|furniture|blinds|networking|civil|cctv|paint", re.I)
HEAD_RULES = [
    (r"building rent|administration charge", "Building Rent", "Fixed"),
    (r"housekeeping", "Housekeeping", "Fixed"),
    (r"security", "Security Guard", "Fixed"),
    (r"salar|vendor'?s staff", "Vendor Salaries / Staff", "Fixed"),
    (r"co.?ordinator", "Coordinator Expenses", "Fixed"),
    (r"electric", "Electricity", "Utilities"),
    (r"\bdg\b", "DG Running Cost", "Utilities"),
    (r"water", "Water Bill", "Utilities"),
    (r"internet", "Internet", "Utilities"),
    (r"food", "Food (Team & Client)", "Operations"),
    (r"guest house", "Guest House", "Operations"),
    (r"admin material", "Admin Material", "Operations"),
    (r"printer", "Printer Cartridge", "Operations"),
    (r"amc|repair", "Repair & AMC", "Operations"),
    (r"misc", "Miscellaneous", "Operations"),
    (r"one time", "One Time Expense", "One-time / Capex"),
]


def classify_head(raw_head):
    """Same head is spelled differently across months (case / wording) -> unify + cost type."""
    h = re.sub(r"\s+", " ", str(raw_head)).strip()
    hl = h.lower()
    if CAPEX_RE.search(hl):
        d = re.sub(r"(?i)^beautification\s*&\s*incidental\s*", "", h).strip().replace("Purhcase", "Purchase")
        return "Setup: " + (d or h), "One-time / Capex"
    for pat, name, typ in HEAD_RULES:
        if re.search(pat, hl):
            return name, typ
    return h.title(), "Operations"


def split_center(name):
    s = re.sub(r"^\(|\)$", "", str(name).strip()).strip()
    s = re.sub(r"^([A-Za-z0-9]+)\s*-\s*", r"\1 - ", s)
    m = re.match(r"^([A-Z]+\d+)\s*-", s)
    return s, (m.group(1) if m else s)


def fix_state(s, proj):
    s = str(s).strip()
    if s.lower() in ("", "nan", "#n/a", "none"):
        return "Gujarat" if "GUJ" in str(proj).upper() else "Unknown"
    return {"Gujrat": "Gujarat"}.get(s, s)


def month_sort_key(m):
    for fmt in ("%b_%y", "%B_%y", "%b-%y", "%b_%Y", "%B_%Y"):
        try:
            return datetime.strptime(str(m), fmt)
        except Exception:
            continue
    return None


def _json_safe(v):
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return str(v)
    return v


def num(r, col):
    try:
        return float(r.get(col, 0) or 0)
    except Exception:
        return 0.0


def build_dataset(raw_df, df):
    """Turn the cleaned dataframe into the JSON-ready rows used by the dashboard."""
    center_col = "Center_Name" if "Center_Name" in df.columns else "Center_Code"
    rows, rev_map = [], {}
    for i, r in df.iterrows():
        month = str(r.get("Month", "")).strip()
        center, short = split_center(r.get(center_col, ""))
        head, ctype = classify_head(r.get("Budget_Head", ""))
        bud, exp, appr = num(r, "Budget"), num(r, "Expense"), num(r, "Approved_Expense")
        extra = num(r, "Not_Related_Budget")
        final = num(r, "Final_Budget") or bud
        rev = num(r, "Revenue")

        if rev > 0:  # revenue is entered once per center-month -> de-duplicate here
            k = (center, month)
            rev_map[k] = max(rev_map.get(k, 0), rev)

        if bud == 0 and final == 0 and exp == 0 and appr == 0:
            continue  # empty placeholder lines (e.g. unused Year_26 heads)

        proj = str(r.get("Project_Code", "")).strip()
        rows.append({
            "uid": str(r.get("UID", "")).strip(),
            "centerName": center,
            "centerShort": short,
            "projectCode": proj,
            "month": month,
            "budgetHead": head,
            "costType": ctype,
            "state": fix_state(r.get("State", ""), proj),
            "budget": bud,
            "additional": extra,
            "finalBudget": final,
            "expense": exp,
            "approved": appr,
            "pending": max(0.0, exp - appr),
            "raw": {h: _json_safe(v) for h, v in raw_df.loc[i].items()},
        })

    all_months = sorted({r["month"] for r in rows if r["month"]})
    parsed = {m: month_sort_key(m) for m in all_months}
    months = sorted([m for m in all_months if parsed[m]], key=lambda m: parsed[m]) + [m for m in all_months if not parsed[m]]
    non_monthly = [m for m in all_months if not parsed[m]]
    monthly_only = [m for m in months if parsed.get(m)]
    period = f"{monthly_only[0]} – {monthly_only[-1]}" if len(monthly_only) > 1 else (monthly_only[0] if monthly_only else "")

    state_of = {}
    for x in rows:
        state_of.setdefault(x["centerName"], x["state"])
    rev_rows = [{"centerName": c, "month": m, "revenue": v, "state": state_of.get(c, "")}
                for (c, m), v in rev_map.items()]
    return rows, rev_rows, months, non_monthly, period


def dump(obj):
    return json.dumps(obj, default=str, ensure_ascii=False).replace("</", "<\\/")


# ----------------------------------------------------------------------
# Division switch (Infra / APK)
# ----------------------------------------------------------------------
view = st.radio("Division", list(SOURCES.keys()), horizontal=True, label_visibility="collapsed")

try:
    raw_df, df, orig_headers = load_data(SOURCES[view])
except Exception as e:
    st.error(f"Could not load '{view}' data from the Google Sheet: {e}")
    st.stop()

missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(
        f"[{view}] These required column(s) were not found in the sheet: {', '.join(missing)}.\n\n"
        "The actual column headers of the sheet are shown below — "
        "please check them and add the correct names in HEADER_ALIASES."
    )
    st.write("Columns found in the sheet:", list(df.columns))
    st.stop()

df = df[df["Budget_Head"].notna()]
raw_df = raw_df.loc[df.index]
if df.empty:
    st.error(f"[{view}] No data could be loaded (0 rows). Please check the sheet sharing - it must be set to 'Anyone with the link - Viewer'.")
    st.stop()

rows, rev_rows, months, non_monthly, period_label = build_dataset(raw_df, df)
if not rows:
    st.error(f"[{view}] No rows left after filtering. Please check the sheet data.")
    st.stop()

html = DASHBOARD_TEMPLATE_HTML
html = html.replace("__ROWS_JSON__", dump(rows))
html = html.replace("__REV_JSON__", dump(rev_rows))
html = html.replace("__MONTH_ORDER_JSON__", dump(months))
html = html.replace("__NON_MONTHLY_JSON__", dump(non_monthly))
html = html.replace("__RAW_HEADERS_JSON__", dump(orig_headers))
html = html.replace("__PERIOD_LABEL__", period_label)
html = html.replace("__DIV_TITLE__", view)

components.html(html, height=2800, scrolling=True)
st.caption(f"Live data ({view}) — auto-refreshes every 5 min from Google Sheet.")
