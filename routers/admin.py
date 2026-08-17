from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from database import supabase, templates
from routers.auth import require_admin

router = APIRouter(tags=["Admin"])

PLACEMENT_POINTS = {
    "7th": 10,
    "1st": 8,
    "2nd": 7,
    "3rd": 6,
    "4th": 5,
    "5th": 4,
    "6th": 3,
    "8th": 2,
    "9th": 1,
    "DNP": 0
}

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, tab: str = "events", subtab: str = "standard", event: str = "Crack the Code", admin: bool = Depends(require_admin)):
    pending_res = supabase.table("team_treasure_progress").select("id, image_url, submitted_at, status, teams(nation_name, flag_emoji), treasure_hunt_items(title, points)").eq("status", "pending").execute()
    pending_submissions = pending_res.data if pending_res.data else []

    teams_res = supabase.table("teams").select("id, nation_name, flag_emoji").order("nation_name").execute()
    teams = teams_res.data if teams_res.data else []

    results_res = supabase.table("event_results").select("id, event_name, points, medal_type, team_id").execute()
    all_results = results_res.data if results_res.data else []

    # Map existing results by team_id for the currently selected event
    event_scores = {}
    for r in all_results:
        if r["event_name"] == event:
            event_scores[r["team_id"]] = r

    recent_results = supabase.table("event_results").select("id, event_name, points, medal_type, teams(nation_name, flag_emoji)").order("recorded_at", desc=True).limit(15).execute()
    recent_list = recent_results.data if recent_results.data else []

    standard_events = [
        "Crack the Code", "Golf Putting", "Padel Pong", "Sticky Bounce", 
        "Ring Toss", "Bean Bag Toss", "The Entrance", "Cut the Deck", 
        "Beer Pong", "The Ultimate Relay Race"
    ]

    template = templates.get_template("admin.html")
    html_content = template.render({
        "request": request,
        "active_tab": tab,
        "active_subtab": subtab,
        "selected_event": event,
        "pending_submissions": pending_submissions,
        "teams": teams,
        "event_scores": event_scores,
        "recent_results": recent_list,
        "standard_events": standard_events
    })
    return HTMLResponse(content=html_content)

@router.post("/admin/event-results/save-standard")
async def save_standard_event(request: Request, admin: bool = Depends(require_admin)):
    form_data = await request.form()
    event_name = form_data.get("event_name")
    
    supabase.table("event_results").delete().eq("event_name", event_name).execute()

    teams_res = supabase.table("teams").select("id").execute()
    teams = teams_res.data if teams_res.data else []

    insert_batch = []
    for t in teams:
        tid = t["id"]
        placement = form_data.get(f"placement_{tid}")
        if not placement or placement == "unscored":
            continue

        points = PLACEMENT_POINTS.get(placement, 0)
        
        medal_type = "none"
        if placement == "1st": medal_type = "gold"
        elif placement == "2nd": medal_type = "silver"
        elif placement == "3rd": medal_type = "bronze"

        insert_batch.append({
            "event_name": event_name,
            "team_id": tid,
            "points": points,
            "medal_type": medal_type
        })

    if insert_batch:
        supabase.table("event_results").insert(insert_batch).execute()

    return RedirectResponse(url=f"/admin?tab=events&subtab=standard&event={event_name}", status_code=303)

@router.post("/admin/event-results/save-duck-hunt")
async def save_duck_hunt(request: Request, admin: bool = Depends(require_admin)):
    form_data = await request.form()
    event_name = "Duck Hunt"
    
    supabase.table("event_results").delete().eq("event_name", event_name).execute()

    teams_res = supabase.table("teams").select("id").execute()
    teams = teams_res.data if teams_res.data else []

    insert_batch = []
    for t in teams:
        tid = t["id"]
        ducks_found = form_data.get(f"ducks_{tid}")
        if not ducks_found:
            continue
        try:
            points = int(ducks_found)
        except ValueError:
            points = 0

        insert_batch.append({
            "event_name": event_name,
            "team_id": tid,
            "points": points,
            "medal_type": "none"
        })

    if insert_batch:
        supabase.table("event_results").insert(insert_batch).execute()

    return RedirectResponse(url="/admin?tab=events&subtab=duck", status_code=303)

@router.post("/admin/event-results/save-treasure")
async def save_treasure_event(request: Request, admin: bool = Depends(require_admin)):
    form_data = await request.form()
    event_name = "City Selfies"
    
    supabase.table("event_results").delete().eq("event_name", event_name).execute()

    teams_res = supabase.table("teams").select("id").execute()
    teams = teams_res.data if teams_res.data else []

    insert_batch = []
    for t in teams:
        tid = t["id"]
        pod = form_data.get(f"pod_{tid}")
        if not pod or pod == "unscored":
            continue
        
        pod_points = {"1st": 10, "2nd": 7, "3rd": 4, "last": 1, "dnp": 0}
        points = pod_points.get(pod, 0)
        
        medal_type = "none"
        if pod == "1st": medal_type = "gold"
        elif pod == "2nd": medal_type = "silver"
        elif pod == "3rd": medal_type = "bronze"

        insert_batch.append({
            "event_name": event_name,
            "team_id": tid,
            "points": points,
            "medal_type": medal_type
        })

    if insert_batch:
        supabase.table("event_results").insert(insert_batch).execute()

    return RedirectResponse(url="/admin?tab=events&subtab=treasure", status_code=303)

@router.post("/admin/event-results/delete")
async def delete_event_result(result_id: str = Form(...), admin: bool = Depends(require_admin)):
    supabase.table("event_results").delete().eq("id", result_id).execute()
    return RedirectResponse(url="/admin?tab=logs", status_code=303)

@router.post("/admin/treasure/verify")
async def verify_treasure_submission(submission_id: str = Form(...), action: str = Form(...), admin: bool = Depends(require_admin)):
    new_status = "approved" if action == "approve" else "rejected"
    supabase.table("team_treasure_progress").update({"status": new_status}).eq("id", submission_id).execute()
    return RedirectResponse(url="/admin?tab=verification", status_code=303)
