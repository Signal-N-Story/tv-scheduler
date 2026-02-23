"""SQLite database setup and connection management."""

import aiosqlite
from pathlib import Path
from src.config import settings

DATABASE_PATH = settings.database_path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tv_schedule (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_date   DATE NOT NULL,
    board_type      TEXT NOT NULL CHECK(board_type IN ('mainboard', 'modboard')),
    workout_title   TEXT NOT NULL,
    workout_date_label TEXT,
    version         TEXT CHECK(version IN ('rx', 'scaled', 'mod')),
    html_content    TEXT NOT NULL,
    html_hash       TEXT,
    status          TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'live', 'archived', 'overridden')),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    pushed_by       TEXT,
    UNIQUE(schedule_date, board_type)
);

CREATE INDEX IF NOT EXISTS idx_schedule_date ON tv_schedule(schedule_date);
CREATE INDEX IF NOT EXISTS idx_schedule_status ON tv_schedule(status);

CREATE TABLE IF NOT EXISTS tv_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT NOT NULL,
    schedule_date   DATE,
    board_type      TEXT,
    details         TEXT,
    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON tv_audit_log(timestamp);
"""


async def get_db() -> aiosqlite.Connection:
    """Get an async database connection."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize database schema."""
    db = await get_db()
    try:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    finally:
        await db.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
    print(f"Database initialized at {DATABASE_PATH}")