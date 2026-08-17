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
async def admin_dashboard(request: Request, admin: bool = Depends(require_admin)):
    pending_res = supabase.table("team_treasure_progress").select("id, image_url, submitted_at, status, teams(nation_name, flag_emoji), treasure_hunt_items(title, points)").eq("status", "pending").execute()
    pending_submissions = pending_res.data if pending_res.data else []

    teams_res = supabase.table("teams").select("id, nation_name, flag_emoji").order("nation_name").execute()
    teams = teams_res.data if teams_res.data else []

    results_res = supabase.table("event_results").select("id, event_name, points, medal_type, teams(nation_name, flag_emoji)").order("recorded_at", desc=True).limit(15).execute()
    recent_results = results_res.data if results_res.data else []

    # Get list of all events
    events_list = [
        "Duck Hunt", "City Selfies", "Crack the Code", "Golf Putting", 
        "Padel Pong", "Sticky Bounce", "Ring Toss", "Bean Bag Toss", 
        "The Entrance", "Cut the Deck", "Beer Pong", "The Ultimate Relay Race"
    ]

    template = templates.get_template("admin.html")
    html_content = template.render({
        "request": request,
        "pending_submissions": pending_submissions,
        "teams": teams,
        "recent_results": recent_results,
        "events_list": events_list
    })
    return HTMLResponse(content=html_content)

@router.post("/admin/event-results/bulk-save")
async def bulk_save_event_results(request: Request, admin: bool = Depends(require_admin)):
    form_data = await request.form()
    event_name = form_data.get("event_name")
    
    # Clear previous results for this event to allow clean overwrites/updates
    supabase.table("event_results").delete().eq("event_name", event_name).execute()

    # Process each team's submission from the form fields
    teams_res = supabase.table("teams").select("id").execute()
    teams = teams_res.data if teams_res.data else []

    insert_batch = []
    for t in teams:
        tid = t["id"]
        placement = form_data.get(f"placement_{tid}")
        custom_pts = form_data.get(f"custom_points_{tid}")
        medal_type = form_data.get(f"medal_{tid}", "none")

        if not placement:
            continue

        if placement == "custom" and custom_pts:
            try:
                points = int(custom_pts)
            except ValueError:
                points = 0
        else:
            points = PLACEMENT_POINTS.get(placement, 0)

        # Only insert if points or placement are active (skip saving 0-point DNPs if preferred, or keep them)
        insert_batch.append({
            "event_name": event_name,
            "team_id": tid,
            "points": points,
            "medal_type": medal_type
        })

    if insert_batch:
        supabase.table("event_results").insert(insert_batch).execute()

    return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/event-results/delete")
async def delete_event_result(result_id: str = Form(...), admin: bool = Depends(require_admin)):
    supabase.table("event_results").delete().eq("id", result_id).execute()
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
