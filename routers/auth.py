from fastapi import APIRouter, Depends, Form, Request, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from database import supabase, templates
import os

router = APIRouter(tags=["Authentication"])

def get_current_team(request: Request):
    team_id = request.cookies.get("team_id")
    if not team_id:
        return None
    
    # Updated to select "*" so custom columns like treasure_group_id are fully loaded into the session
    res = supabase.table("teams").select("*").eq("id", team_id).execute()
    if not res.data:
        return None
    return res.data[0]

def require_team(request: Request):
    team = get_current_team(request)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return team

def require_admin(request: Request):
    is_admin = request.cookies.get("is_admin")
    if is_admin != "true":
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"}
        )
    return True

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    try:
        response = supabase.table("teams").select("id, nation_name, flag_emoji").execute()
        teams = response.data if response.data else []
    except Exception as e:
        print("Error fetching teams for login:", e)
        teams = []
    
    template = templates.get_template("login.html")
    html_content = template.render({"request": request, "teams": teams})
    return HTMLResponse(content=html_content)

@router.post("/login")
async def login_action(team_id: str = Form(...), pin_code: str = Form(...)):
    response = supabase.table("teams").select("*").eq("id", team_id).eq("pin_code", pin_code).execute()
    teams = response.data
    
    if not teams:
        return RedirectResponse(url="/login?error=Invalid+PIN", status_code=status.HTTP_303_SEE_OTHER)
    
    team = teams[0]
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="team_id", value=team["id"], httponly=True)
    response.set_cookie(key="nation_name", value=team["nation_name"], httponly=True)
    
    if team.get("is_admin"):
        response.set_cookie(key="is_admin", value="true", httponly=True)
    else:
        response.delete_cookie("is_admin")
        
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("team_id")
    response.delete_cookie("nation_name")
    response.delete_cookie("is_admin")
    return response

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    template = templates.get_template("admin_login.html")
    html_content = template.render({"request": request})
    return HTMLResponse(content=html_content)

@router.post("/admin/login")
async def admin_login_action(admin_password: str = Form(...)):
    master_pass = os.getenv("ADMIN_PASSWORD", "scuffedadmin123")
    if admin_password != master_pass:
        return RedirectResponse(url="/admin/login?error=Wrong+Password", status_code=status.HTTP_303_SEE_OTHER)
    
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="is_admin", value="true", httponly=True)
    return response
