"""Tests for the Gemini integration, using a stub in place of the google-genai client."""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors, types

from app.models import EpisodeDraft, Show
from app.services.episode_generator import GeminiEpisodeGenerator, RateLimitedError

DRAFT = EpisodeDraft(title="Pilot", logline="It begins.", story="Once upon a time.", image_prompt="A desert.")

BREAKING_BAD = Show(
    id="breaking-bad", title="Breaking Bad", year=2008, network="AMC", genres=["Drama"], summary="Chemistry."
)
THE_OFFICE = Show(id="the-office", title="The Office", year=2005, network="NBC", genres=["Comedy"], summary="Paper.")


def text_response(draft: EpisodeDraft) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(parsed=draft)


def image_response(data: bytes) -> types.GenerateContentResponse:
    part = types.Part(inline_data=types.Blob(data=data, mime_type="image/png"))
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[part]))])


class StubGeminiClient:
    """Mimics `client.aio.models.generate_content`, answering per model name."""

    def __init__(self, responses: dict[str, types.GenerateContentResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate_content))

    async def _generate_content(self, *, model: str, contents: str, config: Any) -> Any:
        self.calls.append({"model": model, "contents": contents})
        response = self.responses[model]
        if isinstance(response, Exception):
            raise response
        return response


def make_generator(client: StubGeminiClient, image_model: str | None = "image-model") -> GeminiEpisodeGenerator:
    return GeminiEpisodeGenerator(client=client, text_model="text-model", image_model=image_model)  # type: ignore[arg-type]


def test_generates_crossover_episode_with_image() -> None:
    client = StubGeminiClient({"text-model": text_response(DRAFT), "image-model": image_response(b"png")})

    episode = asyncio.run(make_generator(client).generate([BREAKING_BAD, THE_OFFICE]))

    assert episode.title == "Pilot"
    assert episode.show_ids == ["breaking-bad", "the-office"]
    assert episode.image_data_url == "data:image/png;base64,cG5n"
    story_prompt = client.calls[0]["contents"]
    assert "crossover" in story_prompt
    assert "Breaking Bad" in story_prompt and "The Office" in story_prompt
    assert "A desert." in client.calls[1]["contents"]


def test_returns_episode_without_image_when_image_model_fails() -> None:
    quota_error = errors.APIError(429, {"error": {"message": "No quota", "status": "RESOURCE_EXHAUSTED"}})
    client = StubGeminiClient({"text-model": text_response(DRAFT), "image-model": quota_error})

    episode = asyncio.run(make_generator(client).generate([BREAKING_BAD]))

    assert episode.title == "Pilot"
    assert episode.image_data_url is None


def test_skips_image_when_disabled() -> None:
    client = StubGeminiClient({"text-model": text_response(DRAFT)})

    episode = asyncio.run(make_generator(client, image_model=None).generate([BREAKING_BAD]))

    assert episode.image_data_url is None
    assert [call["model"] for call in client.calls] == ["text-model"]


def test_text_rate_limit_raises_rate_limited_error() -> None:
    quota_error = errors.APIError(429, {"error": {"message": "No quota", "status": "RESOURCE_EXHAUSTED"}})
    client = StubGeminiClient({"text-model": quota_error})

    with pytest.raises(RateLimitedError):
        asyncio.run(make_generator(client).generate([BREAKING_BAD]))
