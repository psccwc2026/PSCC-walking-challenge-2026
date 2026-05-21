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


JOURNAL_CACHE_DIR = os.path.join(WORKSPACE, "journal_cache")


def fetch_day_journal(token, date_str):
    """Fetch ALL journal entries for one specific calendar day.

    For a single day there are ~475 entries across 199 program teams = ~10 pages.
    This replaces the rolling 3-day window approach: past days are fetched once
    and sealed; only today needs a fresh fetch each sync run.

    Returns: {str(memberId): {photo, activityTexts, journalText}}
    """
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    start_date = f"{date_str}T00:00:00.000Z"
    end_date   = f"{date_str}T23:59:59.999Z"

    members = {}
    page = 1
    while True:
        params = urllib.parse.urlencode({
            "startDate": start_date,
            "endDate":   end_date,
            "perPage":   "50",
            "page":      str(page),
        })
        url = f"{API_BASE}/programs/3270/journals?{params}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        entries = result.get("data") or []
        if not entries:
            break
        for entry in entries:
            mid = str(entry.get("memberId", ""))
            if not mid:
                continue
            activity_texts = [a.get("text", "") for a in (entry.get("activities") or []) if a.get("text")]
            existing = members.get(mid, {})
            members[mid] = {
                "photo":         entry.get("imageLarge") or entry.get("image") or existing.get("photo", ""),
                "activityTexts": activity_texts or existing.get("activityTexts", []),
                "journalText":   entry.get("text") or existing.get("journalText", ""),
            }
        page += 1
        if page > 25:  # 25 pages × 50 = 1,250 — well above any single day's volume
            break
    return members


