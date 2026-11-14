from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import Settings, get_settings
from app.services.episode_generator import EpisodeGenerationError, RateLimitedError


async def handle_generation_error(_: Request, exc: Exception) -> JSONResponse:
    status_code = (
        status.HTTP_429_TOO_MANY_REQUESTS if isinstance(exc, RateLimitedError) else status.HTTP_502_BAD_GATEWAY
    )
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(title="Episode Generator", version="1.0.0")
    app.include_router(router)
    app.add_exception_handler(EpisodeGenerationError, handle_generation_error)

    if settings.frontend_dist:
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")

    return app


app = create_app()
