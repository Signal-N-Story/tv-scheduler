"""Tests for ARIZE TV Scheduler."""

import pytest
from datetime import date
from pathlib import Path


def test_imports():
    """Verify all modules are importable."""
    from src.config import settings
    from src.models.schemas import SchedulePushRequest, ScheduleEntryResponse
    from src.services.auth import require_api_key
    from src.services.templates import create_template, list_templates
    assert settings.timezone == "America/Chicago"


def test_board_type_validation():
    """Verify board_type enum constraints."""
    from src.models.schemas import ScheduleEntry

    # Valid entry
    entry = ScheduleEntry(
        schedule_date=date.today(),
        board_type="mainboard",
        workout_title="Test Workout",
        html_content="<div>Test</div>",
    )
    assert entry.board_type == "mainboard"


def test_board_type_invalid():
    """Verify invalid board_type is rejected."""
    from pydantic import ValidationError
    from src.models.schemas import ScheduleEntry

    with pytest.raises(ValidationError):
        ScheduleEntry(
            schedule_date=date.today(),
            board_type="invalid",
            workout_title="Test",
            html_content="<div>Test</div>",
        )


def test_schedule_push_request():
    """Verify SchedulePushRequest wraps entries correctly."""
    from src.models.schemas import SchedulePushRequest, ScheduleEntry

    entry = ScheduleEntry(
        schedule_date=date.today(),
        board_type="modboard",
        workout_title="Legs Web",
        html_content="<div>Legs</div>",
        version="mod",
    )
    req = SchedulePushRequest(entries=[entry])
    assert len(req.entries) == 1
    assert req.entries[0].board_type == "modboard"
    assert req.entries[0].version == "mod"


def test_fallback_hash():
    """Test HTML hash computation."""
    from src.services.fallback import compute_html_hash

    h1 = compute_html_hash("<div>Hello</div>")
    h2 = compute_html_hash("<div>Hello</div>")
    h3 = compute_html_hash("<div>World</div>")

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # SHA256 hex digest


def test_splash_html():
    """Test splash screen fallback."""
    from src.services.fallback import get_splash_html

    html = get_splash_html()
    assert "ARIZE" in html
    assert "180 Fitness" in html


def test_settings_defaults():
    """Verify settings default values."""
    from src.config import settings

    assert settings.swap_hour == 0
    assert settings.swap_minute == 0
    assert settings.tv_refresh_interval_seconds == 60
    assert settings.default_version("mainboard") == "rx"
    assert settings.default_version("modboard") == "mod"


def test_settings_api_key_default():
    """Verify API key defaults to empty (auth disabled)."""
    from src.config import settings
    assert settings.api_key == ""


def test_template_schemas():
    """Verify template request/response models."""
    from src.models.schemas import TemplateCreateRequest, TemplateResponse
    from datetime import datetime

    req = TemplateCreateRequest(
        name="Test Template",
        board_type="mainboard",
        version="rx",
        html_content="<div>Template</div>",
    )
    assert req.name == "Test Template"
    assert req.board_type == "mainboard"


def test_clone_schemas():
    """Verify clone request models."""
    from src.models.schemas import CloneDayRequest, CloneWeekRequest

    clone_day = CloneDayRequest(
        source_date=date(2026, 2, 23),
        target_date=date(2026, 3, 2),
        board_type="mainboard",
    )
    assert clone_day.source_date == date(2026, 2, 23)
    assert clone_day.board_type == "mainboard"

    clone_week = CloneWeekRequest(
        source_week_start=date(2026, 2, 23),
        target_week_start=date(2026, 3, 2),
    )
    assert clone_week.source_week_start == date(2026, 2, 23)


def test_clone_day_no_board():
    """Clone day request with no board copies both."""
    from src.models.schemas import CloneDayRequest

    clone = CloneDayRequest(
        source_date=date(2026, 2, 23),
        target_date=date(2026, 3, 2),
    )
    assert clone.board_type is None


def test_sample_templates_exist():
    """Verify all 5 sample HTML template files exist."""
    samples_dir = Path("src/static/samples")
    expected = [
        "legs_and_loaded.html",
        "flexecution_day.html",
        "legs_web.html",
        "bermuda_triangle.html",
        "leg_relay.html",
    ]
    for filename in expected:
        filepath = samples_dir / filename
        assert filepath.exists(), f"Missing sample template: {filename}"
        content = filepath.read_text()
        assert len(content) > 100, f"Sample template too small: {filename}"
        assert "<!DOCTYPE html>" in content, f"Not valid HTML: {filename}"


@pytest.mark.asyncio
async def test_template_crud():
    """Test template create/list/delete operations."""
    import aiosqlite
    from src.services.templates import create_template, get_template, list_templates, delete_template

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS card_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            board_type TEXT NOT NULL,
            version TEXT,
            html_content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create
    row_id = await create_template(db, "Test Card", "mainboard", "<div>Test</div>", "rx")
    assert row_id > 0

    # Get
    tmpl = await get_template(db, row_id)
    assert tmpl is not None
    assert tmpl["name"] == "Test Card"
    assert tmpl["board_type"] == "mainboard"

    # List
    all_templates = await list_templates(db)
    assert len(all_templates) == 1

    # List filtered
    filtered = await list_templates(db, board_type="modboard")
    assert len(filtered) == 0

    # Delete
    deleted = await delete_template(db, row_id)
    assert deleted is True

    # Verify deletion
    tmpl = await get_template(db, row_id)
    assert tmpl is None

    await db.close()


@pytest.mark.asyncio
async def test_audit_log_pagination():
    """Test audit log with pagination and filtering."""
    import aiosqlite
    from src.services.audit import log_action, get_audit_log

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS tv_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            schedule_date DATE,
            board_type TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create some entries
    await log_action(db, "schedule", date(2026, 2, 23), "mainboard", {"title": "Test"})
    await log_action(db, "edit", date(2026, 2, 23), "mainboard", {"changes": ["html"]})
    await log_action(db, "schedule", date(2026, 2, 24), "modboard", {"title": "Test2"})

    # All entries
    entries, total = await get_audit_log(db, page=1, page_size=50)
    assert total == 3
    assert len(entries) == 3

    # Filter by action
    entries, total = await get_audit_log(db, page=1, page_size=50, action_filter="schedule")
    assert total == 2

    # Filter by board
    entries, total = await get_audit_log(db, page=1, page_size=50, board_filter="modboard")
    assert total == 1
    assert entries[0]["board_type"] == "modboard"

    # Pagination
    entries, total = await get_audit_log(db, page=1, page_size=2)
    assert total == 3
    assert len(entries) == 2

    await db.close()
