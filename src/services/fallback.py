"""4-Layer Fallback Chain for TV display resilience.

Layer 1: SQLite DB (primary)
Layer 2: JSON Snapshot (backup)
Layer 3: Static HTML Cache (file-based)
Layer 4: Branded Splash Screen (always available)
"""

import json
import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Optional
import aiosqlite

from src.config import settings
from src.services.audit import log_action


# ── Layer 2: JSON Snapshot ───────────────────────────────────────

async def write_json_snapshot(db: aiosqlite.Connection):
    """Write a JSON backup of all scheduled entries.

    Called on every DB write to keep Layer 2 in sync.
    """
    cursor = await db.execute(
        """SELECT schedule_date, board_type, workout_title, version, html_content
           FROM tv_schedule WHERE status IN ('scheduled', 'live')
           ORDER BY schedule_date"""
    )
    rows = await cursor.fetchall()

    # Group by date
    by_date: dict[str, dict] = {}
    for row in rows:
        d = row["schedule_date"]
        if d not in by_date:
            by_date[d] = {"date": d}
        by_date[d][row["board_type"]] = {
            "title": row["workout_title"],
            "version": row["version"],
            "html_file": f"cache/{d}_{row['board_type']}.html",
        }

    snapshot = {
        "last_updated": datetime.now().isoformat(),
        "entries": list(by_date.values()),
    }

    Path(settings.backup_json_path).write_text(json.dumps(snapshot, indent=2))


# ── Layer 3: Static HTML Cache ───────────────────────────────────

async def write_html_cache(
    schedule_date: date,
    board_type: str,
    html_content: str,
):
    """Write a static HTML file to the cache directory.

    Called alongside every DB write for Layer 3 fallback.
    """
    cache_dir = settings.cache_path
    filename = f"{schedule_date}_{board_type}.html"
    (cache_dir / filename).write_text(html_content, encoding="utf-8")


def read_html_cache(schedule_date: date, board_type: str) -> Optional[str]:
    """Read a cached HTML file (Layer 3 fallback)."""
    cache_dir = settings.cache_path
    filename = f"{schedule_date}_{board_type}.html"
    filepath = cache_dir / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return None


# ── Layer 4: Branded Splash Screen ──────────────────────────────

def get_splash_html() -> str:
    """Return the branded splash screen HTML (Layer 4 — last resort)."""
    splash_path = Path(settings.splash_html)
    if splash_path.exists():
        return splash_path.read_text(encoding="utf-8")

    # Inline fallback if template file is missing
    return """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="300">
<style>
  body { margin:0; background:#000; display:flex; align-items:center;
         justify-content:center; height:100vh; font-family:Inter,sans-serif; }
  .logo { text-align:center; color:#fff; }
  .logo h1 { font-size:72px; letter-spacing:4px; margin:0; }
  .logo p { font-size:18px; color:#888; margin-top:12px; }
</style>
</head><body>
<div class="logo">
  <h1>ARIZE</h1>
  <p>180 Fitness Club</p>
</div>
</body></html>"""


# ── Fallback Chain Resolver ──────────────────────────────────────

async def resolve_card_html(
    db: aiosqlite.Connection,
    target_date: date,
    board_type: str,
) -> tuple[str, int]:
    """Resolve the HTML to display, walking the 4-layer fallback chain.

    Returns (html_content, layer_used).
    Layer 1 = DB, 2 = JSON, 3 = file cache, 4 = splash.
    """

    # Layer 1: SQLite
    cursor = await db.execute(
        """SELECT html_content FROM tv_schedule
           WHERE schedule_date = ? AND board_type = ?
           AND status IN ('scheduled', 'live', 'overridden')""",
        (str(target_date), board_type),
    )
    row = await cursor.fetchone()
    if row:
        return row["html_content"], 1

    # Layer 2: JSON Snapshot
    try:
        snapshot_path = Path(settings.backup_json_path)
        if snapshot_path.exists():
            snapshot = json.loads(snapshot_path.read_text())
            for entry in snapshot.get("entries", []):
                if entry.get("date") == str(target_date):
                    board_data = entry.get(board_type)
                    if board_data and board_data.get("html_file"):
                        html_file = Path(board_data["html_file"])
                        if html_file.exists():
                            await log_action(
                                db, "fallback_triggered",
                                target_date, board_type,
                                {"layer": 2, "source": "json_snapshot"},
                            )
                            return html_file.read_text(encoding="utf-8"), 2
    except Exception:
        pass

    # Layer 3: Static HTML Cache
    cached = read_html_cache(target_date, board_type)
    if cached:
        await log_action(
            db, "fallback_triggered",
            target_date, board_type,
            {"layer": 3, "source": "html_cache"},
        )
        return cached, 3

    # Layer 4: Branded Splash
    await log_action(
        db, "fallback_triggered",
        target_date, board_type,
        {"layer": 4, "source": "splash_screen"},
    )
    return get_splash_html(), 4


def compute_html_hash(html_content: str) -> str:
    """Compute SHA256 hash of HTML content for change detection."""
    return hashlib.sha256(html_content.encode("utf-8")).hexdigest()
