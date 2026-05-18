#!/usr/bin/env python3
"""
Walking Challenge 2026 — GitHub Pages Publisher
Reads walking_data.json, generates a self-contained HTML dashboard
with all history embedded, and pushes to GitHub Pages via API.
"""

import json, base64, urllib.request, urllib.error, os, sys
from datetime import datetime, date, timezone

WORKSPACE    = os.path.dirname(os.path.abspath(__file__))
DATA_FILE    = os.path.join(WORKSPACE, "walking_data.json")

# Prefer environment variables (GitHub Actions), fall back to local config file
def _load_github_config():
    env_token = os.environ.get("GH_TOKEN")
    env_repo  = os.environ.get("GITHUB_REPO")
    if env_token:
        return env_token, env_repo or "psccwc2026/PSCC-walking-challenge-2026"
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bewell_config.json")
    with open(config_path) as f:
        cfg = json.load(f)
    return cfg["github_token"], cfg.get("github_repo", "psccwc2026/PSCC-walking-challenge-2026")

GITHUB_TOKEN, GITHUB_REPO = _load_github_config()
GITHUB_PATH  = "index.html"
PAGES_URL    = "https://psccwc2026.github.io/PSCC-walking-challenge-2026/"

CHALLENGE_START = "2026-05-18"
CHALLENGE_END   = "2026-06-15"
DAILY_GOAL      = 8000

TEAMS = [
    {"id": 132544, "name": "Accounting Walkaholics",        "short": "Walkaholics",   "color": "#10b981"},
    {"id": 132626, "name": "PSCC Build is Too Fit to Quit", "short": "PSCC Build",    "color": "#f97316"},
    {"id": 132610, "name": "BusOps Walking Deadlines",      "short": "BusOps",        "color": "#6366f1"},
    {"id": 132609, "name": "Fast and Fully Compliant",      "short": "Fast & Comply", "color": "#eab308"},
]


def generate_html(data):
    # Always stamp the current publish time so "Last synced" reflects this push
    data = dict(data, lastUpdated=datetime.now(timezone.utc).isoformat())
    data_js  = json.dumps(data,  separators=(',', ':'))
    teams_js = json.dumps(TEAMS, separators=(',', ':'))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PSCC Walking Challenge 2026</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js" integrity="sha384-iU8HYtnGQ8Cy4zl7gbNMOhsDTTKX02BTXptVP/vqAWIaTfM7isw76iyZCsjL2eVi" crossorigin="anonymous"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f1f5f9;color:#1e293b;font-size:14px;line-height:1.5}}
