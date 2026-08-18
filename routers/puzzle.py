from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, HTMLResponse
from database import supabase
from routers.auth import require_team

router = APIRouter(prefix="/escape-room", tags=["Escape Room"])

# Define your 4 puzzles and their correct answers
PUZZLES = {
    1: {"question": "Puzzle 1: Decode the first clue...", "answer": "apple"},
    2: {"question": "Puzzle 2: Solve the second riddle...", "answer": "bravo"},
    3: {"question": "Puzzle 3: Crack the third cipher...", "answer": "charlie"},
    4: {"question": "Puzzle 4: The final hurdle...", "answer": "delta"}
}

@router.get("", response_class=HTMLResponse)
async def escape_room_page(request: Request, team: dict = Depends(require_team)):
    settings_res = supabase.table("app_settings").select("key, is_active").execute()
    settings = {s["key"]: s["is_active"] for s in settings_res.data} if settings_res.data else {}
    escape_visible = settings.get("puzzle_room_active", False)

    # Fetch current team's escape room progress (or store stage in a database table/session)
    # Let's assume a table 'team_puzzle_progress' with columns: team_id, current_stage (int default 1)
    prog_res = supabase.table("team_puzzle_progress").select("current_stage").eq("team_id", team["id"]).execute()
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
    
    # Check if answer is correct for the given stage
    if stage in PUZZLES and clean_answer == PUZZLES[stage]["answer"]:
        next_stage = stage + 1
        # Upsert next stage into database
        supabase.table("team_puzzle_progress").upsert({
            "team_id": team["id"],
            "current_stage": next_stage
        }, on_conflict="team_id").execute()

    return RedirectResponse(url="/escape-room", status_code=status.HTTP_303_SEE_OTHER)
