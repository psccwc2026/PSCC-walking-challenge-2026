#!/usr/bin/env python3
"""
Walking Challenge 2026 — Be Well Auto Sync (browser-free)
Logs in to Be Well API directly, fetches step data for all 4 teams,
merges into walking_data.json, then pushes dashboard to GitHub Pages.
"""

import json, urllib.request, urllib.parse, urllib.error, os, sys, subprocess
from datetime import datetime, date, timezone

WORKSPACE   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE   = os.path.join(WORKSPACE, "walking_data.json")
CONFIG_FILE = os.path.join(WORKSPACE, "bewell_config.json")

TEAMS = [
    {"id": 132544, "name": "Accounting Walkaholics",        "color": "#10b981"},
    {"id": 132626, "name": "PSCC Build is Too Fit to Quit", "color": "#f97316"},
    {"id": 132610, "name": "BusOps Walking Deadlines",      "color": "#6366f1"},
    {"id": 132609, "name": "Fast and Fully Compliant",      "color": "#eab308"},
]

CHALLENGE_START = "2026-05-18"
CHALLENGE_END   = "2026-06-15"
API_BASE        = "https://apiv3.walkertracker.com"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://roberthalf.walkertracker.com",
    "Referer": "https://roberthalf.walkertracker.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def load_config():
    # Prefer environment variables (GitHub Actions), fall back to local config file
    env_user = os.environ.get("BEWELL_USERNAME")
    env_pass = os.environ.get("BEWELL_PASSWORD")
    if env_user and env_pass:
        return {"username": env_user, "password": env_pass}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def get_token(config):
    """Log in to Be Well API and return a fresh Bearer token."""
    payload = json.dumps({
        "username": config["username"],
        "password": config["password"],
    }).encode()
    req = urllib.request.Request(
        f"{API_BASE}/login",
        data=payload,
        headers=HEADERS_BASE,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    token = data.get("token")
    if not token:
        raise RuntimeError(f"Login failed — no token in response: {data}")
    return token


def fetch_team_roster(team_id, token):
    """Fetch all team members regardless of whether they have step data."""
    url = f"{API_BASE}/teams/{team_id}/members?perPage=50"
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_team_data(team_id, token, start_date, end_date):
    """Fetch member step data for one team."""
    params = urllib.parse.urlencode({
        "perPage": "30",
        "teamId": str(team_id),
        "startDate": start_date,
        "endDate": end_date,
    })
    url = f"{API_BASE}/teams/{team_id}/members-step-data?{params}"
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_journal_data(token, start_date, end_date):
    """Fetch all journal entries (with photos + activity text) for the program."""
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    # Build lookup: {(memberId, "YYYY-MM-DD"): {photo, activityTexts, journalText}}
    journal_lookup = {}
    page = 1
    while True:
        params = urllib.parse.urlencode({
            "startDate": start_date,
            "endDate": end_date,
            "perPage": "50",
            "page": str(page),
        })
        url = f"{API_BASE}/programs/3270/journals?{params}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        entries = result.get("data") or []
        if not entries:
            break
        for entry in entries:
            member_id = entry.get("memberId")
            date_str  = entry.get("created")  # "YYYY-MM-DD"
            if not member_id or not date_str:
                continue
            key = (member_id, date_str)
            activity_texts = [a.get("text", "") for a in (entry.get("activities") or []) if a.get("text")]
            journal_lookup[key] = {
                "photo":         entry.get("imageLarge") or entry.get("image") or "",
                "activityTexts": activity_texts,
                "journalText":   entry.get("text") or "",
            }
        page += 1
        if page > 20:  # safety cap
            break
    return journal_lookup


def load_existing():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"lastUpdated": None, "teams": []}


