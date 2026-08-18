from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from database import supabase
from routers.auth import require_team

router = APIRouter(prefix="/escape-room", tags=["Escape Room"])
templates = Jinja2Templates(directory="templates")

# Exact answers for your 4 stages
STAGE_ANSWERS = {
    1: "keyboard",
    2: "athletes",
    3: "drink",
    4: "red-orange-yellow-green-blue-indigo-violet"  # 7 colored wires sequence
}

@router.get("", response_class=HTMLResponse)
async def escape_room_page(request: Request, team: dict = Depends(require_team)):
    settings_res = supabase.table("app_settings").select("key, is_active").execute()
    settings = {s["key"]: s["is_active"] for s in settings_res.data} if settings_res.data else {}
    escape_visible = settings.get("puzzle_room_active", False)

    prog_res = supabase.table("puzzle_progress").select("current_stage").eq("team_id", team["id"]).execute()
    current_stage = prog_res.data[0]["current_stage"] if prog_res.data else 1

    return templates.TemplateResponse(
        request=request,
        name="puzzle.html",
        context={
            "request": request,
            "team": team,
            "current_stage": current_stage,
            "escape_visible": escape_visible
        }
    )

@router.post("/submit")
async def submit_puzzle(
    request: Request,
    stage: int = Form(...),
    answer: str = Form(...),
    team: dict = Depends(require_team)
):
    clean_answer = answer.strip().lower()
    
    # Check if the submitted answer is correct for the current stage
    if stage in STAGE_ANSWERS and clean_answer == STAGE_ANSWERS[stage]:
        next_stage = stage + 1
        
        # Check if a progress row already exists for this team to bypass strict RLS insert/upsert restrictions
        existing = supabase.table("puzzle_progress").select("team_id").eq("team_id", team["id"]).execute()
        
        if existing.data:
            supabase.table("puzzle_progress").update({"current_stage": next_stage}).eq("team_id", team["id"]).execute()
        else:
            supabase.table("puzzle_progress").insert({"team_id": team["id"], "current_stage": next_stage}).execute()
            
        return RedirectResponse(url="/escape-room", status_code=status.HTTP_303_SEE_OTHER)
    
    # If the answer is incorrect, redirect back with an error toast parameter
    return RedirectResponse(url="/escape-room?error=Incorrect+Answer!", status_code=status.HTTP_303_SEE_OTHER)
