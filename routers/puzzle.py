from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import supabase
from routers.auth import require_team

router = APIRouter(tags=["Puzzle Room"])
templates = Jinja2Templates(directory="templates")

@router.get("/puzzle", response_class=HTMLResponse)
async def puzzle_page(request: Request, team: dict = Depends(require_team)):
    toggle_res = supabase.table("app_settings").select("is_active").eq("key", "puzzle_room_active").execute()
    is_active = toggle_res.data[0]["is_active"] if toggle_res.data else False
    
    return templates.TemplateResponse("puzzle.html", {"request": request, "team": team, "is_active": is_active})
