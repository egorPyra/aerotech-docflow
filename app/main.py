"""FastAPI application entrypoint.

This module creates the HTTP application and wires API routers. Keep startup
logic small here; application behavior should live in dedicated modules.
"""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """Return a minimal health response for local checks and monitoring."""
        return {"status": "ok"}

    return app


app = create_app()

