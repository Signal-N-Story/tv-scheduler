"""ARIZE TV Scheduler — FastAPI Application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.models.database import init_db, get_db
from src.routes import schedule, tv_display, dashboard
from src.services.swap import execute_midnight_swap

scheduler = AsyncIOScheduler(timezone=settings.timezone)


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


app = FastAPI(
    title="ARIZE TV Scheduler",
    description="Automated workout card scheduling and display system for 180 Fitness Club",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Include routers
app.include_router(schedule.router)
app.include_router(tv_display.router)
app.include_router(dashboard.router)


@app.get("/")
async def root():
    """Root endpoint — redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/health")
async def health():
    """Server health check."""
    from datetime import datetime
    return {
        "status": "ok",
        "service": "arize-tv-scheduler",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }