from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CATALOG_CACHE = Path(__file__).resolve().parents[1] / ".cache" / "shows.json"


class Settings(BaseSettings):
    """Application settings, read from environment variables or a `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    # Tried in order when the main model is rate limited, over capacity or times out.
    # In .env, a comma-separated list: GROQ_FALLBACK_MODELS=openai/gpt-oss-20b,another/model
    groq_fallback_models: Annotated[list[str], NoDecode] = ["openai/gpt-oss-20b"]
    # When set, the built React app is served from this directory at "/".
    frontend_dist: Path | None = None
    # The show catalogue is downloaded from TVmaze and cached here.
    catalog_cache_path: Path = DEFAULT_CATALOG_CACHE
    # Refresh the cache in the background once it is older than this.
    catalog_max_age_hours: float = 24 * 7
    # When false, only the cache file is used and TVmaze is never contacted (tests).
    sync_catalog: bool = True

    @field_validator("groq_fallback_models", mode="before")
    @classmethod
    def split_model_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [model.strip() for model in value.split(",") if model.strip()]
        return value

    @property
    def groq_models(self) -> list[str]:
        return [self.groq_model, *self.groq_fallback_models]


@lru_cache
def get_settings() -> Settings:
    return Settings()
