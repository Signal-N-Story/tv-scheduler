"""ATC TV Scheduler — FastAPI Application."""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.models.database import init_db, get_db
from src.routes import schedule, tv_display, dashboard
from src.routes import templates as templates_router
from src.services.swap import execute_midnight_swap, get_today, get_next_swap_time

scheduler = AsyncIOScheduler(timezone=settings.timezone)

APP_VERSION = "2.0.0"


async def midnight_swap_job():
    """Scheduled job: rotate cards at midnight."""
    db = await get_db()
    try:
        result = await execute_midnight_swap(db)
        print(f"[SWAP] Midnight swap complete: {result}")
    except Exception as e:
        print(f"[SWAP] Error during midnight swap: {e}")
    finally:
        await db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup
    await init_db()
    print(f"[INIT] Database initialized at {settings.database_path}")

    # Seed sample templates on first run
    await _seed_sample_templates()

    # Schedule midnight swap
    scheduler.add_job(
        midnight_swap_job,
        "cron",
        hour=settings.swap_hour,
        minute=settings.swap_minute,
        id="midnight_swap",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[INIT] Swap scheduler started — swap at {settings.swap_hour:02d}:{settings.swap_minute:02d} {settings.timezone}")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    print("[SHUTDOWN] Scheduler stopped")


async def _seed_sample_templates():
    """Seed sample card templates if none exist yet."""
    from src.services.templates import list_templates, create_template

    db = await get_db()
    try:
        existing = await list_templates(db)
        if existing:
            return  # Templates already exist

        # Load sample templates from static directory
        samples_dir = Path("src/static/samples")
        if not samples_dir.exists():
            return

        sample_meta = {
            "legs_and_loaded.html": ("Legs & Loaded", "mainboard", "rx"),
            "flexecution_day.html": ("Flexecution Day", "mainboard", "rx"),
            "legs_web.html": ("Legs Web — 5 Round Challenge", "mainboard", "rx"),
            "bermuda_triangle.html": ("Bermuda Triangle", "modboard", "mod"),
            "leg_relay.html": ("Leg Relay", "mainboard", "rx"),
        }

        for filename, (name, board_type, version) in sample_meta.items():
            filepath = samples_dir / filename
            if filepath.exists():
                html = filepath.read_text(encoding="utf-8")
                await create_template(db, name, board_type, html, version)
                print(f"[INIT] Seeded template: {name}")
    finally:
        await db.close()


app = FastAPI(
    title="ATC TV Scheduler",
    description="Automated workout card scheduling and display system for ATC",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Include routers
app.include_router(schedule.router)
app.include_router(tv_display.router)
app.include_router(dashboard.router)
app.include_router(templates_router.router)


@app.get("/")
async def root():
    """Root endpoint — redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/health")
async def health():
    """Enhanced health check with system diagnostics."""
    db = await get_db()
    try:
        # DB check
        cursor = await db.execute("SELECT COUNT(*) FROM tv_schedule")
        schedule_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tv_schedule WHERE status = 'live'"
        )
        live_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM card_templates")
        template_count = (await cursor.fetchone())[0]

        # Cache check
        cache_path = settings.cache_path
        cache_files = list(cache_path.glob("*.html"))

        # JSON backup check
        backup_path = Path(settings.backup_json_path)

        # Scheduler check
        next_swap = get_next_swap_time()
        scheduler_running = scheduler.running

        return {
            "status": "ok",
            "service": "arize-tv-scheduler",
            "version": APP_VERSION,
            "timestamp": datetime.now().isoformat(),
            "auth_enabled": bool(settings.api_key),
            "database": {
                "path": settings.database_path,
                "total_entries": schedule_count,
                "live_cards": live_count,
                "templates": template_count,
            },
            "fallback": {
                "cache_files": len(cache_files),
                "json_backup_exists": backup_path.exists(),
                "json_backup_size": backup_path.stat().st_size if backup_path.exists() else 0,
            },
            "scheduler": {
                "running": scheduler_running,
                "next_swap_at": next_swap.isoformat(),
                "swap_time": f"{settings.swap_hour:02d}:{settings.swap_minute:02d}",
                "timezone": settings.timezone,
            },
            "today": str(get_today()),
        }
    finally:
        await db.close()
