"""Health check endpoint.

This endpoint provides liveness check that works even when settings are incomplete.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint.

    Returns 200 OK even if settings are incomplete.
    This is for liveness probe, not readiness.

    Returns:
        Simple status dict
    """
    return {"status": "ok"}