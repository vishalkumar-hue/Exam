"""
APK Project Budget vs Actual Expenses Dashboard
Data source: Google Sheet "APK" tab  (or upload a CSV / TSV / XLSX export of the same sheet)

Expected columns (typos in the sheet are fine, they are mapped automatically):
  Project Code | Expences Head | Budget Head | Budget | Actual Expences | Margine | Margine %

Setup: set GID below to the number after "gid=" in the APK tab URL
(and change SHEET_ID if the APK tab is in a different workbook).
The sheet must be shared as "Anyone with the link - Viewer".
"""

import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

SHEET_ID = "1P8awjtc-dwxCce1WJLDixljqL37yqCxnOe5QZ75_gIw"  # change if the APK tab is in another workbook
GID = ""  # <-- paste the APK tab gid here. If empty, the app asks you to upload a file instead.

# Friendly project names, keyed by the 2nd part of the project code (add new ones here)
PROJECT_NAMES = {
    "RAIPUR-LAND": "Raipur Land",
    "APK-EXP-JAIPR": "Jaipur",
    "APK-EXP-LUCK": "Lucknow",
    "APK-PRYJ": "Prayagraj",
    "APK-EXP-BHOPAL": "Bhopal",
    "GUJARAT-SETUP": "Gujarat Setup",
    "APK-NAYARAIPUR": "Naya Raipur",
    "APK-KANPUR": "Kanpur",
}
LARGE_OVERSPEND_PCT = 300  # lines spent at/above this % of budget are flagged "verify"

