"""
PULSE -- Backend Demo UI

Wraps api.py's two JSON endpoints with a small human-facing surface:
a mock banking event simulator (index.html) and a personalization
dashboard (dashboard.html). These read/write the exact same
/session/event and /user/{id}/personalization endpoints api.py
already exposes -- this file adds no new business logic, only routes
to serve the HTML/CSS/JS that were sitting in templates/ and static/
unused.
"""

from pathlib import Path

import api
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="PULSE Backend UI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Real JSON API -- /session/event, /user/{id}/personalization, /health.
app.include_router(api.app.router)

# Demo UI -- static assets + the two HTML routes app.js expects.
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/dashboard/{user_id}", response_class=HTMLResponse)
def dashboard(request: Request, user_id: str):
    profile = api.PROFILES.get(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"no personalization profile found for user_id={user_id!r}")
    return templates.TemplateResponse(request, "dashboard.html", {"user_id": user_id, "profile": profile})
