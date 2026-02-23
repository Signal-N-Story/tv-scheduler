"""Schedule CRUD and business logic."""

from datetime import date, datetime
from typing import Optional
import aiosqlite

from src.services.audit import log_action
from src.services.fallback import (
    compute_html_hash,
    write_html_cache,
    write_json_snapshot,
)


async def upsert_schedule_entry(
    db: aiosqlite.Connection,
    schedule_date: date,
    board_type: str,
    workout_title: str,
    html_content: str,
    version: Optional[str] = None,
    workout_date_label: Optional[str] = None,
    pushed_by: Optional[str] = None,
) -> int:
    """Insert or replace a schedule entry (UPSERT on date+board).

    Also writes to all fallback layers and logs the action.
    Returns the row ID.
    """
    html_hash = compute_html_hash(html_content)

    cursor = await db.execute(
        """INSERT INTO tv_schedule
           (schedule_date, board_type, workout_title, workout_date_label,
            version, html_content, html_hash, status, pushed_by, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, CURRENT_TIMESTAMP)
           ON CONFLICT(schedule_date, board_type)
           DO UPDATE SET
             workout_title = excluded.workout_title,
             workout_date_label = excluded.workout_date_label,
             version = excluded.version,
             html_content = excluded.html_content,
             html_hash = excluded.html_hash,
             status = 'scheduled',
             pushed_by = excluded.pushed_by,
             updated_at = CURRENT_TIMESTAMP""",
        (
            str(schedule_date), board_type, workout_title,
            workout_date_label, version, html_content, html_hash, pushed_by,
        ),
    )
    await db.commit()

    # Write to fallback layers
    await write_html_cache(schedule_date, board_type, html_content)
    await write_json_snapshot(db)

    # Audit
    await log_action(
        db, "schedule", schedule_date, board_type,
        {"title": workout_title, "version": version, "pushed_by": pushed_by},
    )

    return cursor.lastrowid


async def get_schedule_for_date(
    db: aiosqlite.Connection,
    target_date: date,
) -> dict:
    """Get all scheduled cards for a specific date."""
    cursor = await db.execute(
        """SELECT * FROM tv_schedule WHERE schedule_date = ?""",
        (str(target_date),),
    )
    rows = await cursor.fetchall()

    result = {"date": target_date, "mainboard": None, "modboard": None}
    for row in rows:
        result[row["board_type"]] = dict(row)

    return result


async def get_schedule_range(
    db: aiosqlite.Connection,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 31,
) -> tuple[list[dict], int]:
    """Get schedule entries with optional date range and pagination."""
    where_clauses = []
    params = []

    if start_date:
        where_clauses.append("schedule_date >= ?")
        params.append(str(start_date))
    if end_date:
        where_clauses.append("schedule_date <= ?")
        params.append(str(end_date))

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Total count
    cursor = await db.execute(
        f"SELECT COUNT(*) FROM tv_schedule{where_sql}", params
    )
    total = (await cursor.fetchone())[0]

    # Fetch page
    offset = (page - 1) * page_size
    cursor = await db.execute(
        f"""SELECT * FROM tv_schedule{where_sql}
            ORDER BY schedule_date ASC, board_type ASC
            LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    )
    rows = await cursor.fetchall()

    return [dict(row) for row in rows], total


async def edit_schedule_entry(
    db: aiosqlite.Connection,
    target_date: date,
    board_type: str,
    html_content: Optional[str] = None,
    workout_title: Optional[str] = None,
    version: Optional[str] = None,
) -> Optional[dict]:
    """Edit a future scheduled card. Returns updated row or None."""
    # Fetch existing
    cursor = await db.execute(
        """SELECT * FROM tv_schedule
           WHERE schedule_date = ? AND board_type = ?""",
        (str(target_date), board_type),
    )
    existing = await cursor.fetchone()
    if not existing:
        return None

    updates = {}
    if html_content is not None:
        updates["html_content"] = html_content
        updates["html_hash"] = compute_html_hash(html_content)
    if workout_title is not None:
        updates["workout_title"] = workout_title
    if version is not None:
        updates["version"] = version

    if not updates:
        return dict(existing)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())

    await db.execute(
        f"""UPDATE tv_schedule SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE schedule_date = ? AND board_type = ?""",
        values + [str(target_date), board_type],
    )
    await db.commit()

    # Update fallback layers
    final_html = updates.get("html_content", existing["html_content"])
    await write_html_cache(target_date, board_type, final_html)
    await write_json_snapshot(db)

    # Audit
    await log_action(
        db, "edit", target_date, board_type,
        {"changes": list(updates.keys())},
    )

    # Return updated
    cursor = await db.execute(
        "SELECT * FROM tv_schedule WHERE schedule_date = ? AND board_type = ?",
        (str(target_date), board_type),
    )
    return dict(await cursor.fetchone())


async def delete_schedule_date(
    db: aiosqlite.Connection,
    target_date: date,
) -> int:
    """Remove all scheduled cards for a date. Returns count deleted."""
    cursor = await db.execute(
        "SELECT board_type FROM tv_schedule WHERE schedule_date = ?",
        (str(target_date),),
    )
    boards = [row["board_type"] for row in await cursor.fetchall()]

    await db.execute(
        "DELETE FROM tv_schedule WHERE schedule_date = ?",
        (str(target_date),),
    )
    await db.commit()

    # Update JSON snapshot
    await write_json_snapshot(db)

    # Audit
    for board in boards:
        await log_action(db, "delete", target_date, board, {})

    return len(boards)


async def apply_override(
    db: aiosqlite.Connection,
    board_type: str,
    html_content: Optional[str] = None,
    source_date: Optional[date] = None,
    version: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    """Emergency override — instant card swap for today.

    Either provide html_content directly, or source_date to copy
    from another scheduled date.
    """
    from src.services.swap import get_today

    today = get_today()

    if source_date and not html_content:
        cursor = await db.execute(
            """SELECT html_content, workout_title, version FROM tv_schedule
               WHERE schedule_date = ? AND board_type = ?""",
            (str(source_date), board_type),
        )
        source = await cursor.fetchone()
        if not source:
            raise ValueError(f"No card found for {source_date} / {board_type}")
        html_content = source["html_content"]
        version = version or source["version"]

    if not html_content:
        raise ValueError("Either html_content or source_date is required")

    # Mark current as overridden
    await db.execute(
        """UPDATE tv_schedule SET status = 'overridden', updated_at = CURRENT_TIMESTAMP
           WHERE schedule_date = ? AND board_type = ? AND status = 'live'""",
        (str(today), board_type),
    )

    # Upsert override
    row_id = await upsert_schedule_entry(
        db, today, board_type,
        workout_title="OVERRIDE",
        html_content=html_content,
        version=version,
        pushed_by="emergency_override",
    )

    # Set status to overridden
    await db.execute(
        "UPDATE tv_schedule SET status = 'overridden' WHERE id = ?",
        (row_id,),
    )
    await db.commit()

    # Audit
    await log_action(
        db, "override", today, board_type,
        {"reason": reason, "source_date": str(source_date) if source_date else None},
    )

    return {"id": row_id, "board_type": board_type, "date": str(today), "status": "overridden"}