DASHBOARD_TEMPLATE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>APK Project Budget Dashboard</title>
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
  .kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:14px; margin-bottom:22px;}
  .kpi{background:linear-gradient(160deg, var(--panel), var(--panel-2)); border:1px solid var(--border); border-radius:10px; padding:16px 18px;}
  .kpi .label{font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:0.6px;}
  .kpi .value{font-size:21px; font-weight:700; margin-top:6px; word-break:break-word;}
  .kpi .delta{font-size:11.5px; margin-top:4px;}
  .up{color:var(--teal);} .down{color:var(--coral);} .muted{color:var(--muted);}
  .note{font-size:12px; color:var(--muted); margin:-4px 0 14px; line-height:1.5;}
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
  .search-row select, .cmp-controls select{background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:7px 10px; font-size:13px; font-family:inherit;}
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
  .pill{padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; white-space:nowrap; display:inline-block; margin:1px 2px 1px 0;}
  .pill.good{background:rgba(51,184,168,0.15); color:var(--teal);}
  .pill.bad{background:rgba(224,102,95,0.15); color:var(--coral);}
  .pill.mid{background:rgba(217,164,65,0.15); color:var(--gold);}
  .pill.blue{background:rgba(79,139,208,0.18); color:#6fa8e0;}
  .pill.dim{background:rgba(142,160,194,0.15); color:var(--muted);}
  .live-dot{display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--teal); margin-right:6px; box-shadow:0 0 6px var(--teal); animation:pulse 1.6s infinite;}
  @keyframes pulse{0%{opacity:1;}50%{opacity:0.35;}100%{opacity:1;}}
  .cmp-controls label{font-size:11.5px; color:var(--muted); display:block; margin-bottom:4px;}
  .cmp-controls .cmp-field{display:flex; flex-direction:column;}
  .topn-input{background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:5px; padding:3px 7px; font-size:11.5px; width:58px; text-align:center; font-family:inherit;}
  .topn-input:focus{outline:none; border-color:var(--gold);}
  /* expandable project row */
  .hm-row{cursor:pointer;}
  .hm-row:hover td.hm-name{color:var(--gold);}
  .hm-name::after{content:' ▸'; color:var(--muted); font-size:10px;}
  tr.hm-selected td.hm-name{color:var(--gold); font-weight:700; box-shadow:inset 3px 0 0 var(--gold);}
  tr.hm-selected td.hm-name::after{content:' ▾'; color:var(--gold);}
  tr.hm-detail td{background:var(--panel-2) !important; padding:12px 14px; white-space:normal; border-bottom:2px solid var(--gold);}
  .hm-chips{display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px;}
  .hm-chips:last-child{margin-bottom:0;}
  .hm-chip{background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:7px 11px; min-width:130px;}
  .hm-chip.tot{border-color:var(--teal);} .hm-chip.key{border-color:var(--gold);} .hm-chip.bad{border-color:var(--coral);}
  .hm-chip-l{font-size:10.5px; color:var(--muted);}
  .hm-chip-v{font-size:14px; font-weight:700; margin-top:2px;}
  .hm-chip-s{font-size:10.5px; color:var(--muted); margin-top:1px;}
  @media (max-width:980px){ .grid,.grid.even{grid-template-columns:1fr;} }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <h1>APK<span>&amp;</span>Infra</h1>
      <div class="sub"><span class="live-dot"></span>APK Projects · Budget vs Actual Expenses (Live)</div>
    </div>
    <div class="topbar-right">
      <div class="sub" id="periodLabel"></div>
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
    <button class="tabbtn" data-tab="heads">Budget Heads</button>
    <button class="tabbtn" data-tab="items">Line Items</button>
    <button class="tabbtn" data-tab="alerts">Alerts &amp; Data Quality</button>
    <button class="tabbtn" data-tab="comparison">Comparison</button>
  </div>

  <!-- OVERVIEW -->
  <div id="tab-overview" class="tabpage active">
    <div class="kpis" id="kpiRow"></div>
    <div class="grid">
      <div class="card"><h3>Budget vs Actual by Project <span class="tag">click a bar to see its line items</span></h3>
        <div class="chart-box tall"><canvas id="ovProject"></canvas></div></div>
      <div class="card"><h3>Share of Actual Spend by Project</h3>
        <div class="chart-box tall"><canvas id="ovShare"></canvas></div></div>
    </div>
    <div class="grid even" style="margin-top:16px;">
      <div class="card"><h3>Utilization % by Project <span class="tag">label = Util % · Actual / Budget · blue &lt;95%, teal 95–100%, red &gt;100%</span></h3>
        <div class="chart-box tall"><canvas id="ovUtil"></canvas></div></div>
      <div class="card"><h3>Line Items by Spend Status <span class="tag">count of lines</span></h3>
        <div class="chart-box tall"><canvas id="ovStatus"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;">
      <h3>Project Summary <span class="tag" id="projTableTag">click a project to see its budget heads below the row</span></h3>
      <div class="scroll-table"><table id="projTable">
        <thead><tr><th>Project</th><th>Code Date</th><th>Type</th><th class="num">Lines</th><th class="num">Budget</th><th class="num">Actual</th><th class="num">Remaining</th><th class="num">Util %</th><th class="num">Over-Budget Lines</th><th class="num">Not Started Lines</th></tr></thead>
        <tbody></tbody></table></div>
    </div>
  </div>

  <!-- BUDGET HEADS -->
  <div id="tab-heads" class="tabpage">
    <div class="kpis" id="headsKpiRow"></div>
    <div class="grid even">
      <div class="card"><h3>Budget vs Actual by Budget Head <span class="tag">sorted by budget</span></h3>
        <div class="chart-box" id="headBEBox"><canvas id="headBE"></canvas></div></div>
      <div class="card"><h3>Utilization % by Budget Head <span class="tag">label = Util % · Actual / Budget</span></h3>
        <div class="chart-box" id="headUtilBox"><canvas id="headUtil"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Project × Budget Head Utilization Heatmap <span class="tag">Top <input type="text" class="topn-input" id="topNHeads" value="12"> heads by budget · red &gt;100%, teal 95–100%, blue in progress</span></h3>
      <div class="scroll-table"><table id="matrixTable" class="heat"><thead></thead><tbody></tbody></table></div></div>
    <div class="card"><h3>Budget Head Analysis <span class="tag" id="headTableTag"></span></h3>
      <div class="scroll-table"><table id="headTable">
        <thead><tr><th>Budget Head</th><th class="num">Projects</th><th class="num">Lines</th><th class="num">Budget</th><th class="num">Actual</th><th class="num">Remaining</th><th class="num">Util %</th><th class="num">Over-Budget Lines</th><th class="num">Not Started Lines</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- LINE ITEMS -->
  <div id="tab-items" class="tabpage">
    <div class="kpis" id="itemsKpiRow"></div>
    <div class="grid even">
      <div class="card"><h3>Top 15 Lines by Actual Spend <span class="tag">Budget vs Actual</span></h3>
        <div class="chart-box" id="topActualBox"><canvas id="topActual"></canvas></div></div>
      <div class="card"><h3>Top 15 Lines by Remaining Budget <span class="tag">money still to be spent</span></h3>
        <div class="chart-box" id="topRemainingBox"><canvas id="topRemaining"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>All Line Items <span class="tag" id="itemTableTag"></span></h3>
      <div class="search-row">
        <input type="text" id="itemSearch" placeholder="Search project, head, status...">
        <select id="itemStatus"><option value="">All statuses</option></select>
      </div>
      <div class="scroll-table"><table id="itemTable">
        <thead><tr><th>Project</th><th>Budget Head</th><th>Expense Head</th><th class="num">Budget</th><th class="num">Actual</th><th class="num">Remaining</th><th class="num">Util %</th><th>Status</th><th>Flags</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- ALERTS -->
  <div id="tab-alerts" class="tabpage">
    <div class="kpis" id="alertsKpiRow"></div>
    <div class="grid even">
      <div class="card"><h3>Biggest Overspends <span class="tag">top 15 lines · gold = unbudgeted</span></h3>
        <div class="chart-box" id="overLinesBox"><canvas id="overLines"></canvas></div></div>
      <div class="card"><h3>Overspend by Project</h3>
        <div class="chart-box tall"><canvas id="overProject"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Lines to Review <span class="tag" id="flagTableTag"></span></h3>
      <div class="note" id="flagNote"></div>
      <div class="search-row"><input type="text" id="flagSearch" placeholder="Search project, head, flag..."></div>
      <div class="scroll-table"><table id="flagTable">
        <thead><tr><th>Project</th><th>Budget Head</th><th>Expense Head</th><th class="num">Budget</th><th class="num">Actual</th><th class="num">Over (+) / Under (−)</th><th class="num">Util %</th><th>Flags</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>

  <!-- COMPARISON -->
  <div id="tab-comparison" class="tabpage">
    <div class="card"><h3>Comparison Mode <span class="tag">compare 2+ projects, budget heads, project types or clients</span></h3>
      <div class="search-row cmp-controls">
        <div class="cmp-field"><label for="cmpDimension">Compare by</label>
          <select id="cmpDimension">
            <option value="project">Project</option><option value="budgetHead">Budget Head</option>
            <option value="type">Project Type</option><option value="client">Client</option>
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
      <div class="card"><h3>Budget, Actual &amp; Remaining <span class="tag">₹</span></h3><div class="chart-box tall"><canvas id="cmpChart"></canvas></div></div>
      <div class="card"><h3>Utilization % <span class="tag">per group</span></h3><div class="chart-box tall"><canvas id="cmpUtil"></canvas></div></div>
    </div>
    <div class="card" style="margin-top:16px;"><h3>Comparison Table <span class="tag" id="cmpTableTag"></span></h3>
      <div class="scroll-table"><table id="cmpTable">
        <thead><tr><th>Group</th><th class="num">Budget</th><th class="num">Actual</th><th class="num">Actual Δ% vs first</th><th class="num">Remaining</th><th class="num">Util %</th></tr></thead>
        <tbody></tbody></table></div></div>
  </div>
</div>

<script>
const ROWS = __ROWS_JSON__;
const INFO = __INFO_JSON__;

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
const fmtPct = v => (v === null || v === undefined || isNaN(v)) ? '-' : ((v > 0 && v < 10) ? v.toFixed(1) + '%' : Math.round(v) + '%');
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
  ['projTable','project-summary'],['matrixTable','project-head-heatmap'],['headTable','budget-head-analysis'],
  ['itemTable','line-items'],['flagTable','lines-to-review'],['cmpTable','comparison']
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
const COLORS = { gold:'#d9a441', teal:'#33b8a8', coral:'#e0665f', violet:'#8b7ee8', blue:'#4f8bd0', grey:'#8ea0c2' };
const PALETTE = ['#d9a441','#33b8a8','#e0665f','#8b7ee8','#4f8bd0','#5cc96a','#e0a8d0','#e0d05f','#6fa8e0','#c98b5c','#8adfd4','#b98ae0'];
const BAR_B = 'rgba(79,139,208,0.55)', BAR_E = 'rgba(217,164,65,0.75)', BAR_R = 'rgba(51,184,168,0.65)';
const charts = {};
function mk(id, cfg){ if (charts[id]) charts[id].destroy(); charts[id] = new Chart($(id), cfg); return charts[id]; }
const dlab = (o = {}) => ({display:true, clip:false, color:currentDatalabelColor, font:{size:9,weight:'600'}, anchor:'end', align:'right', formatter:v=>fmtCr(v), ...o});

