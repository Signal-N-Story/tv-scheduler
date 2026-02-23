"""Card template CRUD — save and reuse workout card designs."""

from typing import Optional
import aiosqlite


async def create_template(
    db: aiosqlite.Connection,
    name: str,
    board_type: str,
    html_content: str,
    version: Optional[str] = None,
) -> int:
    """Create or update a card template. Returns the row ID."""
    cursor = await db.execute(
        """INSERT INTO card_templates (name, board_type, version, html_content, updated_at)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(name) DO UPDATE SET
             board_type = excluded.board_type,
             version = excluded.version,
             html_content = excluded.html_content,
             updated_at = CURRENT_TIMESTAMP""",
        (name, board_type, version, html_content),
    )
    await db.commit()
    return cursor.lastrowid


async def get_template(db: aiosqlite.Connection, template_id: int) -> Optional[dict]:
    """Get a template by ID."""
    cursor = await db.execute(
        "SELECT * FROM card_templates WHERE id = ?", (template_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_template_by_name(db: aiosqlite.Connection, name: str) -> Optional[dict]:
    """Get a template by name."""
    cursor = await db.execute(
        "SELECT * FROM card_templates WHERE name = ?", (name,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_templates(
    db: aiosqlite.Connection,
    board_type: Optional[str] = None,
) -> list[dict]:
    """List all templates, optionally filtered by board type."""
    if board_type:
        cursor = await db.execute(
            "SELECT * FROM card_templates WHERE board_type = ? ORDER BY name",
            (board_type,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM card_templates ORDER BY name"
        )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def delete_template(db: aiosqlite.Connection, template_id: int) -> bool:
    """Delete a template by ID. Returns True if deleted."""
    cursor = await db.execute(
        "DELETE FROM card_templates WHERE id = ?", (template_id,)
    )
    await db.commit()
    return cursor.rowcount > 0
