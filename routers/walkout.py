from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from database import supabase, templates
from routers.auth import get_current_team

router = APIRouter(tags=["Walkout"])

@router.get("/walkout")
def walkout_page(request: Request):
    team_id = request.cookies.get("team_id")
    if not team_id:
        return RedirectResponse(url="/login", status_code=303)
    
    # Fetch all competing nations/teams
    teams_res = supabase.table("teams").select("*").order("nation_name").execute()
    teams = teams_res.data if teams_res.data else []
    
    # Check if this team has already submitted a walkout ranking ballot
    existing_res = supabase.table("walkout_rankings").select("*").eq("voter_team_id", team_id).execute()
    existing_data = existing_res.data if existing_res.data else []
    
    # If they already voted, sort the teams order to match their previous ballot
    if existing_data and existing_data[0].get('ranked_team_ids'):
        saved_order = existing_data[0]['ranked_team_ids']
        team_dict = {t['id']: t for t in teams}
        sorted_teams = [team_dict[t_id] for t_id in saved_order if t_id in team_dict]
        for t in teams:
            if t not in sorted_teams:
                sorted_teams.append(t)
        teams = sorted_teams

    return templates.TemplateResponse("walkout.html", {
        "request": request,
        "team": get_current_team(request),
        "teams": teams
    })

@router.post("/walkout/submit")
async def submit_walkout(request: Request):
    team_id = request.cookies.get("team_id")
    if not team_id:
        return RedirectResponse(url="/login", status_code=303)
    
    form = await request.form()
    ranked_ids_str = form.get("ranked_ids", "")
    ranked_ids = [uid.strip() for uid in ranked_ids_str.split(",") if uid.strip()]
    
    if not ranked_ids:
        return RedirectResponse(url="/walkout?error=No+rankings+provided", status_code=303)
    
    # Upsert the ballot for this specific voting team
    supabase.table("walkout_rankings").upsert({
        "voter_team_id": team_id,
        "ranked_team_ids": ranked_ids
    }, on_conflict="voter_team_id").execute()
    
    return RedirectResponse(url="/walkout?success=1", status_code=303)
