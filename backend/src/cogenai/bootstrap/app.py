from fastapi import FastAPI

from cogenai.bootstrap import get_settings
from cogenai.bootstrap.logging import get_logger, configure_logging

logger = get_logger(__name__)

def create_app() -> FastAPI:

    # Configure logging
    configure_logging()

    # Settings
    settings = get_settings()

    # Create app
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="1.0.0",
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "environment": settings.app_env}

    logger.info(
        "application_started",
        environment=settings.app_env,
        provider=settings.llm_provider,
    )

    return app

# Create the app instance
app = create_app()
