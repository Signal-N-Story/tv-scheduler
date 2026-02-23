"""Audit logging for all schedule actions."""

from datetime import date, datetime
from typing import Optional
import json
import aiosqlite


async def log_action(
    db: aiosqlite.Connection,
    action: str,
    schedule_date: Optional[date],
    board_type: Optional[str],
    details: Optional[dict] = None,
):
    """Write an audit log entry."""
    await db.execute(
        """INSERT INTO tv_audit_log (action, schedule_date, board_type, details)
           VALUES (?, ?, ?, ?)""",
        (action, str(schedule_date) if schedule_date else None,
         board_type, json.dumps(details) if details else None),
    )
    await db.commit()


async def get_audit_log(
    db: aiosqlite.Connection,
    page: int = 1,
    page_size: int = 50,
    action_filter: Optional[str] = None,
    board_filter: Optional[str] = None,
) -> tuple[list[dict], int]:
    """Retrieve audit log entries with optional filtering and pagination."""
    where_clauses: list[str] = []
    params: list = []

    if action_filter:
        where_clauses.append("action = ?")
        params.append(action_filter)
    if board_filter:
        where_clauses.append("board_type = ?")
        params.append(board_filter)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Total count
    cursor = await db.execute(
        f"SELECT COUNT(*) FROM tv_audit_log{where_sql}", params
    )
    total = (await cursor.fetchone())[0]

    # Fetch page
    offset = (page - 1) * page_size
    cursor = await db.execute(
        f"""SELECT * FROM tv_audit_log{where_sql}
            ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows], total