// ---------------- status / metrics ----------------
const STATUS_ORDER = ['Not Started','In Progress','Fully Used','Over Budget','Unbudgeted'];
const STATUS_COL = {'Not Started':'#8ea0c2','In Progress':'#4f8bd0','Fully Used':'#33b8a8','Over Budget':'#e0665f','Unbudgeted':'#d9a441'};
const STATUS_PILL = {'Not Started':'dim','In Progress':'blue','Fully Used':'good','Over Budget':'bad','Unbudgeted':'mid'};
const statusPill = s => `<span class="pill ${STATUS_PILL[s] || 'dim'}">${esc(s)}</span>`;
const flagPill = f => `<span class="pill ${/Large/i.test(f) ? 'bad' : 'mid'}">${esc(f)}</span>`;
const utilPill = u => (u === null || u === undefined) ? '<span class="muted">-</span>' : `<span class="pill ${u > 100.5 ? 'bad' : (u >= 95 ? 'good' : 'blue')}">${fmtPct(u)}</span>`;
const utilCol = u => (u === null || u === undefined) ? COLORS.gold : (u > 100.5 ? COLORS.coral : (u >= 95 ? COLORS.teal : COLORS.blue));
const rem = r => r.budget - r.actual;
const isOver = r => r.actual > r.budget + 0.5;
const isUnb = r => r.budget <= 0 && r.actual > 0.5;
const overAmt = r => r.actual - r.budget;
const sortBudget = (a,b) => b.Budget - a.Budget;
const by = f => r => r[f];
const PROJ_META = {};
ROWS.forEach(r => { if (!PROJ_META[r.project]) PROJ_META[r.project] = {created:r.created, type:r.type, code:r.code}; });

function agg(rows, keyFn){
  const m = new Map();
  rows.forEach(r => {
    const k = keyFn(r) || '(blank)';
    let g = m.get(k);
    if (!g){ g = {key:k, Budget:0, Actual:0, Count:0, Over:0, OverAmt:0, NotStarted:0, Projects:new Set()}; m.set(k, g); }
    g.Budget += r.budget; g.Actual += r.actual; g.Count++; g.Projects.add(r.project);
    if (isOver(r)){ g.Over++; g.OverAmt += overAmt(r); }
    if (r.status === 'Not Started') g.NotStarted++;
  });
  return [...m.values()].map(g => ({...g, Remaining: g.Budget - g.Actual, UtilPct: g.Budget > 0 ? g.Actual / g.Budget * 100 : null}));
}

// ---------------- filters ----------------
const FILTER_DEFS = [
  {key:'project', label:'Project'},
  {key:'client', label:'Client'},
  {key:'type', label:'Project Type'},
  {key:'budgetHead', label:'Budget Head'},
  {key:'status', label:'Status', order: STATUS_ORDER},
];
const activeFilters = {};
FILTER_DEFS.forEach(f => activeFilters[f.key] = new Set());
function uniqueValues(field, order){
  const vals = Array.from(new Set(ROWS.map(r => r[field]).filter(v => v !== null && v !== undefined && v !== '')));
  if (order && order.length) vals.sort((a,b) => order.indexOf(a) - order.indexOf(b)); else vals.sort();
  return vals;
}
function triggerFilterChange(){ const a = document.querySelector('.tabpage.active'); renderTab(a ? a.id : 'tab-overview'); }
function renderTab(t){
  if (t === 'tab-overview') renderOverview();
  else if (t === 'tab-heads') renderHeads();
  else if (t === 'tab-items') renderItems();
  else if (t === 'tab-alerts') renderAlerts();
  else if (t === 'tab-comparison') populateCmpGroups();
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
const rowMatches = row => FILTER_DEFS.every(f => { const s = activeFilters[f.key]; return !s || s.size === 0 || s.has(String(row[f.key] ?? '')); });
const getFilteredRows = () => ROWS.filter(rowMatches);
function drillFilter(key, value){
  if (value === undefined || value === null || value === '') return;
  activeFilters[key] = new Set([value]);
  const listEl = document.querySelector('#mspanel_' + key + ' .ms-list'), btn = $('msbtn_' + key);
  if (listEl) listEl.querySelectorAll('input').forEach(c => { c.checked = (c.value === value); });
  if (btn){ btn.textContent = value; btn.classList.add('active'); }
  document.querySelector('.tabbtn[data-tab="items"]').click();
}

// ---------------- reusable chart ----------------
function beChart(id, a, drill){
  const labels = a.map(x => x.key);
  mk(id, {type:'bar', data:{labels: a.map(x => cut(x.key, 30)), datasets:[
      {label:'Budget', data:a.map(x => x.Budget), backgroundColor:BAR_B, borderRadius:5},
      {label:'Actual', data:a.map(x => x.Actual), backgroundColor:BAR_E, borderRadius:5}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}},
      plugins:{legend:{position:'bottom'}, datalabels:dlab(), tooltip:{callbacks:{title:it => labels[it[0].dataIndex], label:c => c.dataset.label + ': ' + fmtRs(c.parsed.x)}}},
      onClick:(evt, els) => { if (els.length && drill) drillFilter(drill, labels[els[0].index]); }}});
}
function utilChart(id, a, drill){
  const u = [...a].sort((x,y) => (y.UtilPct ?? -1) - (x.UtilPct ?? -1));
  mk(id, {type:'bar', data:{labels:u.map(x => cut(x.key, 30)), datasets:[{label:'Utilization %', data:u.map(x => x.UtilPct ?? 0), backgroundColor:u.map(x => utilCol(x.UtilPct)), borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:210}},
      plugins:{legend:{display:false},
        datalabels:dlab({formatter:(v, ctx) => { const x = u[ctx.dataIndex]; return (x.UtilPct === null ? 'no budget' : fmtPct(v)) + '  ·  ' + fmtCr(x.Actual) + ' / ' + fmtCr(x.Budget); }}),
        tooltip:{callbacks:{title:it => u[it[0].dataIndex].key, label:c => 'Utilization: ' + fmtPct(u[c.dataIndex].UtilPct), afterLabel:c => ['Budget: ' + fmtRs(u[c.dataIndex].Budget), 'Actual: ' + fmtRs(u[c.dataIndex].Actual), 'Remaining: ' + fmtRs(u[c.dataIndex].Remaining)]}}},
      onClick:(evt, els) => { if (els.length && drill) drillFilter(drill, u[els[0].index].key); }}});
}

