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
    action_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Retrieve audit log entries with optional filtering."""
    where = ""
    params: list = []

    if action_filter:
        where = " WHERE action = ?"
        params.append(action_filter)

    cursor = await db.execute(
        f"""SELECT * FROM tv_audit_log{where}
            ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
        params + [limit, offset],
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