def merge_data(existing, team_def, roster_result, step_result):
    """Merge full roster + step data into the existing data structure."""
    team_entry = next((t for t in existing["teams"] if t["id"] == team_def["id"]), None)
    if team_entry is None:
        team_entry = {
            "id": team_def["id"],
            "name": team_def["name"],
            "color": team_def["color"],
            "members": []
        }
        existing["teams"].append(team_entry)

    # Step 1: ensure every roster member exists (even with zero steps)
    for roster_member in (roster_result.get("data") or []):
        name = f"{roster_member.get('firstName','')} {roster_member.get('lastName','')}".strip()
        username = roster_member.get("username", "")
        member_id = roster_member.get("id")
        m_entry = next((m for m in team_entry["members"] if m["username"] == username), None)
        if m_entry is None:
            m_entry = {"name": name, "username": username, "memberId": member_id, "dailyData": {}}
            team_entry["members"].append(m_entry)
        else:
            if member_id and not m_entry.get("memberId"):
                m_entry["memberId"] = member_id

    # Step 2: layer in step data for those who have it
    for api_member in (step_result.get("data") or []):
        name = f"{api_member.get('firstName','')} {api_member.get('lastName','')}".strip()
        username = api_member.get("username", "")
        member_id = api_member.get("id")

        m_entry = next((m for m in team_entry["members"] if m["username"] == username), None)
        if m_entry is None:
            m_entry = {"name": name, "username": username, "memberId": member_id, "dailyData": {}}
            team_entry["members"].append(m_entry)
        else:
            if member_id and not m_entry.get("memberId"):
                m_entry["memberId"] = member_id

        for day in (api_member.get("stepData") or []):
            d = day.get("created")  # "YYYY-MM-DD"
            if d:
                m_entry["dailyData"][d] = {
                    "steps": day.get("steps", 0),
                    "activities": day.get("activities", 0)
                }


def main(start_date=None, end_date=None):
    print("📡 Walking Challenge Sync — browser-free")
    print(f"   Workspace: {WORKSPACE}")

    config = load_config()

    if start_date is None:
        start_date = f"{CHALLENGE_START}T00:00:00.000Z"
    if end_date is None:
        today = date.today().isoformat()
        end_date = f"{today}T23:59:59.999Z"
    print(f"   Date range: {start_date[:10]} → {end_date[:10]}")

    # Authenticate
    print("🔑 Logging in to Be Well API...")
    token = get_token(config)
    print(f"   Token obtained ({len(token)} chars)")

    # Load existing data
    existing = load_existing()
    print(f"   Existing data: {len(existing.get('teams', []))} teams")

    # Fetch and merge step data
    for team_def in TEAMS:
        print(f"   Fetching: {team_def['name']} (id={team_def['id']})...", end="", flush=True)
        try:
            roster = fetch_team_roster(team_def["id"], token)
            steps  = fetch_team_data(team_def["id"], token, start_date, end_date)
            merge_data(existing, team_def, roster, steps)
            print(f" ✓ {len(roster.get('data', []))} members ({len(steps.get('data', []))} with steps)")
        except Exception as e:
            print(f" ✗ ERROR: {e}")

    # Fetch journal data (photos + activity text) and merge into daily entries
    print("   Fetching journal entries (photos + activity text)...", end="", flush=True)
    try:
        journal_lookup = fetch_journal_data(token, start_date, end_date)
        photo_count = sum(1 for v in journal_lookup.values() if v.get("photo"))
        # Layer journal data into each member's daily records
        for team in existing["teams"]:
            for member in team["members"]:
                member_id = member.get("memberId")
                if not member_id:
                    continue
                for date_str, day_data in member["dailyData"].items():
                    key = (member_id, date_str)
                    if key in journal_lookup:
                        j = journal_lookup[key]
                        if j.get("photo"):
                            day_data["photo"] = j["photo"]
                        if j.get("activityTexts"):
                            day_data["activityTexts"] = j["activityTexts"]
                        if j.get("journalText"):
                            day_data["journalText"] = j["journalText"]
        print(f" ✓ {len(journal_lookup)} entries ({photo_count} with photos)")
    except Exception as e:
        print(f" ✗ ERROR: {e}")

    # Write updated data
    existing["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    with open(DATA_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    total_members = sum(len(t.get("members", [])) for t in existing["teams"])
    print(f"\n✅ walking_data.json updated")
    print(f"   Teams: {len(existing['teams'])} | Members: {total_members}")

    # Push to GitHub Pages
    print("\n🚀 Pushing dashboard to GitHub Pages...")
    push_script = os.path.join(WORKSPACE, "push_to_github.py")
    result = subprocess.run(
        [sys.executable, push_script],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"   ⚠️  GitHub push error: {result.stderr.strip()}")


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else None
    e = sys.argv[2] if len(sys.argv) > 2 else None
    main(s, e)