.page{{max-width:1200px;margin:0 auto;padding:16px}}
.header{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 22px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;gap:12px}}
.header h1{{font-size:20px;font-weight:700}}
.header p{{font-size:12px;color:#64748b;margin-top:3px}}
.meta{{text-align:right}}
.meta .lbl{{font-size:11px;color:#94a3b8}}
.meta .val{{font-size:12px;font-weight:600;color:#334155}}
.stats-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}}
.stat{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px}}
.stat .sl{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.4px}}
.stat .sv{{font-size:22px;font-weight:800;margin-top:2px}}
.stat .ss{{font-size:11px;color:#94a3b8;margin-top:1px}}
.tabs{{display:flex;gap:4px;margin-bottom:14px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:4px;width:fit-content}}
.tab{{padding:7px 18px;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;color:#64748b;transition:all .15s;border:none;background:none}}
.tab.active{{background:#3b82f6;color:#fff}}
.tab-content{{display:none}}
.tab-content.active{{display:block}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px}}
.card h2{{font-size:14px;font-weight:700;margin-bottom:14px}}
.team-row{{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f1f5f9}}
.team-row:last-child{{border-bottom:none}}
.rank{{font-size:16px;font-weight:800;width:26px;text-align:center;flex-shrink:0}}
.dot{{width:11px;height:11px;border-radius:50%;flex-shrink:0}}
.ti{{flex:1;min-width:0}}
.ti .tn{{font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ti .tm{{font-size:11px;color:#94a3b8}}
.ti .bar-bg{{background:#f1f5f9;border-radius:2px;height:4px;margin-top:5px}}
.ti .bar-fg{{height:4px;border-radius:2px}}
.ts{{text-align:right;flex-shrink:0}}
.ts .steps{{font-size:15px;font-weight:700}}
.ts .avg{{font-size:11px;color:#94a3b8}}
.chart-wrap{{position:relative;height:195px}}
.full-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;margin-bottom:14px}}
.full-card h2{{font-size:14px;font-weight:700;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse}}
th{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.4px;padding:7px 10px;text-align:left;border-bottom:1px solid #e2e8f0;white-space:nowrap}}
td{{padding:8px 10px;font-size:13px;border-bottom:1px solid #f8fafc;white-space:nowrap}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#fafbfd}}
.badge{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}}
.day-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;margin-bottom:14px}}
.day-card h2{{font-size:14px;font-weight:700;margin-bottom:10px}}
.day-controls{{display:flex;align-items:center;gap:10px;margin-bottom:14px}}
.day-controls label{{font-size:12px;color:#64748b}}
.day-controls select{{padding:5px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;background:#fff;cursor:pointer}}
/* History table */
.hist-controls{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;align-items:center}}
.hist-controls select{{padding:5px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;background:#fff;cursor:pointer}}
.hist-controls label{{font-size:12px;color:#64748b}}
.scroll-wrap{{overflow-x:auto}}
.hist-table th{{font-size:10px;padding:5px 7px}}
.hist-table td{{font-size:12px;padding:5px 7px}}
.cell-hit{{background:#d1fae5;color:#065f46;font-weight:600;border-radius:3px;display:inline-block;padding:1px 4px;min-width:52px;text-align:right}}
.cell-miss{{background:#fee2e2;color:#991b1b;border-radius:3px;display:inline-block;padding:1px 4px;min-width:52px;text-align:right}}
.cell-zero{{color:#cbd5e1;display:inline-block;padding:1px 4px;min-width:52px;text-align:right}}
.total-col{{font-weight:700;background:#f8fafc}}
@media(max-width:700px){{.two-col{{grid-template-columns:1fr}}.stats-bar{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    <div>
      <h1>🚶 PSCC Walking Challenge 2026</h1>
      <p id="subhead">Loading…</p>
    </div>
    <div class="meta">
      <div class="lbl">Last synced</div>
      <div class="val" id="lastSync">—</div>
    </div>
  </div>

  <div class="stats-bar">
    <div class="stat"><div class="sl">Total Steps</div><div class="sv" id="statSteps">—</div><div class="ss">all 4 teams</div></div>
    <div class="stat"><div class="sl">Active Members</div><div class="sv" id="statMembers">—</div><div class="ss">with steps recorded</div></div>
    <div class="stat"><div class="sl">Daily Goal</div><div class="sv">{DAILY_GOAL:,}</div><div class="ss">steps / person</div></div>
    <div class="stat"><div class="sl">Challenge Day</div><div class="sv" id="statDay">—</div><div class="ss" id="statDaysLeft">—</div></div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('dashboard')">📊 Dashboard</button>
    <button class="tab" onclick="switchTab('history')">📅 Full History</button>
  </div>

  <!-- DASHBOARD TAB -->
  <div id="tab-dashboard" class="tab-content active">
    <div class="two-col">
      <div class="card">
        <h2>🏆 Team Standings</h2>
        <div id="teamStandings"></div>
      </div>
      <div class="card">
        <h2>📈 Cumulative Steps by Team</h2>
        <div class="chart-wrap"><canvas id="lineChart"></canvas></div>
      </div>
    </div>

    <div class="full-card">
      <h2>👟 Individual Leaderboard</h2>
      <table>
        <thead><tr>
          <th>#</th><th>Member</th><th>Team</th>
          <th>Steps</th><th>Activity Steps</th><th>Total Steps ↕</th><th>Daily Avg</th><th>Active Days</th><th>Goal Hit Days</th>
        </tr></thead>
        <tbody id="leaderBody"></tbody>
      </table>
    </div>

    <div class="day-card">
      <h2>📅 Day Breakdown</h2>
      <div class="day-controls">
        <label>Select day:</label>
        <select id="dayPick" onchange="renderDay(this.value)"></select>
      </div>
      <div id="dayDetail"></div>
    </div>
  </div>

  <!-- HISTORY TAB -->
  <div id="tab-history" class="tab-content">
    <div class="full-card">
      <h2>📋 Full Step History — All Members × All Days</h2>
      <p style="font-size:12px;color:#64748b;margin-bottom:14px;">
        Green = met {DAILY_GOAL:,} step goal &nbsp;·&nbsp; Red = below goal &nbsp;·&nbsp; Grey = no data
      </p>
      <div class="hist-controls">
        <label>Filter by team:</label>
        <select id="histTeamFilter" onchange="renderHistory()">
          <option value="all">All Teams</option>
          {''.join(f'<option value="{t["id"]}">{t["short"]}</option>' for t in TEAMS)}
        </select>
      </div>
      <div class="scroll-wrap">
        <table class="hist-table" id="histTable">
          <thead id="histHead"></thead>
          <tbody id="histBody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
const DATA = {data_js};
const TEAMS_CFG = {teams_js};
const CHALLENGE_START = '{CHALLENGE_START}';
const CHALLENGE_END   = '{CHALLENGE_END}';
const DAILY_GOAL      = {DAILY_GOAL};

let lineChart = null;

function fmt(n) {{ return (n||0).toLocaleString(); }}
function dateLabel(d) {{
  return new Date(d+'T12:00:00').toLocaleDateString('en-US',{{month:'short',day:'numeric'}});
}}
function allDays() {{
  const days=[]; const d=new Date(CHALLENGE_START+'T00:00:00');
  const end=new Date(CHALLENGE_END+'T00:00:00');
  while(d<=end){{ days.push(d.toISOString().split('T')[0]); d.setDate(d.getDate()+1); }}
  return days;
}}
function todayStr() {{ return new Date().toISOString().split('T')[0]; }}
function challengeDay() {{
  const diff=Math.floor((new Date(todayStr())-new Date(CHALLENGE_START+'T00:00:00'))/86400000)+1;
  return Math.max(1,Math.min(diff,29));
}}
function daysLeft() {{
  const diff=Math.floor((new Date(CHALLENGE_END+'T00:00:00')-new Date(todayStr()))/86400000);
  return Math.max(0,diff);
}}
function memberTotal(m) {{
  let steps=0,acts=0,days=0;
  for(const [date,v] of Object.entries(m.dailyData||{{}})){{
    if(date<CHALLENGE_START||date>CHALLENGE_END) continue;
    steps+=v.steps||0; acts+=v.activities||0;
    if(((v.steps||0)+(v.activities||0))>0) days++;
  }}
  const total=steps+acts;
  const goalDays=Object.entries(m.dailyData||{{}}).filter(([d,v])=>d>=CHALLENGE_START&&d<=CHALLENGE_END&&((v.steps||0)+(v.activities||0))>=DAILY_GOAL).length;
  return {{steps,acts,total,days,avg:days?Math.round(total/days):0,goalDays}};
}}
function teamTotal(team) {{
  let steps=0,acts=0,total=0;
  for(const m of team.members){{ const t=memberTotal(m); steps+=t.steps; acts+=t.acts; total+=t.total; }}
  return {{steps,acts,total,mc:team.members.length,avg:team.members.length?Math.round(total/team.members.length):0}};
}}
function teamCfg(id) {{
  return TEAMS_CFG.find(t=>t.id===id)||{{name:'Unknown',short:'?',color:'#888'}};
}}

function switchTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  event.target.classList.add('active');
  if(name==='history') renderHistory();
}}

function init() {{
  // Header
  const cd=challengeDay(), dl=daysLeft();
  document.getElementById('subhead').textContent=
    `May 18 – June 15, 2026 · Day ${{cd}} of 29 · ${{dl}} day${{dl===1?'':'s'}} remaining`;
  if(DATA.lastUpdated) {{
    document.getElementById('lastSync').textContent=
      new Date(DATA.lastUpdated).toLocaleString('en-US',{{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}});
  }}

  // Stats
  let grand=0, activeMem=0;
  DATA.teams.forEach(team=>{{
    const t=teamTotal(team); grand+=t.total;
    team.members.forEach(m=>{{ if(memberTotal(m).total>0) activeMem++; }});
  }});
  document.getElementById('statSteps').textContent=fmt(grand);
  document.getElementById('statMembers').textContent=activeMem;
  document.getElementById('statDay').textContent=`${{cd}} / 29`;
  document.getElementById('statDaysLeft').textContent=`${{dl}} day${{dl===1?'':'s'}} remaining`;

  // Team standings
  const tStats=DATA.teams.map(team=>{{
    const cfg=teamCfg(team.id);
    return {{...teamTotal(team), cfg, team}};
  }}).sort((a,b)=>b.total-a.total);
  const maxT=tStats[0]?.total||1;
  const medals=['🥇','🥈','🥉','4️⃣'];
  document.getElementById('teamStandings').innerHTML=tStats.map((t,i)=>{{
    const pct=Math.round(t.total/maxT*100);
    return `<div class="team-row">
      <div class="rank">${{medals[i]||i+1}}</div>
      <div class="dot" style="background:${{t.cfg.color}}"></div>
      <div class="ti">
        <div class="tn" title="${{t.cfg.name}}">${{t.cfg.short}}</div>
        <div class="tm">${{t.mc}} members</div>
        <div class="bar-bg"><div class="bar-fg" style="width:${{pct}}%;background:${{t.cfg.color}}"></div></div>
      </div>
      <div class="ts">
        <div class="steps">${{fmt(t.total)}}</div>
        <div class="avg">${{fmt(t.avg)}} avg/member</div>
      </div>
    </div>`;
  }}).join('');

  // Individual leaderboard
  const allM=[];
  DATA.teams.forEach(team=>{{
    const cfg=teamCfg(team.id);
    team.members.forEach(m=>{{
      allM.push({{...m,...memberTotal(m),cfg}});
    }});
  }});
  allM.sort((a,b)=>b.total-a.total);
  const maxM=allM[0]?.total||1;
  document.getElementById('leaderBody').innerHTML=allM.map((m,i)=>{{
    const bp=Math.round(m.total/maxM*100);
    return `<tr>
      <td style="color:#94a3b8;font-weight:700">${{i+1}}</td>
      <td><strong>${{m.name}}</strong></td>
      <td><span class="badge" style="background:${{m.cfg.color}}"></span>${{m.cfg.short}}</td>
      <td style="color:#64748b;font-size:12px">${{fmt(m.steps)}}</td>
      <td style="color:#64748b;font-size:12px">${{fmt(m.acts)}}</td>
      <td>
        <strong>${{fmt(m.total)}}</strong>
        <span style="display:inline-block;vertical-align:middle;margin-left:6px;background:#f1f5f9;border-radius:2px;height:5px;width:80px;overflow:hidden">
          <span style="display:block;background:${{m.cfg.color}};width:${{bp}}%;height:5px"></span>
        </span>
      </td>
      <td>${{fmt(m.avg)}}</td>
      <td>${{m.days}}</td>
      <td>${{m.goalDays}}</td>
    </tr>`;
  }}).join('');

  // Day selector
  const days=allDays();
  const today=todayStr();
  const pastDays=days.filter(d=>d<=today);
  const sel=document.getElementById('dayPick');
  sel.innerHTML=pastDays.slice().reverse().map(d=>
    `<option value="${{d}}">${{new Date(d+'T12:00:00').toLocaleDateString('en-US',{{weekday:'short',month:'short',day:'numeric'}})}}</option>`
  ).join('');
  if(pastDays.length) renderDay(pastDays[pastDays.length-1]);

  // Chart
  buildChart(pastDays);
}}

function renderDay(day) {{
  if(!day) return;
  const rows=[];
  DATA.teams.forEach(team=>{{
    const cfg=teamCfg(team.id);
    team.members.forEach(m=>{{
      const d=m.dailyData?.[day];
      const steps=d?.steps||0, acts=d?.activities||0;
      rows.push({{name:m.name,cfg,steps,acts,total:steps+acts}});
    }});
  }});
  rows.sort((a,b)=>b.total-a.total);
  const maxS=rows[0]?.total||1;
  const dayLabel=new Date(day+'T12:00:00').toLocaleDateString('en-US',{{weekday:'long',month:'long',day:'numeric',year:'numeric'}});
  document.getElementById('dayDetail').innerHTML=`
    <p style="font-size:12px;color:#64748b;margin-bottom:12px">${{dayLabel}}</p>
    <table>
      <thead><tr><th>#</th><th>Member</th><th>Team</th><th>Steps</th><th>Activity Steps</th><th>Total Steps</th><th>vs Goal</th></tr></thead>
      <tbody>
        ${{rows.map((r,i)=>{{
          const pct=Math.min(100,Math.round(r.total/DAILY_GOAL*100));
          const col=pct>=100?'#10b981':pct>=70?'#f97316':'#ef4444';
          const bp=Math.round(r.total/maxS*80);
          return `<tr>
            <td style="color:#94a3b8;font-weight:700">${{i+1}}</td>
            <td><strong>${{r.name}}</strong></td>
            <td><span class="badge" style="background:${{r.cfg.color}}"></span>${{r.cfg.short}}</td>
            <td style="color:#64748b">${{fmt(r.steps)}}</td>
            <td style="color:#64748b">${{fmt(r.acts)}}</td>
            <td><strong>${{fmt(r.total)}}</strong> <span style="display:inline-block;vertical-align:middle;margin-left:4px;background:#f1f5f9;border-radius:2px;height:4px;width:${{bp}}px"></span></td>
            <td style="color:${{col}};font-weight:600">${{pct}}%</td>
          </tr>`;
        }}).join('')}}
      </tbody>
    </table>`;
}}

function buildChart(pastDays) {{
  const datasets=TEAMS_CFG.map(cfg=>{{
    const team=DATA.teams.find(t=>t.id===cfg.id);
    let cum=0;
    const pts=pastDays.map(day=>{{
      if(team) team.members.forEach(m=>{{cum+=(m.dailyData?.[day]?.steps||0)+(m.dailyData?.[day]?.activities||0);}});
      return cum;
    }});
    return {{label:cfg.short,data:pts,borderColor:cfg.color,backgroundColor:'transparent',borderWidth:2.5,tension:0.3,pointRadius:pastDays.length>10?2:3}};
  }});
  if(lineChart) lineChart.destroy();
  const ctx=document.getElementById('lineChart').getContext('2d');
  lineChart=new Chart(ctx,{{
    type:'line',
    data:{{labels:pastDays.map(d=>d.slice(5)),datasets}},
    options:{{
      responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{position:'bottom',labels:{{boxWidth:12,font:{{size:11}},padding:8}}}}}},
      scales:{{
        x:{{grid:{{display:false}},ticks:{{font:{{size:10}},maxTicksLimit:10}}}},
        y:{{grid:{{color:'#f1f5f9'}},ticks:{{font:{{size:10}},callback:v=>v>=1000?(v/1000).toFixed(0)+'k':v}}}}
      }}
    }}
  }});
}}

function renderHistory() {{
  const teamFilter=document.getElementById('histTeamFilter').value;
  const days=allDays();
  const today=todayStr();
  const pastDays=days.filter(d=>d<=today);

  // Build member list
  const rows=[];
  DATA.teams.forEach(team=>{{
    if(teamFilter!=='all' && team.id!==parseInt(teamFilter)) return;
    const cfg=teamCfg(team.id);
    team.members.forEach(m=>{{
      const tot=memberTotal(m);
      rows.push({{m,cfg,tot}});
    }});
  }});
  rows.sort((a,b)=>b.tot.total-a.tot.total);

  // Header
  document.getElementById('histHead').innerHTML=`<tr>
    <th>#</th><th>Member</th><th>Team</th>
    ${{pastDays.map(d=>`<th title="${{new Date(d+'T12:00:00').toLocaleDateString('en-US',{{weekday:'long',month:'long',day:'numeric'}})}}">${{d.slice(5)}}</th>`).join('')}}
    <th class="total-col">Total</th><th>Avg/Day</th>
  </tr>`;

  // Body
  document.getElementById('histBody').innerHTML=rows.map((row,i)=>{{
    const cells=pastDays.map(day=>{{
      const s=row.m.dailyData?.[day]?.steps||0;
      const a=row.m.dailyData?.[day]?.activities||0;
      const t=s+a;
      if(t===0) return `<td><span class="cell-zero">—</span></td>`;
      const cls=t>=DAILY_GOAL?'cell-hit':'cell-miss';
      const tip=` title="Steps: ${{s.toLocaleString()}} | Activity Steps: ${{a.toLocaleString()}} | Total: ${{t.toLocaleString()}}"`;
      return `<td${{tip}}><span class="${{cls}}">${{t>=1000?(t/1000).toFixed(1)+'k':t}}</span></td>`;
    }}).join('');
    return `<tr>
      <td style="color:#94a3b8;font-weight:700">${{i+1}}</td>
      <td><strong>${{row.m.name}}</strong></td>
      <td><span class="badge" style="background:${{row.cfg.color}}"></span>${{row.cfg.short}}</td>
      ${{cells}}
      <td class="total-col">${{fmt(row.tot.total)}}</td>
      <td style="color:#64748b">${{fmt(row.tot.avg)}}</td>
    </tr>`;
  }}).join('');
}}

init();
</script>
</body>
</html>"""


def push_to_github(html_content):
    """Push HTML to GitHub via Contents API."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Get current file SHA (needed for updates; None if file doesn't exist yet)
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    content_b64 = base64.b64encode(html_content.encode("utf-8")).decode()
    today = date.today().isoformat()
    payload = {
        "message": f"Update dashboard {today}",
        "content": content_b64,
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={**headers, "Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    return result.get("content", {}).get("html_url", PAGES_URL)


def main():
    print("🌐 Walking Challenge — GitHub Pages Publisher")
    print(f"   Data file : {DATA_FILE}")
    print(f"   Repo      : {GITHUB_REPO}")

    if not os.path.exists(DATA_FILE):
        print("❌ walking_data.json not found — run sync first")
        sys.exit(1)

    with open(DATA_FILE) as f:
        data = json.load(f)

    teams_count   = len(data.get("teams", []))
    members_count = sum(len(t.get("members", [])) for t in data.get("teams", []))
    print(f"   Data      : {teams_count} teams, {members_count} members")

    print("⚙️  Generating dashboard HTML...")
    html = generate_html(data)
    size_kb = len(html.encode("utf-8")) / 1024
    print(f"   HTML size : {size_kb:.1f} KB")

    print("🚀 Pushing to GitHub Pages...")
    push_to_github(html)

    print(f"\n✅ Live at: {PAGES_URL}")
    print("   (GitHub Pages may take ~60 seconds to refresh after first publish)")


if __name__ == "__main__":
    main()
