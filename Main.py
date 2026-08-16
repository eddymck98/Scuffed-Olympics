from fastapi import FastAPI, Depends, Form, Request, HTTPException, status
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
    # Fetch all teams from Supabase to populate the nation dropdown
    response = supabase.table("teams").select("id, nation_name, flag_emoji").execute()
    teams = response.data if response.data else []
    return templates.TemplateResponse("login.html", {"request": request, "teams": teams})

@app.post("/login")
async def login_action(team_id: str = Form(...), pin_code: str = Form(...)):
    # Verify PIN against Supabase database
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
    # Simple hardcoded admin password check (or store it securely in your .env)
    master_pass = os.getenv("ADMIN_PASSWORD", "scuffedadmin123")
    if admin_password != master_pass:
        return RedirectResponse(url="/admin/login?error=Wrong+Password", status_code=status.HTTP_303_SEE_OTHER)
    
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="is_admin", value="true", httponly=True)
    return response


# --- MAIN APP ROUTES (PROTECTED) ---

@app.get("/", response_class=HTMLResponse)
async def home_dashboard(request: Request, team: dict = Depends(require_team)):
    # Fetch global app settings (toggles) and recent activity here later
    return templates.TemplateResponse("index.html", {"request": request, "team": team})

@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, team: dict = Depends(require_team)):
    return templates.TemplateResponse("events.html", {"request": request, "team": team})

@app.get("/treasure-hunt", response_class=HTMLResponse)
async def treasure_hunt_page(request: Request, team: dict = Depends(require_team)):
    # Check if treasure hunt is active in app_settings table
    toggle_res = supabase.table("app_settings").select("is_active").eq("key", "treasure_hunt_active").execute()
    is_active = toggle_res.data[0]["is_active"] if toggle_res.data else False
    
    return templates.TemplateResponse("treasure_hunt.html", {"request": request, "team": team, "is_active": is_active})

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
    return templates.TemplateResponse("admin.html", {"request": request})