// ---------------- OVERVIEW ----------------
let openProjects = new Set();
function projDetailHtml(name){
  const rows = getFilteredRows().filter(r => r.project === name);
  if (!rows.length) return '<span class="muted">No data for this project under the current filters.</span>';
  const heads = agg(rows, by('budgetHead')).sort((a,b) => b.Actual - a.Actual || b.Budget - a.Budget);
  const tb = sum(rows, r => r.budget), ta = sum(rows, r => r.actual);
  const chip = (l, a, b, cls, sub) => `<div class="hm-chip ${cls || ''}"><div class="hm-chip-l">${esc(l)}</div><div class="hm-chip-v">${fmtCr(a)}</div><div class="hm-chip-s">${sub !== undefined ? sub : 'Budget ' + fmtCr(b) + (b > 0 ? ' · ' + fmtPct(a / b * 100) : '')}</div></div>`;
  return '<div class="hm-chips">'
    + chip('Total Actual', ta, tb, 'tot')
    + chip('Remaining Budget', tb - ta, tb, 'key', 'of ' + fmtCr(tb) + ' budget')
    + '</div><div class="hm-chips">'
    + heads.map(x => chip(x.key, x.Actual, x.Budget, x.Actual > x.Budget + 0.5 ? 'bad' : '')).join('')
    + '</div>';
}
function projRow(a){
  const m = PROJ_META[a.key] || {}, open = openProjects.has(a.key);
  return `<tr class="hm-row${open ? ' hm-selected' : ''}" data-key="${esc(a.key)}"><td class="hm-name" title="${esc(m.code || '')}">${esc(a.key)}</td><td>${esc(m.created || '')}</td><td>${esc(m.type || '')}</td><td class="num">${a.Count}</td><td class="num">${fmtCr(a.Budget)}</td><td class="num">${fmtCr(a.Actual)}</td><td class="num">${fmtCr(a.Remaining)}</td><td class="num">${utilPill(a.UtilPct)}</td><td class="num">${a.Over}</td><td class="num">${a.NotStarted}</td></tr>`
    + (open ? `<tr class="hm-detail" data-key="${esc(a.key)}"><td colspan="10">${projDetailHtml(a.key)}</td></tr>` : '');
}
$('projTable').addEventListener('click', e => {
  const tr = e.target.closest('tr.hm-row'); if (!tr) return;
  const name = tr.dataset.key, nxt = tr.nextElementSibling;
  if (openProjects.has(name)){
    openProjects.delete(name); tr.classList.remove('hm-selected');
    if (nxt && nxt.classList.contains('hm-detail')) nxt.remove();
  } else {
    openProjects.add(name); tr.classList.add('hm-selected');
    const d = document.createElement('tr'); d.className = 'hm-detail'; d.dataset.key = name;
    const td = document.createElement('td'); td.colSpan = tr.children.length; td.innerHTML = projDetailHtml(name);
    d.appendChild(td); tr.after(d);
  }
});
function renderOverview(){
  const rows = getFilteredRows();
  const tb = sum(rows, r => r.budget), ta = sum(rows, r => r.actual);
  const over = rows.filter(isOver), unb = rows.filter(isUnb), ns = rows.filter(r => r.status === 'Not Started');
  kpis('kpiRow', [
    {label:'Total Budget', value:fmtCr(tb), delta:fmtNum(rows.length) + ' line items', cls:'muted'},
    {label:'Actual Expenses', value:fmtCr(ta), delta: tb > 0 ? fmtPct(ta / tb * 100) + ' of budget' : '', cls:'muted'},
    {label:'Remaining Budget', value:fmtCr(tb - ta), delta: tb >= ta ? 'available' : 'over budget overall', cls: tb >= ta ? 'up' : 'down'},
    {label:'Utilization %', value: tb > 0 ? fmtPct(ta / tb * 100) : '-'},
    {label:'Over-Budget Lines', value:fmtNum(over.length) + ' / ' + fmtNum(rows.length), delta: over.length ? fmtCr(sum(over, overAmt)) + ' overspend' : 'none', cls: over.length ? 'down' : 'up'},
    {label:'Unbudgeted Spend', value:fmtCr(sum(unb, r => r.actual)), delta:unb.length + ' lines with ₹0 budget', cls: unb.length ? 'down' : 'up'},
    {label:'Not Started', value:fmtNum(ns.length) + ' lines', delta:fmtCr(sum(ns, r => r.budget)) + ' budget untouched', cls:'muted'},
    {label:'Projects', value:fmtNum(new Set(rows.map(r => r.project)).size)},
  ]);
  const p = agg(rows, by('project')).sort(sortBudget);
  boxH('ovProject', Math.max(380, p.length * 40 + 60));
  beChart('ovProject', p, 'project');
  const sp = p.filter(x => x.Actual > 0).sort((a,b) => b.Actual - a.Actual), spTotal = sum(sp, x => x.Actual);
  mk('ovShare', {type:'doughnut', data:{labels:sp.map(x => x.key), datasets:[{data:sp.map(x => x.Actual), backgroundColor:sp.map((x,i) => PALETTE[i % PALETTE.length]), borderWidth:2, borderColor:cssv('--panel')}]},
    options:{responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'bottom', labels:{boxWidth:10, font:{size:10}}}, datalabels:dlab({anchor:'center', align:'center', font:{size:10,weight:'700'}, display:c => spTotal > 0 && c.dataset.data[c.dataIndex] / spTotal > 0.05}),
        tooltip:{callbacks:{label:c => c.label + ': ' + fmtRs(c.parsed) + ' (' + fmtPct(spTotal ? c.parsed / spTotal * 100 : 0) + ')'}}},
      onClick:(evt, els) => { if (els.length) drillFilter('project', sp[els[0].index].key); }}});
  boxH('ovUtil', Math.max(380, p.length * 40 + 60));
  utilChart('ovUtil', p, 'project');
  const st = STATUS_ORDER.map(k => { const x = rows.filter(r => r.status === k); return {key:k, n:x.length, b:sum(x, r => r.budget), a:sum(x, r => r.actual)}; }).filter(x => x.n > 0);
  mk('ovStatus', {type:'doughnut', data:{labels:st.map(x => x.key), datasets:[{data:st.map(x => x.n), backgroundColor:st.map(x => STATUS_COL[x.key]), borderWidth:2, borderColor:cssv('--panel')}]},
    options:{responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'bottom'}, datalabels:dlab({anchor:'center', align:'center', font:{size:11,weight:'700'}, formatter:v => v}),
        tooltip:{callbacks:{label:c => st[c.dataIndex].key + ': ' + st[c.dataIndex].n + ' lines', afterLabel:c => ['Budget: ' + fmtRs(st[c.dataIndex].b), 'Actual: ' + fmtRs(st[c.dataIndex].a)]}}},
      onClick:(evt, els) => { if (els.length) drillFilter('status', st[els[0].index].key); }}});
  fillBody('projTable', p.map(projRow).join(''));
  setTag('projTableTag', p.length + ' projects · click a project to see its budget heads below the row');
}

