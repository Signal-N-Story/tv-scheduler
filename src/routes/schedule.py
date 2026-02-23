"""Schedule management API endpoints."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from src.models.database import get_db
from src.models.schemas import (
    SchedulePushRequest,
    ScheduleEditRequest,
    OverrideRequest,
    CloneDayRequest,
    CloneWeekRequest,
    TVStatusResponse,
    AuditLogResponse,
)
from src.services.scheduler import (
    upsert_schedule_entry,
    get_schedule_for_date,
    get_schedule_range,
    edit_schedule_entry,
    delete_schedule_date,
    apply_override,
)
from src.services.audit import get_audit_log
from src.services.auth import require_api_key
from src.services.swap import get_today, get_next_swap_time

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.post("", dependencies=[Depends(require_api_key)])
async def push_schedule(request: SchedulePushRequest):
    """Push approved cards to the schedule (1-31 days)."""
    db = await get_db()
    try:
        results = []
        for entry in request.entries:
            row_id = await upsert_schedule_entry(
                db,
                schedule_date=entry.schedule_date,
                board_type=entry.board_type,
                workout_title=entry.workout_title,
                html_content=entry.html_content,
                version=entry.version,
                workout_date_label=entry.workout_date_label,
                pushed_by=entry.pushed_by,
            )
            results.append({"id": row_id, "date": str(entry.schedule_date), "board": entry.board_type})

        return {"status": "ok", "scheduled": len(results), "entries": results}
    finally:
        await db.close()


@router.get("")
async def get_schedule(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(31, ge=1, le=100),
):
    """Get the full schedule (paginated, optional date range)."""
    db = await get_db()
    try:
        entries, total = await get_schedule_range(db, start, end, page, page_size)
        return {"entries": entries, "total": total, "page": page, "page_size": page_size}
    finally:
        await db.close()


@router.get("/status")
async def get_live_status():
    """Current live status — what's on each TV right now."""
    db = await get_db()
    try:
        today = get_today()
        schedule = await get_schedule_for_date(db, today)
        from datetime import datetime
        return {
            "mainboard": schedule.get("mainboard"),
            "modboard": schedule.get("modboard"),
            "next_swap_at": get_next_swap_time().isoformat(),
            "server_time": datetime.now().isoformat(),
        }
    finally:
        await db.close()


@router.get("/audit")
async def get_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None),
    board: Optional[str] = Query(None),
):
    """Audit log of all schedule changes."""
    db = await get_db()
    try:
        entries, total = await get_audit_log(db, page, page_size, action_filter=action, board_filter=board)
        return {"entries": entries, "total": total, "page": page, "page_size": page_size}
    finally:
        await db.close()


@router.get("/{target_date}")
async def get_schedule_by_date(target_date: date):
    """Get cards scheduled for a specific date."""
    db = await get_db()
    try:
        return await get_schedule_for_date(db, target_date)
    finally:
        await db.close()


@router.put("/{target_date}/{board_type}", dependencies=[Depends(require_api_key)])
async def edit_scheduled_card(
    target_date: date,
    board_type: str,
    request: ScheduleEditRequest,
):
    """Edit a future scheduled card."""
    if board_type not in ("mainboard", "modboard"):
        raise HTTPException(400, "board_type must be 'mainboard' or 'modboard'")

    today = get_today()
    if target_date < today:
        raise HTTPException(400, "Cannot edit past schedule entries")

    db = await get_db()
    try:
        result = await edit_schedule_entry(
            db, target_date, board_type,
            html_content=request.html_content,
            workout_title=request.workout_title,
            version=request.version,
        )
        if not result:
            raise HTTPException(404, f"No entry for {target_date} / {board_type}")
        return result
    finally:
        await db.close()


@router.delete("/{target_date}", dependencies=[Depends(require_api_key)])
async def delete_scheduled_date(target_date: date):
    """Remove a scheduled day."""
    today = get_today()
    if target_date < today:
        raise HTTPException(400, "Cannot delete past schedule entries")

    db = await get_db()
    try:
        count = await delete_schedule_date(db, target_date)
        if count == 0:
            raise HTTPException(404, f"No entries for {target_date}")
        return {"status": "ok", "deleted": count, "date": str(target_date)}
    finally:
        await db.close()


@router.post("/clone", dependencies=[Depends(require_api_key)])
async def clone_day(request: CloneDayRequest):
    """Clone cards from one date to another."""
    from src.services.swap import get_today
    today = get_today()
    if request.target_date < today:
        raise HTTPException(400, "Cannot clone to a past date")

    db = await get_db()
    try:
        source = await get_schedule_for_date(db, request.source_date)
        boards = [request.board_type] if request.board_type else ["mainboard", "modboard"]
        cloned = []
        for board in boards:
            card = source.get(board)
            if card:
                row_id = await upsert_schedule_entry(
                    db,
                    schedule_date=request.target_date,
                    board_type=board,
                    workout_title=card["workout_title"],
                    html_content=card["html_content"],
                    version=card.get("version"),
                    workout_date_label=card.get("workout_date_label"),
                    pushed_by="clone",
                )
                cloned.append({"id": row_id, "board": board})

        if not cloned:
            raise HTTPException(404, f"No cards found on {request.source_date} to clone")
        return {"status": "ok", "cloned": len(cloned), "entries": cloned}
    finally:
        await db.close()


@router.post("/clone-week", dependencies=[Depends(require_api_key)])
async def clone_week(request: CloneWeekRequest):
    """Clone an entire week of cards to another week."""
    from datetime import timedelta
    today = get_today()
    if request.target_week_start < today:
        raise HTTPException(400, "Cannot clone to a past week")

    db = await get_db()
    try:
        cloned = []
        for day_offset in range(7):
            source_date = request.source_week_start + timedelta(days=day_offset)
            target_date = request.target_week_start + timedelta(days=day_offset)
            source = await get_schedule_for_date(db, source_date)
            for board in ["mainboard", "modboard"]:
                card = source.get(board)
                if card:
                    row_id = await upsert_schedule_entry(
                        db,
                        schedule_date=target_date,
                        board_type=board,
                        workout_title=card["workout_title"],
                        html_content=card["html_content"],
                        version=card.get("version"),
                        workout_date_label=card.get("workout_date_label"),
                        pushed_by="clone_week",
                    )
                    cloned.append({"id": row_id, "date": str(target_date), "board": board})

        if not cloned:
            raise HTTPException(404, "No cards found in source week to clone")
        return {"status": "ok", "cloned": len(cloned), "entries": cloned}
    finally:
        await db.close()


@router.post("/override", dependencies=[Depends(require_api_key)])
async def emergency_override(request: OverrideRequest):
    """Emergency override — instant card swap."""
    db = await get_db()
    try:
        result = await apply_override(
            db,
            board_type=request.board_type,
            html_content=request.html_content,
            source_date=request.source_date,
            version=request.version,
            reason=request.reason,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        await db.close()
