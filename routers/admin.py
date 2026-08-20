from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from database import supabase, templates
from routers.auth import require_admin

router = APIRouter(tags=["Admin"])

PLACEMENT_POINTS = {
    "7th": 10, "1st": 8, "2nd": 7, "3rd": 6, "4th": 5, 
    "5th": 4, "6th": 3, "8th": 2, "9th": 1, "DNP": 0
}

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, tab: str = "events", subtab: str = "standard", event: str = "Crack the Code", admin: bool = Depends(require_admin)):
    pending_res = supabase.table("team_treasure_progress").select("id, image_url, submitted_at, status, team_id, item_id, teams(nation_name, flag_emoji), treasure_hunt_items(title)").eq("status", "pending").execute()
    
    teams_res = supabase.table("teams").select("id, nation_name, flag_emoji, shots_owed").order("nation_name").execute()
    all_results = supabase.table("event_results").select("id, event_name, points, medal_type, team_id").execute()
    var_res = supabase.table("var_submissions").select("*, teams(nation_name, flag_emoji)").eq("status", "pending").execute()
     
    settings_res = supabase.table("app_settings").select("key, is_active").execute()
    app_settings = {s["key"]: s["is_active"] for s in settings_res.data} if settings_res.data else {}
     
    # Pull visibility flags and countdown state
    treasure_visible = app_settings.get("treasure_hunt_active", False)
    escape_visible = app_settings.get("puzzle_room_active", False)
    walkout_visible = app_settings.get("walkout_active", False)
    ceremony_countdown_active = app_settings.get("ceremony_countdown_active", False)
     
    teams = teams_res.data if teams_res.data else []
    event_scores = {r["team_id"]: r for r in (all_results.data or []) if r["event_name"] == event}
    recent_list = supabase.table("event_results").select("id, event_name, points, medal_type, teams(nation_name, flag_emoji)").order("recorded_at", desc=True).limit(15).execute().data or []

    # Calculate Walkout Consensus Points
    ballots_res = supabase.table("walkout_rankings").select("ranked_team_ids").execute()
    ballots = ballots_res.data if ballots_res.data else []
    
    consensus_scores = {t['id']: {"name": t['nation_name'], "emoji": t['flag_emoji'], "total_points": 0, "first_place_votes": 0} for t in teams}
    
    for ballot in ballots:
        ranked_list = ballot.get('ranked_team_ids', [])
        for index, t_id in enumerate(ranked_list):
            if t_id in consensus_scores:
                # 1st place gets 10 pts, decreasing by 1 down to a minimum of 1
                points = max(1, 11 - (index + 1))
                consensus_scores[t_id]["total_points"] += points
                if index == 0:
                    consensus_scores[t_id]["first_place_votes"] += 1
                    
    sorted_consensus = sorted(consensus_scores.values(), key=lambda x: x["total_points"], reverse=True)
    walkout_consensus = {
        "ballots_cast": len(ballots),
        "consensus": sorted_consensus
    }

    template = templates.get_template("admin.html")
    html_content = template.render({
        "request": request,
        "team": {"nav_color": "rgba(15, 23, 42, 0.9)"}, 
        "active_tab": tab,
        "active_subtab": subtab,
        "selected_event": event,
        "pending_submissions": pending_res.data or [],
        "var_submissions": var_res.data or [],
        "teams": teams,
        "event_scores": event_scores,
        "recent_results": recent_list,
        "app_settings": app_settings,
        "treasure_visible": treasure_visible,
        "escape_visible": escape_visible,
        "walkout_visible": walkout_visible,
        "ceremony_countdown_active": ceremony_countdown_active,
        "walkout_consensus": walkout_consensus,
        "ceremony_date": "Oct 2, 2026 18:00:00",
        "standard_events": ["Crack the Code", "Golf Putting", "Padel Pong", "Sticky Bounce", "Ring Toss", "Bean Bag Toss", "The Entrance", "Cut the Deck", "Beer Pong", "The Ultimate Relay Race"]
    })
    return HTMLResponse(content=html_content)

# --- Feature Toggle Endpoint ---

@router.post("/admin/toggle-setting")
async def toggle_setting(key: str = Form(...), value: bool = Form(...), admin: bool = Depends(require_admin)):
    supabase.table("app_settings").update({"is_active": value}).eq("key", key).execute()
    return RedirectResponse(url="/admin?tab=settings", status_code=303)

# --- Event Scoring Endpoints ---

