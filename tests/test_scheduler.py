"""Basic tests for ARIZE TV Scheduler."""

import pytest
from datetime import date


def test_imports():
    """Verify all modules are importable."""
    from src.config import settings
    from src.models.schemas import SchedulePushRequest, ScheduleEntryResponse
    assert settings.timezone == "America/Chicago"


def test_board_type_validation():
    """Verify board_type enum constraints."""
    from src.models.schemas import SchedulePushRequest

    # Valid request
    req = SchedulePushRequest(
        schedule_date=date.today(),
        board_type="mainboard",
        html_content="<div>Test</div>",
    )
    assert req.board_type == "mainboard"


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
    assert settings.tv_refresh_interval == 60
    assert settings.default_version("mainboard") == "rx"
    assert settings.default_version("modboard") == "mod"
