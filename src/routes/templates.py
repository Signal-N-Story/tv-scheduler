"""Card template API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from src.models.database import get_db
from src.models.schemas import TemplateCreateRequest
from src.services.auth import require_api_key
from src.services.templates import (
    create_template,
    get_template,
    list_templates,
    delete_template,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
async def get_templates(board_type: Optional[str] = Query(None)):
    """List all card templates."""
    db = await get_db()
    try:
        templates = await list_templates(db, board_type)
        return {"templates": templates}
    finally:
        await db.close()


@router.get("/{template_id}")
async def get_template_by_id(template_id: int):
    """Get a single card template."""
    db = await get_db()
    try:
        template = await get_template(db, template_id)
        if not template:
            raise HTTPException(404, f"Template {template_id} not found")
        return template
    finally:
        await db.close()


@router.post("", dependencies=[Depends(require_api_key)])
async def save_template(request: TemplateCreateRequest):
    """Create or update a card template."""
    db = await get_db()
    try:
        row_id = await create_template(
            db,
            name=request.name,
            board_type=request.board_type,
            html_content=request.html_content,
            version=request.version,
        )
        return {"status": "ok", "id": row_id, "name": request.name}
    finally:
        await db.close()


@router.delete("/{template_id}", dependencies=[Depends(require_api_key)])
async def remove_template(template_id: int):
    """Delete a card template."""
    db = await get_db()
    try:
        deleted = await delete_template(db, template_id)
        if not deleted:
            raise HTTPException(404, f"Template {template_id} not found")
        return {"status": "ok", "deleted": template_id}
    finally:
        await db.close()
