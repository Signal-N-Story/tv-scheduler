"""TV Display endpoints — unauthenticated, served to Fire TV browsers."""

from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from src.config import settings
from src.models.database import get_db
from src.services.fallback import resolve_card_html
from src.services.swap import get_today

router = APIRouter(prefix="/tv", tags=["tv-display"])

TV_WRAPPER = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="{refresh}">
<style>
  * {{ margin:0; padding:0; }}
  body {{ width:1920px; height:1080px; overflow:hidden; background:#000; }}
  iframe {{ width:1920px; height:1080px; border:none; }}
</style>
<script>
  // Auto-refresh via JS (primary), meta refresh as backup
  setTimeout(function() {{ window.location.reload(); }}, {refresh_ms});
</script>
</head>
<body>
{content}
</body>
</html>"""


def _wrap_card(html_content: str) -> str:
    """Wrap card HTML in the auto-refreshing TV shell."""
    refresh_sec = settings.tv_refresh_interval_seconds
    return TV_WRAPPER.format(
        refresh=refresh_sec,
        refresh_ms=refresh_sec * 1000,
        content=html_content,
    )


@router.get("/mainboard", response_class=HTMLResponse)
async def tv_mainboard():
    """Serve today's main board card full-screen.

    TV1 (MAINBOARD_FRONT) and TV3 (MAINBOARD_BACK) point here.
    Falls through 4-layer fallback chain if no card found.
    """
    db = await get_db()
    try:
        today = get_today()
        html, layer = await resolve_card_html(db, today, settings.BOARD_MAINBOARD)
        return HTMLResponse(_wrap_card(html))
    finally:
        await db.close()


@router.get("/modboard", response_class=HTMLResponse)
async def tv_modboard():
    """Serve today's mod board card full-screen.

    TV2 (MODBOARD_FRONT) points here.
    Falls through 4-layer fallback chain if no card found.
    """
    db = await get_db()
    try:
        today = get_today()
        html, layer = await resolve_card_html(db, today, settings.BOARD_MODBOARD)
        return HTMLResponse(_wrap_card(html))
    finally:
        await db.close()


@router.get("/status")
async def tv_health_check():
    """JSON health check — TVs can ping to confirm connectivity."""
    db = await get_db()
    try:
        today = get_today()
        main = await db.execute(
            "SELECT 1 FROM tv_schedule WHERE schedule_date = ? AND board_type = ?",
            (str(today), "mainboard"),
        )
        mod = await db.execute(
            "SELECT 1 FROM tv_schedule WHERE schedule_date = ? AND board_type = ?",
            (str(today), "modboard"),
        )
        return {
            "status": "ok",
            "server_time": datetime.now().isoformat(),
            "mainboard_scheduled": (await main.fetchone()) is not None,
            "modboard_scheduled": (await mod.fetchone()) is not None,
        }
    finally:
        await db.close()
