import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import Settings, get_settings
from app.models import Show
from app.services.catalog_store import CatalogStore
from app.services.episode_generator import EpisodeGenerationError, RateLimitedError
from app.services.tvmaze import TvmazeClient, create_http_client

# Uvicorn only configures its own loggers; make ours (e.g. catalogue sync progress) visible too.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")


async def handle_generation_error(_: Request, exc: Exception) -> JSONResponse:
    status_code = (
        status.HTTP_429_TOO_MANY_REQUESTS if isinstance(exc, RateLimitedError) else status.HTTP_502_BAD_GATEWAY
    )
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


async def fetch_tvmaze_shows() -> list[Show]:
    async with create_http_client() as http:
        return await TvmazeClient(http).fetch_all_shows()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = CatalogStore(
        cache_path=settings.catalog_cache_path,
        max_age=timedelta(hours=settings.catalog_max_age_hours),
        fetch_shows=fetch_tvmaze_shows,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.sync_catalog:
            await store.start()
        else:
            store.load_cache()
        yield
        await store.stop()

    app = FastAPI(title="Episode Generator", version="1.0.0", lifespan=lifespan)
    app.state.catalog_store = store
    app.include_router(router)
    app.add_exception_handler(EpisodeGenerationError, handle_generation_error)

    if settings.frontend_dist:
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")

    return app


app = create_app()
