from fastapi import APIRouter, Depends, Form, Request, UploadFile, File, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from database import supabase
from routers.auth import require_team

router = APIRouter(prefix="/treasure-hunt", tags=["Treasure Hunt"])
templates = Jinja2Templates(directory="templates")

@router.get("", response_class=HTMLResponse)
async def treasure_hunt_page(request: Request, team: dict = Depends(require_team)):
    toggle_res = supabase.table("app_settings").select("is_active").eq("key", "treasure_hunt_active").execute()
    is_active = toggle_res.data[0]["is_active"] if toggle_res.data else False
    
    items_res = supabase.table("treasure_hunt_items").select("*").execute()
    items = items_res.data if items_res.data else []

    progress_res = supabase.table("team_treasure_progress").select("*").eq("team_id", team["id"]).execute()
    progress_map = {p["item_id"]: p for p in progress_res.data} if progress_res.data else {}

    return templates.TemplateResponse("treasure_hunt.html", {
        "request": request, 
        "team": team, 
        "is_active": is_active,
        "items": items,
        "progress_map": progress_map
    })

@router.post("/submit")
async def submit_treasure_item(request: Request, item_id: str = Form(...), photo: UploadFile = File(...), team: dict = Depends(require_team)):
    file_bytes = await photo.read()
    file_path = f"{team['id']}/{item_id}_{photo.filename}"
    
    supabase.storage.from_("treasure-hunt-uploads").upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": photo.content_type}
    )
    
    public_url_res = supabase.storage.from_("treasure-hunt-uploads").get_public_url(file_path)
    image_url = public_url_res if isinstance(public_url_res, str) else public_url_res.get("publicURL", "")

    supabase.table("team_treasure_progress").upsert({
        "team_id": team["id"],
        "item_id": item_id,
        "image_url": image_url,
        "status": "pending"
    }, on_conflict="team_id,item_id").execute()

    return RedirectResponse(url="/treasure-hunt", status_code=status.HTTP_303_SEE_OTHER)
