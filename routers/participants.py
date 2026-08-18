from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from database import supabase, templates
from routers.auth import require_team

router = APIRouter(tags=["Participants"])

@router.get("/", response_class=HTMLResponse)
async def home_dashboard(request: Request, team: dict = Depends(require_team)):
    teams_res = supabase.table("teams").select("id, nation_name, participant_name, flag_emoji, shots_owed").order("nation_name").execute()
    teams = teams_res.data if teams_res.data else []
    
    # Fetch feature toggles from your app_settings table using your exact schema (key, is_active)
    settings_res = supabase.table("app_settings").select("key, is_active").execute()
    settings = {s["key"]: s["is_active"] for s in settings_res.data} if settings_res.data else {}
    
    treasure_visible = settings.get("treasure_hunt_active", False)
    escape_visible = settings.get("puzzle_room_active", False)

    results_res = supabase.table("event_results").select("team_id, medal_type, points").execute()
    results = results_res.data if results_res.data else []
    
    # Fetch shot history for this specific team
    shots_history_res = supabase.table("shots_log").select("amount, reason").eq("team_id", team["id"]).order("recorded_at", desc=True).limit(5).execute()
    shots_history = shots_history_res.data if shots_history_res.data else []
    
    standings = {}
    for t in teams:
        # Determine correct flag URL directly in Python to prevent template lookup mismatches
        code = (t.get("flag_emoji") or "").lower().strip()
        name = (t.get("nation_name") or "").lower().strip()
        
        if 'wales' in name or code == 'wls' or code == 'gb-wls':
            flag_url = 'https://flagcdn.com/w640/gb-wls.png'
        elif 'austria' in name or code == 'at':
            flag_url = 'https://flagcdn.com/w640/at.png'
        elif 'ireland' in name or code == 'ie':
            flag_url = 'https://flagcdn.com/w640/ie.png'
        elif 'united states' in name or 'usa' in name or code == 'us':
            flag_url = 'https://flagcdn.com/w640/us.png'
        elif 'china' in name or code == 'cn' or code == 'ch':
            flag_url = 'https://flagcdn.com/w640/cn.png'
        elif 'japan' in name or code == 'jp':
            flag_url = 'https://flagcdn.com/w640/jp.png'
        elif 'germany' in name or code == 'de':
            flag_url = 'https://flagcdn.com/w640/de.png'
        elif 'canada' in name or code == 'ca':
            flag_url = 'https://flagcdn.com/w640/ca.png'
        elif 'brazil' in name or code == 'br':
            flag_url = 'https://flagcdn.com/w640/br.png'
        else:
            flag_url = 'https://flagcdn.com/w640/gb.png'

        standings[t["id"]] = {
            "nation_name": t["nation_name"],
            "flag_emoji": t["flag_emoji"],
            "flag_url": flag_url,
            "gold": 0,
            "silver": 0,
            "bronze": 0,
            "total_points": 0
        }
        
    for r in results:
        tid = r["team_id"]
        if tid in standings:
            medal = r["medal_type"]
            if medal == "gold":
                standings[tid]["gold"] += 1
            elif medal == "silver":
                standings[tid]["silver"] += 1
            elif medal == "bronze":
                standings[tid]["bronze"] += 1
            
            if r["points"]:
                standings[tid]["total_points"] += r["points"]

    sorted_standings = sorted(
        standings.values(), 
        key=lambda x: (x["total_points"], x["gold"], x["silver"], x["bronze"]), 
        reverse=True
    )

    # Fetch medal results for the rolling news ticker
    activity_res = supabase.table("event_results") \
        .select("event_name, medal_type, recorded_at, teams(nation_name, flag_emoji)") \
        .neq("medal_type", "none") \
        .order("recorded_at", desc=True) \
        .limit(6) \
        .execute()
    
    # Fetch recent shot forfeits for the rolling news ticker
    shots_res = supabase.table("shots_log") \
        .select("amount, reason, recorded_at, teams(nation_name, flag_emoji)") \
        .order("recorded_at", desc=True) \
        .limit(6) \
        .execute()

    # Combine and format news ticker items
    news_items = []
    for act in (activity_res.data or []):
        news_items.append({
            "type": "medal",
            "text": f"{act['teams']['flag_emoji']} {act['teams']['nation_name']} won {act['medal_type'].upper()} in {act['event_name']}!",
            "recorded_at": act["recorded_at"]
        })
    for shot in (shots_res.data or []):
        news_items.append({
            "type": "shot",
            "text": f"🍻 {shot['teams']['flag_emoji']} {shot['teams']['nation_name']} penalized +{shot['amount']} shots! Reason: {shot['reason']}",
            "recorded_at": shot["recorded_at"]
        })
    
    # Sort combined feed by timestamp descending
    news_items = sorted(news_items, key=lambda x: x["recorded_at"], reverse=True)[:10]

    template = templates.get_template("index.html")
    html_content = template.render({
        "request": request, 
        "team": team, 
        "teams": teams,
        "standings": sorted_standings,
        "activities": news_items,
        "shots_history": shots_history,
        "treasure_visible": treasure_visible,
        "escape_visible": escape_visible
    })
    return HTMLResponse(content=html_content)

