from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import auth, participants, party, treasure, puzzle, admin

app = FastAPI(title="Scuffed Olympics")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include all routers
app.include_router(auth.router)
app.include_router(participants.router)
app.include_router(party.router)
app.include_router(treasure.router)
app.include_router(puzzle.router)
app.include_router(admin.router)
