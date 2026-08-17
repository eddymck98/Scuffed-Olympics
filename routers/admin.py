from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from database import supabase, templates
from routers.auth import require_admin

router = APIRouter(tags=["Admin"])

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: bool = Depends(require_admin)):
    pending_res = supabase.table("team_treasure_progress").select("id, image_url, submitted_at, status, teams(nation_name, flag_emoji), treasure_hunt_items(title, points)").eq("status", "pending").execute()
    pending_submissions = pending_res.data if pending_res.data else []

    teams_res = supabase.table("teams").select("id, nation_name, flag_emoji").execute()
    teams = teams_res.data if teams_res.data else []

    results_res = supabase.table("event_results").select("id, event_name, points, medal_type, teams(nation_name, flag_emoji)").order("recorded_at", desc=True).limit(10).execute()
    recent_results = results_res.data if results_res.data else []

    # Bypass Starlette's cached TemplateResponse to prevent Python 3.14 dict-hashing error
    template = templates.get_template("admin.html")
    html_content = template.render({
        "request": request,
        "pending_submissions": pending_submissions,
        "teams": teams,
        "recent_results": recent_results
    })
    return HTMLResponse(content=html_content)

@router.post("/admin/event-results/add")
async def add_event_result(
    event_name: str = Form(...),
    team_id: str = Form(...),
    points: int = Form(...),
    medal_type: str = Form("none"),
    admin: bool = Depends(require_admin)
):
    supabase.table("event_results").insert({
        "event_name": event_name,
        "team_id": team_id,
        "points": points,
        "medal_type": medal_type
    }).execute()
    
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/event-results/delete")
async def delete_event_result(result_id: str = Form(...), admin: bool = Depends(require_admin)):
    supabase.table("event_results").delete().eq("id", result_id).execute()
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/toggle")
async def admin_toggle(key: str = Form(...), admin: bool = Depends(require_admin)):
    res = supabase.table("app_settings").select("is_active").eq("key", key).execute()
    if res.data:
        current_state = res.data[0]["is_active"]
        new_state = not current_state
        supabase.table("app_settings").update({"is_active": new_state}).eq("key", key).execute()
    
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/treasure/verify")
async def verify_treasure_submission(submission_id: str = Form(...), action: str = Form(...), admin: bool = Depends(require_admin)):
    new_status = "approved" if action == "approve" else "rejected"
    
    supabase.table("team_treasure_progress").update({"status": new_status}).eq("id", submission_id).execute()
    
    if new_status == "approved":
        sub_info = supabase.table("team_treasure_progress").select("team_id, treasure_hunt_items(points)").eq("id", submission_id).execute()
        if sub_info.data:
            data = sub_info.data[0]
            tid = data["team_id"]
            pts = data["treasure_hunt_items"]["points"] if data["treasure_hunt_items"] else 10
            supabase.table("event_results").insert({
                "event_name": "City Treasure Hunt Task",
                "team_id": tid,
                "medal_type": "none",
                "points": pts
            }).execute()

    return RedirectResponse(url="/admin", status_code=303)
