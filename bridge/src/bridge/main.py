"""Main FastAPI application for pulse-bridge."""

import logging

from fastapi import FastAPI

from .routers import health_router, webhooks_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="pulse-bridge",
        description="Misskey webhook bridge for pulse-kestra",
        version="0.1.0",
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(webhooks_router)

    logger.info("pulse-bridge application created")

    return app


# Create application instance
app = create_app()