@router.post("/var/submit")
async def submit_var(target_team_id: str = Form(...), incident: str = Form(...), team: dict = Depends(require_team)):
    # Get target team details to make the incident description clear
    target_res = supabase.table("teams").select("nation_name, participant_name").eq("id", target_team_id).execute()
    target_info = target_res.data[0] if target_res.data else {"nation_name": "Unknown", "participant_name": "Athlete"}
    
    formatted_incident = f"[Target: {target_info['nation_name']} ({target_info['participant_name']})] {incident}"
    
    supabase.table("var_submissions").insert({
        "team_id": target_team_id,
        "incident_description": formatted_incident,
        "status": "pending"
    }).execute()
    return RedirectResponse(url="/?message=VAR+submitted", status_code=303)

@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, team: dict = Depends(require_team)):
    # Fetch feature toggles so the navbar links display correctly on the events page too
    settings_res = supabase.table("app_settings").select("key, is_active").execute()
    settings = {s["key"]: s["is_active"] for s in settings_res.data} if settings_res.data else {}
    
    treasure_visible = settings.get("treasure_hunt_active", False)
    escape_visible = settings.get("puzzle_room_active", False)

    results_res = supabase.table("event_results").select("event_name, points, medal_type, teams(nation_name, flag_emoji)").order("points", desc=True).execute()
    results = results_res.data if results_res.data else []

    event_results_map = {}
    for r in results:
        ev_name = r["event_name"]
        if ev_name not in event_results_map:
            event_results_map[ev_name] = []
        event_results_map[ev_name].append(r)

    template = templates.get_template("events.html")
    html_content = template.render({
        "request": request, 
        "team": team,
        "event_results_map": event_results_map,
        "treasure_visible": treasure_visible,
        "escape_visible": escape_visible
    })
    return HTMLResponse(content=html_content)

@router.get("/nations", response_class=HTMLResponse)
async def nations_page(request: Request, team: dict = Depends(require_team)):
    # Explicitly select participant_name and olympics_attended alongside team details
    teams_res = supabase.table("teams").select("id, nation_name, participant_name, flag_emoji, is_admin, olympics_attended").execute()
    teams = teams_res.data if teams_res.data else []

    # Also include feature toggles here just to keep navbar fully consistent
    settings_res = supabase.table("app_settings").select("key, is_active").execute()
    settings = {s["key"]: s["is_active"] for s in settings_res.data} if settings_res.data else {}
    
    treasure_visible = settings.get("treasure_hunt_active", False)
    escape_visible = settings.get("puzzle_room_active", False)

    template = templates.get_template("nations.html")
    html_content = template.render({
        "request": request, 
        "team": team,
        "teams": teams,
        "treasure_visible": treasure_visible,
        "escape_visible": escape_visible
    })
    return HTMLResponse(content=html_content)
