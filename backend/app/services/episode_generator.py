import logging
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.models import Episode, EpisodeDraft, Show

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

SYSTEM_INSTRUCTION = """\
You are a seasoned TV writer. You write new, original episodes for existing shows.
Stay true to each show's characters, tone and setting, but never retell an existing episode.
Keep it family friendly and fun to read."""


class EpisodeGenerationError(Exception):
    """The language model could not produce an episode."""


class RateLimitedError(EpisodeGenerationError):
    """The language model provider rejected the request due to quota or rate limits."""


class EpisodeGenerator(Protocol):
    async def generate(self, shows: Sequence[Show]) -> Episode: ...


def _describe(show: Show) -> str:
    details = ", ".join(str(part) for part in (show.year, show.network) if part)
    return f"{show.title} ({details})" if details else show.title


def build_story_prompt(shows: Sequence[Show]) -> str:
    show_details = "\n".join(f"- {_describe(show)}: {show.summary}" for show in shows)
    if len(shows) == 1:
        task = f"Write a brand-new episode of {shows[0].title}."
    else:
        titles = " and ".join(show.title for show in shows)
        task = f"Write a crossover episode in which the worlds of {titles} collide."
    return f"{task}\n\nAbout the show(s):\n{show_details}"


# Errors worth retrying on a different model: rate limits, capacity (Groq's 498) and server-side failures.
_FALLBACK_STATUS_CODES = {429, 498, 500, 502, 503, 504}

# JSON schema Groq must fill in: the EpisodeDraft fields, nothing else.
_EPISODE_SCHEMA: dict[str, Any] = {**EpisodeDraft.model_json_schema(), "additionalProperties": False}


class _ModelUnavailableError(Exception):
    def __init__(self, model: str, reason: str, *, rate_limited: bool = False) -> None:
        super().__init__(f"{model}: {reason}")
        self.rate_limited = rate_limited


class GroqEpisodeGenerator:
    """Writes episodes with Groq's OpenAI-compatible chat completions API.

    `models` is tried in order: if a model is rate limited, over capacity, failing or times out, the next one
    gets the request, so one busy model doesn't fail the whole request.
    """

    def __init__(self, http: httpx.AsyncClient, models: Sequence[str]) -> None:
        if not models:
            raise ValueError("at least one model is required")
        self._http = http
        self._models = list(dict.fromkeys(models))  # dedupe, keep order

    async def generate(self, shows: Sequence[Show]) -> Episode:
        draft = await self._write_story(shows)
        return Episode(
            show_ids=[show.id for show in shows], title=draft.title, logline=draft.logline, story=draft.story
        )

    async def _write_story(self, shows: Sequence[Show]) -> EpisodeDraft:
        prompt = build_story_prompt(shows)
        failures: list[_ModelUnavailableError] = []
        for model in self._models:
            try:
                draft = await self._write_story_with(model, prompt)
            except _ModelUnavailableError as failure:
                logger.warning("Groq %s; trying the next model", failure)
                failures.append(failure)
                continue
            if failures:
                logger.info("Story written by fallback model %s", model)
            return draft

        tried = ", ".join(self._models)
        if all(failure.rate_limited for failure in failures):
            raise RateLimitedError(f"Groq rate limit reached on every model ({tried}). Please try again shortly.")
        raise EpisodeGenerationError(
            f"Every Groq model is busy right now (tried {tried}). Please try again in a minute."
        )

    async def _write_story_with(self, model: str, prompt: str) -> EpisodeDraft:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "episode", "schema": _EPISODE_SCHEMA},
            },
        }
        try:
            response = await self._http.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise _ModelUnavailableError(model, "timed out") from exc
        except httpx.TransportError as exc:
            raise _ModelUnavailableError(model, f"connection failed ({exc.__class__.__name__})") from exc

        if response.status_code in _FALLBACK_STATUS_CODES:
            raise _ModelUnavailableError(
                model, f"HTTP {response.status_code}", rate_limited=response.status_code == 429
            )
        if response.status_code == 401:
            raise EpisodeGenerationError("Groq rejected the API key: check GROQ_API_KEY.")
        if response.is_error:
            # Bad request, unknown model, etc.: another model won't fix it.
            raise EpisodeGenerationError(f"Groq request failed: {_error_message(response)}")

        try:
            content = response.json()["choices"][0]["message"]["content"]
            return EpisodeDraft.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise _ModelUnavailableError(model, "returned a response we could not parse") from exc


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {response.status_code}"


def create_groq_client(api_key: str, timeout: float = 30) -> httpx.AsyncClient:
    """No retries: a busy model hands over to the next one in the chain instead. Healthy models answer in seconds."""
    return httpx.AsyncClient(base_url=GROQ_BASE_URL, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})
