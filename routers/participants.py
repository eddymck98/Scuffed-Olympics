from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from database import supabase, templates
from routers.auth import require_team

router = APIRouter(tags=["Participants"])

@router.get("/", response_class=HTMLResponse)
async def home_dashboard(request: Request, team: dict = Depends(require_team)):
    teams_res = supabase.table("teams").select("id, nation_name, flag_emoji").execute()
    teams = teams_res.data if teams_res.data else []
    
    results_res = supabase.table("event_results").select("team_id, medal_type, points").execute()
    results = results_res.data if results_res.data else []
    
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
        .limit(5) \
        .execute()
    activities = activity_res.data if activity_res.data else []

    # Bypass Starlette's cached TemplateResponse to prevent Python 3.14 dict-hashing error
    template = templates.get_template("index.html")
    html_content = template.render({
        "request": request, 
        "team": team, 
        "standings": sorted_standings,
        "activities": activities
    })
    return HTMLResponse(content=html_content)

@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, team: dict = Depends(require_team)):
    # Fetch all event results to display standings per event
    results_res = supabase.table("event_results").select("event_name, points, medal_type, teams(nation_name, flag_emoji)").order("points", desc=True).execute()
    results = results_res.data if results_res.data else []

    # Group results by event name
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
