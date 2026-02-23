"""Dashboard route — serves the management UI."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Full management dashboard UI."""
    return templates.TemplateResponse("dashboard.html", {"request": request})
