from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status
from google import genai

from app.catalog import ShowCatalog
from app.config import get_settings
from app.services.episode_generator import EpisodeGenerator, GeminiEpisodeGenerator

SHOWS_FILE = Path(__file__).parent / "data" / "shows.json"


@lru_cache
def get_catalog() -> ShowCatalog:
    return ShowCatalog.from_json_file(SHOWS_FILE)


@lru_cache
def get_episode_generator() -> EpisodeGenerator:
    settings = get_settings()
    if settings.gemini_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Episode generation is not configured: set GEMINI_API_KEY.",
        )
    return GeminiEpisodeGenerator(
        client=genai.Client(api_key=settings.gemini_api_key.get_secret_value()),
        text_model=settings.gemini_text_model,
        image_model=settings.gemini_image_model if settings.generate_images else None,
    )