// ---------------- BUDGET HEADS ----------------
function renderHeads(){
  const rows = getFilteredRows();
  const a = agg(rows, by('budgetHead')).sort(sortBudget);
  const topSpend = [...a].sort((x,y) => y.Actual - x.Actual)[0], topOver = [...a].sort((x,y) => y.OverAmt - x.OverAmt)[0], big = a[0];
  kpis('headsKpiRow', [
    {label:'Budget Heads', value:fmtNum(a.length)},
    {label:'Total Budget', value:fmtCr(sum(a, x => x.Budget))},
    {label:'Total Actual', value:fmtCr(sum(a, x => x.Actual))},
    {label:'Largest Budget Head', value: big ? cut(big.key, 26) : '-', delta: big ? fmtCr(big.Budget) : '', cls:'muted'},
    {label:'Highest Spend Head', value: topSpend && topSpend.Actual > 0 ? cut(topSpend.key, 26) : '-', delta: topSpend && topSpend.Actual > 0 ? fmtCr(topSpend.Actual) : '', cls:'muted'},
    {label:'Most Overspent Head', value: topOver && topOver.OverAmt > 0 ? cut(topOver.key, 26) : '-', delta: topOver && topOver.OverAmt > 0 ? fmtCr(topOver.OverAmt) + ' over' : '', cls:'down'},
    {label:'Heads Not Started', value:fmtNum(a.filter(x => x.Actual <= 0).length) + ' / ' + fmtNum(a.length), cls:'muted'},
  ]);
  const h = Math.max(380, a.length * 34 + 60); boxH('headBE', h); boxH('headUtil', h);
  beChart('headBE', a, 'budgetHead');
  utilChart('headUtil', a, 'budgetHead');
  renderMatrix(rows, a);
  fillBody('headTable', a.map(x => `<tr><td>${esc(x.key)}</td><td class="num">${x.Projects.size}</td><td class="num">${x.Count}</td><td class="num">${fmtCr(x.Budget)}</td><td class="num">${fmtCr(x.Actual)}</td><td class="num">${fmtCr(x.Remaining)}</td><td class="num">${utilPill(x.UtilPct)}</td><td class="num">${x.Over}</td><td class="num">${x.NotStarted}</td></tr>`).join(''));
  setTag('headTableTag', a.length + ' budget heads');
}
let topNHeads = 12;
function renderMatrix(rows, heads){
  const n = topNHeads === Infinity ? heads.length : topNHeads;
  const hs = heads.slice(0, n);
  const projs = agg(rows, by('project')).sort(sortBudget);
  const cm = new Map();
  rows.forEach(r => { const k = r.project + '|' + r.budgetHead; let g = cm.get(k); if (!g){ g = {b:0, a:0}; cm.set(k, g); } g.b += r.budget; g.a += r.actual; });
  const bg = u => u > 100.5 ? 'rgba(224,102,95,0.38)' : (u >= 95 ? 'rgba(51,184,168,0.30)' : (u > 0 ? 'rgba(79,139,208,0.22)' : 'transparent'));
  document.querySelector('#matrixTable thead').innerHTML = '<tr><th>Project</th>' + hs.map(h => `<th class="num" style="text-align:center" title="${esc(h.key)}">${esc(cut(h.key, 16))}</th>`).join('') + '<th class="num" style="text-align:center">Overall</th></tr>';
  fillBody('matrixTable', projs.map(pr => {
    const cells = hs.map(h => {
      const g = cm.get(pr.key + '|' + h.key);
      if (!g) return '<td class="hc muted">-</td>';
      if (g.b <= 0) return g.a > 0 ? `<td class="hc" style="background:rgba(217,164,65,0.25)" title="Unbudgeted: ${fmtRs(g.a)}">${fmtCr(g.a)}</td>` : '<td class="hc muted">-</td>';
      const u = g.a / g.b * 100;
      return `<td class="hc" style="background:${bg(u)}" title="${fmtRs(g.a)} of ${fmtRs(g.b)}">${fmtPct(u)}</td>`;
    }).join('');
    return `<tr><td>${esc(pr.key)}</td>${cells}<td class="hc" style="background:${bg(pr.UtilPct ?? 0)};font-weight:700">${fmtPct(pr.UtilPct)}</td></tr>`;
  }).join(''));
}
const onTopNHeads = e => { topNHeads = parseTopN(e.target.value); renderHeads(); };
$('topNHeads').addEventListener('input', onTopNHeads); $('topNHeads').addEventListener('change', onTopNHeads);

