from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from database import supabase, templates
from routers.auth import require_team

router = APIRouter(tags=["Participants"])

@router.get("/", response_class=HTMLResponse)
async def home_dashboard(request: Request, team: dict = Depends(require_team)):
    teams_res = supabase.table("teams").select("id, nation_name, participant_name, flag_emoji").order("nation_name").execute()
    teams = teams_res.data if teams_res.data else []
    
    results_res = supabase.table("event_results").select("team_id, medal_type, points").execute()
    results = results_res.data if results_res.data else []
    
    # Fetch shot history for this specific team
    shots_history_res = supabase.table("shots_log").select("amount, reason").eq("team_id", team["id"]).order("recorded_at", desc=True).limit(5).execute()
    shots_history = shots_history_res.data if shots_history_res.data else []
    
    standings = {}
    for t in teams:
        standings[t["id"]] = {
            "nation_name": t["nation_name"],
            "flag_emoji": t["flag_emoji"],
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

    # Fetch ONLY medal winners for the recent activity feed
    activity_res = supabase.table("event_results") \
        .select("event_name, medal_type, recorded_at, teams(nation_name, flag_emoji)") \
        .neq("medal_type", "none") \
        .order("recorded_at", desc=True) \
        .limit(6) \
        .execute()
    activities = activity_res.data if activity_res.data else []

    template = templates.get_template("index.html")
    html_content = template.render({
        "request": request, 
        "team": team, 
        "teams": teams,
        "standings": sorted_standings,
        "activities": activities,
        "shots_history": shots_history
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
        "event_results_map": event_results_map
    })
    return HTMLResponse(content=html_content)

@router.get("/nations", response_class=HTMLResponse)
async def nations_page(request: Request, team: dict = Depends(require_team)):
    teams_res = supabase.table("teams").select("id, nation_name, flag_emoji, is_admin").execute()
    teams = teams_res.data if teams_res.data else []

    template = templates.get_template("nations.html")
    html_content = template.render({
        "request": request, 
        "team": team,
        "teams": teams
    })
    return HTMLResponse(content=html_content)