def load_day_cache(date_str):
    """Load a cached journal day. Returns the full cache dict, or None if not found."""
    path = os.path.join(JOURNAL_CACHE_DIR, f"{date_str}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_day_cache(date_str, members, sealed):
    """Write journal data for one day to journal_cache/YYYY-MM-DD.json."""
    os.makedirs(JOURNAL_CACHE_DIR, exist_ok=True)
    path = os.path.join(JOURNAL_CACHE_DIR, f"{date_str}.json")
    with open(path, "w") as f:
        json.dump({"date": date_str, "sealed": sealed, "members": members}, f, indent=2)
    return path


def build_journal_lookup_from_cache():
    """Read all cache files and return lookup: {(str_mid, date_str): {photo, activityTexts, journalText}}"""
    lookup = {}
    if not os.path.exists(JOURNAL_CACHE_DIR):
        return lookup
    for fname in sorted(os.listdir(JOURNAL_CACHE_DIR)):
        if not fname.endswith(".json"):
            continue
        date_str = fname[:-5]
        with open(os.path.join(JOURNAL_CACHE_DIR, fname)) as f:
            cache = json.load(f)
        for mid_str, jdata in cache.get("members", {}).items():
            lookup[(mid_str, date_str)] = jdata
    return lookup


def sync_journal_cache(token):
    """Ensure every challenge day up to today has a cache file.

    - Past days (before today): fetch once and mark sealed=True. Never re-fetched.
    - Today: always re-fetch and save with sealed=False (data still accumulating).

    Returns list of cache file paths that were created or updated this run.
    """
    from datetime import timedelta
    today_d   = date.today()
    today_str = today_d.isoformat()
    start_d   = date.fromisoformat(CHALLENGE_START)
    end_d     = date.fromisoformat(CHALLENGE_END)

    # All challenge days from start up to today (inclusive)
    days = []
    d = start_d
    while d <= min(today_d, end_d):
        days.append(d.isoformat())
        d += timedelta(days=1)

    updated_files = []

    for day in days:
        if day < today_str:
            # Past day — only fetch if not already sealed
            cache = load_day_cache(day)
            if cache and cache.get("sealed"):
                continue  # Already done, skip
            print(f"   Sealing journal for {day}...", end="", flush=True)
            members = fetch_day_journal(token, day)
            save_day_cache(day, members, sealed=True)
            updated_files.append(f"journal_cache/{day}.json")
            photos = sum(1 for v in members.values() if v.get("photo"))
            print(f" ✓ {len(members)} members, {photos} photos (sealed)")
        else:
            # Today — always refresh (activities accumulate through the day)
            print(f"   Fetching today's journal ({day})...", end="", flush=True)
            members = fetch_day_journal(token, day)
            save_day_cache(day, members, sealed=False)
            updated_files.append(f"journal_cache/{day}.json")
            photos = sum(1 for v in members.values() if v.get("photo"))
            print(f" ✓ {len(members)} members, {photos} photos")

    return updated_files


CHALLENGE_ID    = 90886
PROGRAM_TEAMS   = 199   # teams in "2026 Global Activity Challenge (Steps + Activities)"


def fetch_challenge_rankings(token):
    """
    Fetch the full paginated global challenge leaderboard and return:
      rankings: { teamId: {"position": int, "tally": int, "outOf": int} }
      total:    int  (total teams in challenge)
    Uses paginated=1 to get proper page-by-page results (199 teams, 20 pages).
    """
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    OUR_TEAM_IDS = {t["id"] for t in TEAMS}
    rankings = {}
    total = PROGRAM_TEAMS

    for page in range(1, 25):
        params = urllib.parse.urlencode({
            "page": str(page), "perPage": "10",
            "paginated": "1", "showUserPage": "0", "organizationLeaderboard": "0",
        })
        url = f"{API_BASE}/challenges/{CHALLENGE_ID}/leaderboard?{params}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        inner      = result.get("data", {})
        entries    = inner.get("data", []) if isinstance(inner, dict) else []
        pagination = inner.get("pagination", {}) if isinstance(inner, dict) else {}
        total      = pagination.get("total", total)

        if not entries:
            break

        for e in entries:
            tid = e.get("id")
            if tid in OUR_TEAM_IDS:
                rankings[tid] = {
                    "position": e.get("position"),
                    "tally":    e.get("tally"),
                    "outOf":    total,
                }

        # Stop as soon as we've found all 4 teams — no need to scan further
        if len(rankings) == len(TEAMS):
            break

        if not pagination.get("has_more", True):
            break

    return rankings, total


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
                # Preserve any existing journal fields (photo, activityTexts, journalText)
                # so they are not wiped out when step data is refreshed each sync
                existing_day = m_entry["dailyData"].get(d, {})
                m_entry["dailyData"][d] = {
                    "steps": day.get("steps", 0),
                    "activities": day.get("activities", 0),
                    **{k: existing_day[k] for k in ("photo", "activityTexts", "journalText") if k in existing_day}
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

    # Journal cache: seal past days once, refresh today each run
    print("📓 Syncing journal cache...")
    try:
        updated_cache_files = sync_journal_cache(token)
    except Exception as e:
        print(f"   ✗ Journal cache ERROR: {e}")
        updated_cache_files = []

    # Build full journal lookup from all cache files and apply to member dailyData
    journal_lookup = build_journal_lookup_from_cache()
    photo_count = 0
    for team in existing["teams"]:
        for member in team["members"]:
            mid_str = str(member.get("memberId", ""))
            if not mid_str:
                continue
            for date_str, day_data in member["dailyData"].items():
                j = journal_lookup.get((mid_str, date_str))
                if j:
                    if j.get("photo"):
                        day_data["photo"] = j["photo"]
                        photo_count += 1
                    if j.get("activityTexts"):
                        day_data["activityTexts"] = j["activityTexts"]
                    if j.get("journalText"):
                        day_data["journalText"] = j["journalText"]
    print(f"   Applied journal data: {len(journal_lookup)} member-day entries, {photo_count} photos")

    # Fetch global challenge rankings for all 4 teams (full paginated scan)
    print("   Fetching global challenge rankings...", end="", flush=True)
    try:
        rankings, total_teams = fetch_challenge_rankings(token)
        existing["challengeRankings"] = rankings
        print(f" ✓ found {len(rankings)}/4 teams across {total_teams} total")
        for team in existing["teams"]:
            r = rankings.get(team["id"], {})
            pos = r.get("position", "?")
            tally = r.get("tally", 0)
            print(f"      {team['name']}: #{pos} / {total_teams} (tally={tally})")
    except Exception as e:
        print(f" ✗ ERROR: {e}")

    # Write updated data
    existing["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    with open(DATA_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    total_members = sum(len(t.get("members", [])) for t in existing["teams"])
    print(f"\n✅ walking_data.json updated")
    print(f"   Teams: {len(existing['teams'])} | Members: {total_members}")

    # Push to GitHub Pages (pass updated cache files so push script only pushes what changed)
    print("\n🚀 Pushing dashboard to GitHub Pages...")
    push_script = os.path.join(WORKSPACE, "push_to_github.py")
    env = {**os.environ, "JOURNAL_CACHE_UPDATED": ",".join(updated_cache_files)}
    result = subprocess.run(
        [sys.executable, push_script],
        capture_output=True, text=True, env=env
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"   ⚠️  GitHub push error: {result.stderr.strip()}")


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else None
    e = sys.argv[2] if len(sys.argv) > 2 else None
    main(s, e)
