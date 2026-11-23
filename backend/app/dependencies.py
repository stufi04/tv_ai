from functools import lru_cache

from fastapi import HTTPException, Request, status

from app.catalog import ShowCatalog
from app.config import get_settings
from app.services.catalog_store import CatalogStore
from app.services.episode_generator import EpisodeGenerator, GroqEpisodeGenerator, create_groq_client


def get_catalog_store(request: Request) -> CatalogStore:
    return request.app.state.catalog_store


def get_catalog(request: Request) -> ShowCatalog:
    return get_catalog_store(request).catalog


@lru_cache
def get_episode_generator() -> EpisodeGenerator:
    settings = get_settings()
    if settings.groq_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Episode generation is not configured: set GROQ_API_KEY.",
        )
    return GroqEpisodeGenerator(
        http=create_groq_client(settings.groq_api_key.get_secret_value()),
        models=settings.groq_models,
    )
