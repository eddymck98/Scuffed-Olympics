from fastapi import FastAPI, Depends, Form, Request, HTTPException, status, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import supabase
import os

app = FastAPI(title="Scuffed Olympics")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- AUTHENTICATION HELPERS ---

def get_current_team(request: Request):
    """Helper to retrieve the logged-in team from cookies."""
    team_id = request.cookies.get("team_id")
    nation_name = request.cookies.get("nation_name")
    if not team_id or not nation_name:
        return None
    return {"id": team_id, "nation_name": nation_name}

def require_team(request: Request):
    """Dependency to protect team routes. Redirects to login if not authenticated."""
    team = get_current_team(request)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return team

def require_admin(request: Request):
    """Simple check for admin access (using an admin session cookie)."""
    is_admin = request.cookies.get("is_admin")
    if is_admin != "true":
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"}
        )
    return True


# --- PUBLIC / AUTH ROUTES ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    response = supabase.table("teams").select("id, nation_name, flag_emoji").execute()
    teams = response.data if response.data else []
    return templates.TemplateResponse("login.html", {"request": request, "teams": teams})

@app.post("/login")
async def login_action(team_id: str = Form(...), pin_code: str = Form(...)):
    response = supabase.table("teams").select("*").eq("id", team_id).eq("pin_code", pin_code).execute()
    teams = response.data
    
    if not teams:
        return RedirectResponse(url="/login?error=Invalid+PIN", status_code=status.HTTP_303_SEE_OTHER)
    
    team = teams[0]
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="team_id", value=team["id"], httponly=True)
    response.set_cookie(key="nation_name", value=team["nation_name"], httponly=True)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("team_id")
    response.delete_cookie("nation_name")
    return response


# --- ADMIN LOGIN ROUTES ---

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def admin_login_action(admin_password: str = Form(...)):
    master_pass = os.getenv("ADMIN_PASSWORD", "scuffedadmin123")
    if admin_password != master_pass:
        return RedirectResponse(url="/admin/login?error=Wrong+Password", status_code=status.HTTP_303_SEE_OTHER)
    
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="is_admin", value="true", httponly=True)
    return response


# --- MAIN APP ROUTES (PROTECTED) ---

@app.get("/", response_class=HTMLResponse)
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
                standings[tid]["total_points"] += 3
            elif medal == "silver":
                standings[tid]["silver"] += 1
                standings[tid]["total_points"] += 2
            elif medal == "bronze":
                standings[tid]["bronze"] += 1
                standings[tid]["total_points"] += 1
            if r["points"]:
                standings[tid]["total_points"] += r["points"]

    sorted_standings = sorted(
        standings.values(), 
        key=lambda x: (x["total_points"], x["gold"], x["silver"], x["bronze"]), 
        reverse=True
    )

    activity_res = supabase.table("event_results").select("event_name, medal_type, recorded_at, teams(nation_name, flag_emoji)").order("recorded_at", desc=True).limit(5).execute()
    activities = activity_res.data if activity_res.data else []

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "team": team, 
        "standings": sorted_standings,
        "activities": activities
    })

@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, team: dict = Depends(require_team)):
    return templates.TemplateResponse("events.html", {"request": request, "team": team})

@app.get("/treasure-hunt", response_class=HTMLResponse)
async def treasure_hunt_page(request: Request, team: dict = Depends(require_team)):
    # 1. Check if hunt is active
    toggle_res = supabase.table("app_settings").select("is_active").eq("key", "treasure_hunt_active").execute()
    is_active = toggle_res.data[0]["is_active"] if toggle_res.data else False
    
    # 2. Fetch all hunt items and team's progress
    items_res = supabase.table("treasure_hunt_items").select("*").execute()
    items = items_res.data if items_res.data else []

    progress_res = supabase.table("team_treasure_progress").select("*").eq("team_id", team["id"]).execute()
    # Map progress by item_id for easy lookup in Jinja template
    progress_map = {p["item_id"]: p for p in progress_res.data} if progress_res.data else {}

    return templates.TemplateResponse("treasure_hunt.html", {
        "request": request, 
        "team": team, 
        "is_active": is_active,
        "items": items,
        "progress_map": progress_map
    })

@app.post("/treasure-hunt/submit")
async def submit_treasure_item(request: Request, item_id: str = Form(...), photo: UploadFile = File(...), team: dict = Depends(require_team)):
    # 1. Upload photo to Supabase storage bucket named 'treasure-hunt-uploads'
    file_bytes = await photo.read()
    file_path = f"{team['id']}/{item_id}_{photo.filename}"
    
    storage_res = supabase.storage.from_("treasure-hunt-uploads").upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": photo.content_type}
    )
    
    # Get public URL for the uploaded image
    public_url_res = supabase.storage.from_("treasure-hunt-uploads").get_public_url(file_path)
    image_url = public_url_res if isinstance(public_url_res, str) else public_url_res.get("publicURL", "")

    # 2. Upsert submission record into database as 'pending'
    supabase.table("team_treasure_progress").upsert({
        "team_id": team["id"],
        "item_id": item_id,
        "image_url": image_url,
        "status": "pending"
    }, on_conflict="team_id,item_id").execute()

    return RedirectResponse(url="/treasure-hunt", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/nations", response_class=HTMLResponse)
async def nations_page(request: Request, team: dict = Depends(require_team)):
    return templates.TemplateResponse("nations.html", {"request": request, "team": team})

@app.get("/puzzle", response_class=HTMLResponse)
async def puzzle_page(request: Request, team: dict = Depends(require_team)):
    toggle_res = supabase.table("app_settings").select("is_active").eq("key", "puzzle_room_active").execute()
    is_active = toggle_res.data[0]["is_active"] if toggle_res.data else False
    
    return templates.TemplateResponse("puzzle.html", {"request": request, "team": team, "is_active": is_active})


# --- ADMIN CONTROL PANEL ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: bool = Depends(require_admin)):
    # Fetch pending treasure hunt submissions for verification queue
    pending_res = supabase.table("team_treasure_progress").select("id, image_url, submitted_at, status, teams(nation_name, flag_emoji), treasure_hunt_items(title, points)").eq("status", "pending").execute()
    pending_submissions = pending_res.data if pending_res.data else []

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "pending_submissions": pending_submissions
    })

@app.post("/admin/toggle")
async def admin_toggle(key: str = Form(...), admin: bool = Depends(require_admin)):
    res = supabase.table("app_settings").select("is_active").eq("key", key).execute()
    if res.data:
        current_state = res.data[0]["is_active"]
        new_state = not current_state
        supabase.table("app_settings").update({"is_active": new_state}).eq("key", key).execute()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/treasure/verify")
async def verify_treasure_submission(submission_id: str = Form(...), action: str = Form(...), admin: bool = Depends(require_admin)):
    # action can be 'approve' or 'reject'
    new_status = "approved" if action == "approve" else "rejected"
    
    # Update submission status
    supabase.table("team_treasure_progress").update({"status": new_status}).eq("id", submission_id).execute()
    
    # If approved, award points as a bonus event result or handle points logic here
    if new_status == "approved":
        sub_info = supabase.table("team_treasure_progress").select("team_id, treasure_hunt_items(points)").eq("id", submission_id).execute()
        if sub_info.data:
            data = sub_info.data[0]
            tid = data["team_id"]
            pts = data["treasure_hunt_items"]["points"] if data["treasure_hunt_items"] else 10
            # Record points in event_results
            supabase.table("event_results").insert({
                "event_name": "City Treasure Hunt Task",
                "team_id": tid,
                "medal_type": "none",
                "points": pts
            }).execute()

    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
