from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from database import supabase, templates
from routers.auth import require_team

router = APIRouter(tags=["Party Mode"])

@router.get("/party", response_class=HTMLResponse)
async def party_page(request: Request, team: dict = Depends(require_team)):
    teams_res = supabase.table("teams").select("id, nation_name, participant_name, flag_emoji").execute()
    teams = teams_res.data if teams_res.data else []

    settings_res = supabase.table("app_settings").select("key, is_active").execute()
    settings = {s["key"]: s["is_active"] for s in settings_res.data} if settings_res.data else {}
    
    treasure_visible = settings.get("treasure_hunt_active", False)
    escape_visible = settings.get("puzzle_room_active", False)

    template = templates.get_template("party.html")
    html_content = template.render({
        "request": request,
        "team": team,
        "teams": teams,
        "treasure_visible": treasure_visible,
        "escape_visible": escape_visible
    })
    return HTMLResponse(content=html_content)

@router.get("/api/party-tasks")
async def get_party_tasks(team: dict = Depends(require_team)):
    tasks_res = supabase.table("drinking_tasks").select("*").execute()
    return JSONResponse(content=tasks_res.data if tasks_res.data else [])