// ---------------- LINE ITEMS ----------------
let itemSearchTerm = '', itemStatusSel = '';
function renderItems(){
  const rows = getFilteredRows(), spent = rows.filter(r => r.actual > 0);
  kpis('itemsKpiRow', [
    {label:'Line Items', value:fmtNum(rows.length)},
    {label:'With Spend', value:fmtNum(spent.length), cls:'up'},
    {label:'Not Started', value:fmtNum(rows.filter(r => r.status === 'Not Started').length), cls:'muted'},
    {label:'Total Budget', value:fmtCr(sum(rows, r => r.budget))},
    {label:'Total Actual', value:fmtCr(sum(rows, r => r.actual))},
  ]);
  const lab = r => cut(r.project + ' · ' + r.expHead, 44);
  const ta = [...spent].sort((a,b) => b.actual - a.actual).slice(0, 15);
  boxH('topActual', Math.max(380, ta.length * 34 + 60));
  mk('topActual', {type:'bar', data:{labels:ta.map(lab), datasets:[
      {label:'Budget', data:ta.map(r => r.budget), backgroundColor:BAR_B, borderRadius:4},
      {label:'Actual', data:ta.map(r => r.actual), backgroundColor:BAR_E, borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}},
      plugins:{legend:{position:'bottom'}, datalabels:dlab(), tooltip:{callbacks:{title:it => ta[it[0].dataIndex].project + ' · ' + ta[it[0].dataIndex].expHead, label:c => c.dataset.label + ': ' + fmtRs(c.parsed.x)}}},
      scales:{y:{ticks:{autoSkip:false, font:{size:9}}}}}});
  const tr = rows.filter(r => rem(r) > 0).sort((a,b) => rem(b) - rem(a)).slice(0, 15);
  boxH('topRemaining', Math.max(380, tr.length * 34 + 60));
  mk('topRemaining', {type:'bar', data:{labels:tr.map(lab), datasets:[{label:'Remaining Budget', data:tr.map(rem), backgroundColor:BAR_R, borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}},
      plugins:{legend:{display:false}, datalabels:dlab(), tooltip:{callbacks:{title:it => tr[it[0].dataIndex].project + ' · ' + tr[it[0].dataIndex].expHead, label:c => 'Remaining: ' + fmtRs(c.parsed.x), afterLabel:c => 'Budget: ' + fmtRs(tr[c.dataIndex].budget)}}},
      scales:{y:{ticks:{autoSkip:false, font:{size:9}}}}}});
  renderItemTable();
}
function renderItemTable(){
  const term = itemSearchTerm.trim().toLowerCase();
  const rows = getFilteredRows().filter(r => (!itemStatusSel || r.status === itemStatusSel)
    && (!term || [r.project, r.code, r.budgetHead, r.expHead, r.status, ...r.flags].some(v => String(v || '').toLowerCase().includes(term))))
    .sort((a,b) => a.project.localeCompare(b.project) || b.budget - a.budget);
  fillBody('itemTable', rows.map(r => `<tr class="${isOver(r) ? 'row-bad' : ''}"><td>${esc(r.project)}</td><td>${esc(r.budgetHead)}</td><td>${esc(r.expHead)}</td><td class="num">${fmtRs(r.budget)}</td><td class="num">${fmtRs(r.actual)}</td><td class="num">${fmtRs(rem(r))}</td><td class="num">${utilPill(r.budget > 0 ? r.actual / r.budget * 100 : null)}</td><td>${statusPill(r.status)}</td><td>${r.flags.map(flagPill).join('')}</td></tr>`).join(''));
  setTag('itemTableTag', rows.length + ' of ' + ROWS.length + ' items');
}
STATUS_ORDER.forEach(s => { const o = document.createElement('option'); o.value = s; o.textContent = s; $('itemStatus').appendChild(o); });
$('itemSearch').addEventListener('input', e => { itemSearchTerm = e.target.value; renderItemTable(); });
$('itemStatus').addEventListener('change', e => { itemStatusSel = e.target.value; renderItemTable(); });

// ---------------- ALERTS & DATA QUALITY ----------------
let flagSearchTerm = '';
function renderAlerts(){
  const rows = getFilteredRows(), over = rows.filter(isOver), unb = over.filter(isUnb), flagged = rows.filter(r => r.flags.length);
  kpis('alertsKpiRow', [
    {label:'Over-Budget Lines', value:fmtNum(over.length) + ' / ' + fmtNum(rows.length), cls: over.length ? 'down' : 'up'},
    {label:'Total Overspend', value:fmtCr(sum(over, overAmt)), cls:'down'},
    {label:'Unbudgeted Spend', value:fmtCr(sum(unb, r => r.actual)), delta:unb.length + ' lines with ₹0 budget', cls:'down'},
    {label:'Lines to Verify', value:fmtNum(flagged.length), delta:'flagged for a data check', cls: flagged.length ? 'down' : 'up'},
    {label:'Sheet Formula Errors', value:fmtNum(INFO.formulaErrors), delta:'#DIV/0! / #VALUE! in source', cls:'muted'},
  ]);
  const top = [...over].sort((a,b) => overAmt(b) - overAmt(a)).slice(0, 15);
  boxH('overLines', Math.max(380, top.length * 34 + 60));
  mk('overLines', {type:'bar', data:{labels:top.map(r => cut(r.project + ' · ' + r.expHead, 44)), datasets:[{label:'Overspend', data:top.map(overAmt), backgroundColor:top.map(r => isUnb(r) ? COLORS.gold : COLORS.coral), borderRadius:4}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false, layout:{padding:{right:62}},
      plugins:{legend:{display:false}, datalabels:dlab(), tooltip:{callbacks:{title:it => top[it[0].dataIndex].project + ' · ' + top[it[0].dataIndex].expHead, label:c => 'Overspend: ' + fmtRs(c.parsed.x), afterLabel:c => ['Budget: ' + fmtRs(top[c.dataIndex].budget), 'Actual: ' + fmtRs(top[c.dataIndex].actual)]}}},
      scales:{y:{ticks:{autoSkip:false, font:{size:9}}}},
      onClick:(evt, els) => { if (!els.length) return; flagSearchTerm = top[els[0].index].expHead; $('flagSearch').value = flagSearchTerm; renderFlagTable(); $('flagTable').scrollIntoView({behavior:'smooth', block:'start'}); }}});
  const op = agg(over, by('project')).sort((a,b) => b.OverAmt - a.OverAmt);
  mk('overProject', {type:'bar', data:{labels:op.map(x => cut(x.key, 22)), datasets:[{label:'Overspend', data:op.map(x => x.OverAmt), backgroundColor:COLORS.coral, borderRadius:4}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}},
      plugins:{legend:{display:false}, datalabels:dlab({align:'top'}), tooltip:{callbacks:{title:it => op[it[0].dataIndex].key, label:c => 'Overspend: ' + fmtRs(c.parsed.y), afterLabel:c => op[c.dataIndex].Over + ' over-budget lines'}}},
      onClick:(evt, els) => { if (els.length) drillFilter('project', op[els[0].index].key); }}});
  $('flagNote').innerHTML = 'Flags: <b>Unbudgeted spend</b> = actual booked against a ₹0 budget line · <b>Large overspend</b> = actual is ' + INFO.largePct + '%+ of budget (often a typo in the amount) · <b>Possible duplicate</b> = same expense head, budget and actual repeated in another project. '
    + 'The sheet shows #DIV/0! / #VALUE! on ' + INFO.formulaErrors + ' line(s); this dashboard recalculates Remaining and Util % from Budget and Actual, so they are not affected.'
    + (INFO.mismatch ? ' <b>' + INFO.mismatch + '</b> line(s) have a sheet Margin that differs from Budget − Actual.' : '');
  renderFlagTable();
}
function renderFlagTable(){
  const term = flagSearchTerm.trim().toLowerCase();
  const rows = getFilteredRows().filter(r => isOver(r) || r.flags.length)
    .filter(r => !term || [r.project, r.budgetHead, r.expHead, ...r.flags].some(v => String(v || '').toLowerCase().includes(term)))
    .sort((a,b) => overAmt(b) - overAmt(a));
  fillBody('flagTable', rows.map(r => `<tr class="${isOver(r) ? 'row-bad' : ''}"><td>${esc(r.project)}</td><td>${esc(r.budgetHead)}</td><td>${esc(r.expHead)}</td><td class="num">${fmtRs(r.budget)}</td><td class="num">${fmtRs(r.actual)}</td><td class="num"><span class="${overAmt(r) > 0 ? 'down' : 'up'}">${overAmt(r) > 0 ? '+' : '−'}${fmtRs(Math.abs(overAmt(r)))}</span></td><td class="num">${utilPill(r.budget > 0 ? r.actual / r.budget * 100 : null)}</td><td>${r.flags.map(flagPill).join('')}</td></tr>`).join(''));
  setTag('flagTableTag', rows.length + ' lines');
}
$('flagSearch').addEventListener('input', e => { flagSearchTerm = e.target.value; renderFlagTable(); });

