"""Pydantic models for request/response validation."""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Schedule Models ──────────────────────────────────────────────

class ScheduleEntry(BaseModel):
    """A single card scheduled for a specific date and board."""
    schedule_date: date
    board_type: str = Field(..., pattern="^(mainboard|modboard)$")
    workout_title: str
    workout_date_label: Optional[str] = None
    version: Optional[str] = Field(None, pattern="^(rx|scaled|mod)$")
    html_content: str
    pushed_by: Optional[str] = None


class SchedulePushRequest(BaseModel):
    """Request to push multiple cards to the schedule."""
    entries: list[ScheduleEntry]


class ScheduleEntryResponse(BaseModel):
    """A scheduled card returned from the API."""
    id: int
    schedule_date: date
    board_type: str
    workout_title: str
    workout_date_label: Optional[str]
    version: Optional[str]
    html_hash: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    pushed_by: Optional[str]


class ScheduleDateResponse(BaseModel):
    """Cards for a specific date."""
    date: date
    mainboard: Optional[ScheduleEntryResponse] = None
    modboard: Optional[ScheduleEntryResponse] = None


class ScheduleEditRequest(BaseModel):
    """Request to edit a scheduled card."""
    html_content: Optional[str] = None
    workout_title: Optional[str] = None
    version: Optional[str] = Field(None, pattern="^(rx|scaled|mod)$")


# ── Override Models ──────────────────────────────────────────────

class OverrideRequest(BaseModel):
    """Emergency override — instant card swap."""
    board_type: str = Field(..., pattern="^(mainboard|modboard)$")
    html_content: Optional[str] = None
    source_date: Optional[date] = None
    version: Optional[str] = Field(None, pattern="^(rx|scaled|mod)$")
    reason: Optional[str] = None


# ── Status Models ────────────────────────────────────────────────

class TVStatusResponse(BaseModel):
    """Current live status of all TVs."""
    mainboard: Optional[ScheduleEntryResponse] = None
    modboard: Optional[ScheduleEntryResponse] = None
    next_swap_at: Optional[datetime] = None
    server_time: datetime


class TVHealthCheck(BaseModel):
    """Health check response for TV connectivity."""
    status: str = "ok"
    server_time: datetime
    mainboard_scheduled: bool
    modboard_scheduled: bool


# ── Audit Models ─────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    """A single audit log entry."""
    id: int
    action: str
    schedule_date: Optional[date]
    board_type: Optional[str]
    details: Optional[str]
    timestamp: datetime


class AuditLogResponse(BaseModel):
    """Paginated audit log."""
    entries: list[AuditLogEntry]
    total: int
    page: int
    page_size: int