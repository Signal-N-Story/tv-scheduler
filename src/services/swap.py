"""Midnight card swap service — auto-rotates cards daily."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import aiosqlite

from src.config import settings
from src.services.audit import log_action


def get_today() -> date:
    """Get today's date in the configured timezone."""
    tz = ZoneInfo(settings.timezone)
    return datetime.now(tz).date()


def get_next_swap_time() -> datetime:
    """Calculate the next midnight swap time."""
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    tomorrow = now.replace(
        hour=settings.swap_hour,
        minute=settings.swap_minute,
        second=0,
        microsecond=0,
    )
    if tomorrow <= now:
        from datetime import timedelta
        tomorrow += timedelta(days=1)
    return tomorrow


async def execute_midnight_swap(db: aiosqlite.Connection):
    """Run the midnight card rotation.

    1. Archive yesterday's cards (status → 'archived')
    2. Activate today's cards (status → 'live')
    """
    today = get_today()
    from datetime import timedelta
    yesterday = today - timedelta(days=1)

    # Archive yesterday
    await db.execute(
        """UPDATE tv_schedule SET status = 'archived', updated_at = CURRENT_TIMESTAMP
           WHERE schedule_date = ? AND status IN ('live', 'overridden')""",
        (str(yesterday),),
    )

    # Activate today
    cursor = await db.execute(
        """UPDATE tv_schedule SET status = 'live', updated_at = CURRENT_TIMESTAMP
           WHERE schedule_date = ? AND status = 'scheduled'""",
        (str(today),),
    )
    activated = cursor.rowcount

    await db.commit()

    # Audit
    await log_action(
        db, "swap", today, None,
        {"activated_count": activated, "from_date": str(yesterday)},
    )

    return {"date": str(today), "activated": activated}
