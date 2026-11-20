import base64
import logging
from collections.abc import Sequence
from typing import Protocol

import httpx
from google import genai
from google.genai import errors, types

from app.models import Episode, EpisodeDraft, Show

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """\
You are a seasoned TV writer. You write new, original episodes for existing shows.
Stay true to each show's characters, tone and setting, but never retell an existing episode.
Keep it family friendly and fun to read."""

IMAGE_STYLE = (
    "A cinematic, painterly illustration of a TV episode's key scene. "
    "Do not render any text, captions, logos or watermarks. "
    "Do not depict the likeness of real actors."
)


class EpisodeGenerationError(Exception):
    """The language model could not produce an episode."""


class RateLimitedError(EpisodeGenerationError):
    """The language model provider rejected the request due to quota or rate limits."""


class EpisodeGenerator(Protocol):
    async def generate(self, shows: Sequence[Show]) -> Episode: ...


def build_story_prompt(shows: Sequence[Show]) -> str:
    show_details = "\n".join(f"- {show.title} ({show.year}, {show.network}): {show.summary}" for show in shows)
    if len(shows) == 1:
        task = f"Write a brand-new episode of {shows[0].title}."
    else:
        titles = " and ".join(show.title for show in shows)
        task = f"Write a crossover episode in which the worlds of {titles} collide."
    return f"{task}\n\nAbout the show(s):\n{show_details}"


class GeminiEpisodeGenerator:
    """Writes episodes with a Gemini text model and illustrates them with an image model."""

    def __init__(self, client: genai.Client, text_model: str, image_model: str | None) -> None:
        self._client = client
        self._text_model = text_model
        self._image_model = image_model

    async def generate(self, shows: Sequence[Show]) -> Episode:
        draft = await self._write_story(shows)
        image_data_url = await self._illustrate(draft.image_prompt) if self._image_model else None
        return Episode(
            show_ids=[show.id for show in shows],
            title=draft.title,
            logline=draft.logline,
            story=draft.story,
            image_data_url=image_data_url,
        )

    async def _write_story(self, shows: Sequence[Show]) -> EpisodeDraft:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._text_model,
                contents=build_story_prompt(shows),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=EpisodeDraft,
                ),
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise RateLimitedError("Gemini rate limit reached. Please try again shortly.") from exc
            if exc.code == 503:
                raise EpisodeGenerationError(
                    f"Gemini model {self._text_model} is overloaded right now. Please try again shortly."
                ) from exc
            raise EpisodeGenerationError(f"Gemini request failed: {exc.message}") from exc
        except httpx.TimeoutException as exc:
            raise EpisodeGenerationError("Gemini took too long to respond. Please try again.") from exc

        if not isinstance(response.parsed, EpisodeDraft):
            raise EpisodeGenerationError("Gemini returned a response we could not understand.")
        return response.parsed

    async def _illustrate(self, scene: str) -> str | None:
        """Best effort: the story is still useful without a picture (image quotas are tight)."""
        assert self._image_model is not None
        try:
            response = await self._client.aio.models.generate_content(
                model=self._image_model,
                contents=f"{IMAGE_STYLE}\n\nScene: {scene}",
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
        except Exception:
            logger.exception("Image generation failed; returning the episode without an image")
            return None

        for part in response.parts or []:
            if part.inline_data and part.inline_data.data:
                mime_type = part.inline_data.mime_type or "image/png"
                encoded = base64.b64encode(part.inline_data.data).decode("ascii")
                return f"data:{mime_type};base64,{encoded}"

        logger.warning("Image model returned no image")
        return None
