from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status
from google import genai
from google.genai import types

from app.catalog import ShowCatalog
from app.config import get_settings
from app.services.episode_generator import EpisodeGenerator, GeminiEpisodeGenerator

SHOWS_FILE = Path(__file__).parent / "data" / "shows.json"

# Without these the SDK never times out and never retries, so an overloaded model can hang a request forever.
GEMINI_HTTP_OPTIONS = types.HttpOptions(
    timeout=90_000,  # milliseconds, per attempt
    retry_options=types.HttpRetryOptions(attempts=3, max_delay=8, http_status_codes=[500, 502, 503, 504]),
)


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
        client=genai.Client(api_key=settings.gemini_api_key.get_secret_value(), http_options=GEMINI_HTTP_OPTIONS),
        text_model=settings.gemini_text_model,
        image_model=settings.gemini_image_model if settings.generate_images else None,
    )
