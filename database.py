import os
from supabase import create_client, Client
from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize templates and disable the Jinja2 cache to fix the Python/Starlette bug
templates = Jinja2Templates(directory="templates")
templates.env.cache = None