@router.post("/admin/event-results/save-standard")
async def save_standard_event(request: Request, admin: bool = Depends(require_admin)):
    form_data = await request.form()
    event_name = form_data.get("event_name")
    supabase.table("event_results").delete().eq("event_name", event_name).execute()
    teams = supabase.table("teams").select("id").execute().data or []

    insert_batch = []
    for t in teams:
        placement = form_data.get(f"placement_{t['id']}")
        if not placement or placement == "unscored": continue
         
        points = PLACEMENT_POINTS.get(placement, 0)
        medal = "gold" if placement == "1st" else "silver" if placement == "2nd" else "bronze" if placement == "3rd" else "none"
        insert_batch.append({"event_name": event_name, "team_id": t['id'], "points": points, "medal_type": medal})

    if insert_batch: supabase.table("event_results").insert(insert_batch).execute()
    return RedirectResponse(url=f"/admin?tab=events&subtab=standard&event={event_name}", status_code=303)

@router.post("/admin/event-results/save-duck-hunt")
async def save_duck_hunt(request: Request, admin: bool = Depends(require_admin)):
    form_data = await request.form()
    supabase.table("event_results").delete().eq("event_name", "Duck Hunt").execute()
    teams = supabase.table("teams").select("id").execute().data or []
    insert_batch = [{"event_name": "Duck Hunt", "team_id": t['id'], "points": int(form_data.get(f"ducks_{t['id']}", 0) or 0), "medal_type": "none"} for t in teams]
    supabase.table("event_results").insert(insert_batch).execute()
    return RedirectResponse(url="/admin?tab=events&subtab=duck", status_code=303)

@router.post("/admin/event-results/save-treasure")
async def save_treasure_event(request: Request, admin: bool = Depends(require_admin)):
    form_data = await request.form()
    supabase.table("event_results").delete().eq("event_name", "City Selfies").execute()
    teams = supabase.table("teams").select("id").execute().data or []
     
    insert_batch = []
    for t in teams:
        pod = form_data.get(f"pod_{t['id']}")
        if not pod or pod == "unscored": continue
        points = {"1st": 10, "2nd": 7, "3rd": 4, "last": 1, "dnp": 0}.get(pod, 0)
        medal = "gold" if pod == "1st" else "silver" if pod == "2nd" else "bronze" if pod == "3rd" else "none"
        insert_batch.append({"event_name": "City Selfies", "team_id": t['id'], "points": points, "medal_type": medal})
     
    if insert_batch: supabase.table("event_results").insert(insert_batch).execute()
    return RedirectResponse(url="/admin?tab=events&subtab=treasure", status_code=303)

# --- VAR Ruling Endpoints ---

@router.post("/admin/var/issue")
async def issue_ruling(
    submission_id: str = Form(...), 
    decision: str = Form(...), 
    points: int = Form(0), 
    shots: int = Form(0),
    reason: str = Form(...),
    admin: bool = Depends(require_admin)
):
    supabase.table("var_submissions").update({"status": decision}).eq("id", submission_id).execute()
    sub = supabase.table("var_submissions").select("team_id").eq("id", submission_id).execute().data[0]
    tid = sub["team_id"]

    if decision == "upheld":
        if points != 0:
            supabase.table("event_results").insert({"event_name": f"VAR Ruling: {reason}", "team_id": tid, "points": points, "medal_type": "none"}).execute()
        if shots > 0:
            team_res = supabase.table("teams").select("shots_owed").eq("id", tid).execute().data[0]
            supabase.table("teams").update({"shots_owed": team_res["shots_owed"] + shots}).eq("id", tid).execute()
            supabase.table("shots_log").insert({"team_id": tid, "amount": shots, "reason": f"VAR: {reason}"}).execute()

    return RedirectResponse(url="/admin?tab=var", status_code=303)

@router.post("/admin/event-results/delete")
async def delete_event_result(result_id: str = Form(...), admin: bool = Depends(require_admin)):
    supabase.table("event_results").delete().eq("id", result_id).execute()
    return RedirectResponse(url="/admin?tab=logs", status_code=303)

@router.post("/admin/treasure/verify")
async def verify_treasure_submission(
    submission_id: str = Form(...), 
    action: str = Form(...), 
    rejection_reason: str = Form(""), 
    admin: bool = Depends(require_admin)
):
    sub_res = supabase.table("team_treasure_progress").select("team_id, item_id").eq("id", submission_id).execute()
    if not sub_res.data:
        return RedirectResponse(url="/admin?tab=verification", status_code=303)
     
    sub = sub_res.data[0]
     
    if action == "approve":
        supabase.table("team_treasure_progress").update({"status": "approved", "rejection_reason": None}).eq("id", submission_id).execute()
    else:
        supabase.table("team_treasure_progress").update({
            "status": "rejected", 
            "rejection_reason": rejection_reason or "Photo does not match checklist criteria."
        }).eq("id", submission_id).execute()

    return RedirectResponse(url="/admin?tab=verification", status_code=303)
