"""API key authentication for schedule management endpoints."""

import hmac
from typing import Optional
from fastapi import Header, HTTPException

from src.config import settings


async def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """FastAPI dependency — validates API key if configured.

    If settings.api_key is empty, authentication is disabled (open access).
    """
    if not settings.api_key:
        return  # Auth disabled

    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key header")

    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(403, "Invalid API key")
