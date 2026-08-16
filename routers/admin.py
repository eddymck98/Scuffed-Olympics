from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from database import supabase
from routers.auth import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="templates")

@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: bool = Depends(require_admin)):
    pending_res = supabase.table("team_treasure_progress").select("id, image_url, submitted_at, status, teams(nation_name, flag_emoji), treasure_hunt_items(title, points)").eq("status", "pending").execute()
    pending_submissions = pending_res.data if pending_res.data else []

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "pending_submissions": pending_submissions
    })

@router.post("/toggle")
async def admin_toggle(key: str = Form(...), admin: bool = Depends(require_admin)):
    res = supabase.table("app_settings").select("is_active").eq("key", key).execute()
    if res.data:
        current_state = res.data[0]["is_active"]
        new_state = not current_state
        supabase.table("app_settings").update({"is_active": new_state}).eq("key", key).execute()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/treasure/verify")
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

    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