// ---------------- COMPARISON ----------------
let cmpSelected = new Set();
function populateCmpGroups(){
  const dim = $('cmpDimension').value, a = agg(getFilteredRows(), by(dim));
  const values = [...a].sort(sortBudget).map(x => x.key);
  const keep = new Set(values.filter(v => cmpSelected.has(v)));
  if (keep.size === 0 && values.length) values.slice(0, 3).forEach(v => keep.add(v));
  cmpSelected = keep;
  const listEl = $('cmpGroupsList'); listEl.innerHTML = '';
  values.forEach(v => {
    const row = document.createElement('label'); row.className = 'ms-option';
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.value = v; cb.checked = cmpSelected.has(v);
    const span = document.createElement('span'); span.textContent = v; span.title = v;
    row.appendChild(cb); row.appendChild(span); listEl.appendChild(row);
  });
  updateCmpBtn(); renderComparison();
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
  const g = [...cmpSelected].sort().map(k => map.get(k) || {key:k, Budget:0, Actual:0, Remaining:0, UtilPct:null});
  if (g.length){
    const withU = g.filter(x => x.UtilPct !== null);
    const lo = [...withU].sort((a,b) => a.UtilPct - b.UtilPct)[0], hi = [...withU].sort((a,b) => b.UtilPct - a.UtilPct)[0];
    kpis('cmpKpiRow', [
      {label:'Groups Selected', value:fmtNum(g.length)}, {label:'Combined Budget', value:fmtCr(sum(g, x => x.Budget))}, {label:'Combined Actual', value:fmtCr(sum(g, x => x.Actual))},
      {label:'Lowest Utilization', value: lo ? cut(lo.key, 22) + ' (' + fmtPct(lo.UtilPct) + ')' : '-'},
      {label:'Highest Utilization', value: hi ? cut(hi.key, 22) + ' (' + fmtPct(hi.UtilPct) + ')' : '-'},
    ]);
  } else $('cmpKpiRow').innerHTML = '';
  mk('cmpChart', {type:'bar', data:{labels:g.map(x => cut(x.key, 22)), datasets:[
      {label:'Budget', data:g.map(x => x.Budget), backgroundColor:BAR_B, borderRadius:5},
      {label:'Actual', data:g.map(x => x.Actual), backgroundColor:BAR_E, borderRadius:5},
      {label:'Remaining', data:g.map(x => x.Remaining), backgroundColor:BAR_R, borderRadius:5}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, plugins:{legend:{position:'bottom'}, datalabels:dlab({align:'top'}), tooltip:{callbacks:{title:it => g[it[0].dataIndex].key, label:c => c.dataset.label + ': ' + fmtRs(c.parsed.y)}}}}});
  mk('cmpUtil', {type:'bar', data:{labels:g.map(x => cut(x.key, 16)), datasets:[{label:'Utilization %', data:g.map(x => x.UtilPct ?? 0), backgroundColor:g.map(x => utilCol(x.UtilPct)), borderRadius:5}]},
    options:{responsive:true, maintainAspectRatio:false, layout:{padding:{top:20}}, plugins:{legend:{display:false}, datalabels:dlab({align:'top', formatter:(v, ctx) => g[ctx.dataIndex].UtilPct === null ? 'no budget' : fmtPct(v)}), tooltip:{callbacks:{title:it => g[it[0].dataIndex].key}}}}});
  const base = g[0];
  fillBody('cmpTable', g.map((x, i) => {
    let dh = '-';
    if (i === 0) dh = '<span class="muted">baseline</span>';
    else if (base && base.Actual){ const d = (x.Actual - base.Actual) / Math.abs(base.Actual) * 100; dh = `<span class="${d <= 0 ? 'up' : 'down'}">${d >= 0 ? '+' : ''}${Math.round(d)}%</span>`; }
    return `<tr><td>${esc(x.key)}</td><td class="num">${fmtCr(x.Budget)}</td><td class="num">${fmtCr(x.Actual)}</td><td class="num">${dh}</td><td class="num">${fmtCr(x.Remaining)}</td><td class="num">${utilPill(x.UtilPct)}</td></tr>`;
  }).join(''));
  setTag('cmpTableTag', g.length + ' groups');
}

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
const THEME_STORAGE_KEY = 'apkProjectDashboardTheme';
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
addExportButtons();
$('periodLabel').textContent = '__PERIOD_LABEL__';
renderOverview();
</script>
</body>
</html>
"""

st.set_page_config(page_title="APK Project Budget Dashboard", layout="wide")

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
        iframe { display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Column mapping (sheet headers have typos: "Expences", "Margine" ...)
# ----------------------------------------------------------------------
HEADER_ALIASES = {
    "projectcode": "Project_Code",
    "expenceshead": "Expense_Head", "expenseshead": "Expense_Head",
    "expencehead": "Expense_Head", "expensehead": "Expense_Head",
    "budgethead": "Budget_Head",
    "budget": "Budget",
    "actualexpences": "Actual", "actualexpenses": "Actual",
    "actualexpence": "Actual", "actualexpense": "Actual", "actual": "Actual",
    "margine": "Margin", "margin": "Margin",
    "margine%": "Margin_Pct", "margin%": "Margin_Pct",
    "remarks": "Remarks",
}
REQUIRED_COLS = ["Project_Code", "Budget_Head", "Budget", "Actual"]


def _norm(name):
    return re.sub(r"[^a-z%]", "", str(name).lower())


def to_num(series):
    s = series.astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce")  # "#DIV/0!", "#VALUE!" -> NaN


def clean_text(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def parse_code(code):
    """IIL/APK-NAYARAIPUR/240226/CENTRE-SETUP/IILC -> client, project key, date, type"""
    parts = [p.strip() for p in str(code).split("/")]
    client = parts[0] if parts else ""
    key = parts[1] if len(parts) > 1 else parts[0]
    date = None
    if len(parts) > 2:
        try:
            date = datetime.strptime(parts[2], "%d%m%y")
        except ValueError:
            date = None
    ptype = parts[3] if len(parts) > 3 else ""
    return client, key, date, ptype


def project_name(key):
    k = key.strip().upper()
    if k in PROJECT_NAMES:
        return PROJECT_NAMES[k]
    return re.sub(r"^APK-(EXP-)?", "", key, flags=re.I).replace("-", " ").title()


def status_of(budget, actual):
    if budget <= 0:
        return "Unbudgeted" if actual > 0 else "No Budget"
    if actual <= 0:
        return "Not Started"
    util = actual / budget * 100
    if util > 100.5:
        return "Over Budget"
    if util >= 95:
        return "Fully Used"
    return "In Progress"


def prepare(raw):
    df = raw.copy()
    df.columns = [HEADER_ALIASES.get(_norm(c), str(c).strip()) for c in df.columns]
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return None, {"missing": missing, "found": list(df.columns)}

    # drop the second "header-like" row and empty rows
    code = df["Project_Code"].astype(str).str.strip()
    keep = ~code.str.lower().isin(["project code", "", "nan", "none"])
    skipped = int((~keep).sum())
    df = df[keep].copy()

    # sheet formula errors (#DIV/0!, #VALUE!) in Margin columns
    err = pd.Series(False, index=df.index)
    for col in ("Margin", "Margin_Pct"):
        if col in df.columns:
            err |= df[col].astype(str).str.strip().str.startswith("#")
    formula_errors = int(err.sum())

    df["Budget"] = to_num(df["Budget"]).fillna(0)
    df["Actual"] = to_num(df["Actual"]).fillna(0)
    sheet_margin = to_num(df["Margin"]) if "Margin" in df.columns else pd.Series(float("nan"), index=df.index)

    rows, mismatch = [], 0
    for idx, r in df.iterrows():
        bud, act = float(r["Budget"]), float(r["Actual"])
        if bud == 0 and act == 0:
            continue
        client, key, date, ptype = parse_code(r["Project_Code"])
        bhead = clean_text(r.get("Budget_Head", ""))
        ehead = clean_text(r.get("Expense_Head", "")) or bhead
        bhead = bhead or ehead
        sm = sheet_margin.get(idx)
        if pd.notna(sm) and abs(float(sm) - (bud - act)) > 1:
            mismatch += 1
        rows.append({
            "code": clean_text(r["Project_Code"]),
            "project": project_name(key),
            "client": client,
            "type": ptype,
            "created": date.strftime("%d %b %Y") if date else "",
            "budgetHead": bhead,
            "expHead": ehead,
            "budget": bud,
            "actual": act,
            "status": status_of(bud, act),
            "flags": [],
        })

    # flags: unbudgeted, large overspend, possible duplicates across projects
    dup = {}
    for r in rows:
        if r["actual"] > 0:
            dup.setdefault((r["expHead"].lower(), r["budget"], r["actual"]), set()).add(r["project"])
    for r in rows:
        if r["budget"] <= 0 and r["actual"] > 0:
            r["flags"].append("Unbudgeted spend")
        elif r["budget"] > 0 and r["actual"] / r["budget"] * 100 >= LARGE_OVERSPEND_PCT:
            r["flags"].append(f"Large overspend ({LARGE_OVERSPEND_PCT}%+)")
        if r["actual"] > 0 and len(dup.get((r["expHead"].lower(), r["budget"], r["actual"]), ())) >= 2:
            r["flags"].append("Possible duplicate")

    info = {"formulaErrors": formula_errors, "skipped": skipped, "mismatch": mismatch, "largePct": LARGE_OVERSPEND_PCT}
    return rows, info


@st.cache_data(ttl=300)
def load_sheet(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return pd.read_csv(url)


def read_upload(f):
    name = f.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    if name.endswith((".tsv", ".txt")):
        return pd.read_csv(f, sep="\t")
    return pd.read_csv(f, sep=None, engine="python")


# ----------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------
raw_df = None
if str(GID).strip():
    try:
        raw_df = load_sheet(SHEET_ID, str(GID).strip())
    except Exception as e:
        st.error(f"Could not load data from the Google Sheet: {e}")
        st.stop()
else:
    up = st.file_uploader("Upload the APK sheet (CSV / TSV / XLSX) - or set GID in the code to read it live from Google Sheets",
                          type=["csv", "tsv", "txt", "xlsx", "xls"])
    if up is None:
        st.info("Set GID at the top of this file to load the APK tab live, or upload an export of the sheet here.")
        st.stop()
    try:
        raw_df = read_upload(up)
    except Exception as e:
        st.error(f"Could not read the uploaded file: {e}")
        st.stop()

rows, info = prepare(raw_df)
if rows is None:
    st.error("These required column(s) were not found in the sheet: " + ", ".join(info["missing"]) +
             ". Please check the headers and add the correct names in HEADER_ALIASES.")
    st.write("Columns found in the sheet:", info["found"])
    st.stop()
if not rows:
    st.error("No data rows found after cleaning. Please check the sheet data and sharing (Anyone with the link - Viewer).")
    st.stop()

period_label = f"{len({r['project'] for r in rows})} projects · {len(rows)} line items"


def dump(obj):
    return json.dumps(obj, default=str, ensure_ascii=False).replace("</", "<\\/")


html = DASHBOARD_TEMPLATE_HTML
html = html.replace("__ROWS_JSON__", dump(rows))
html = html.replace("__INFO_JSON__", dump(info))
html = html.replace("__PERIOD_LABEL__", period_label)

components.html(html, height=2600, scrolling=True)
st.caption("Budget = 'Budget' column, Actual = 'Actual Expences' column. Remaining and Util % are recalculated here, so sheet errors like #DIV/0! do not affect the charts.")
