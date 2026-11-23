"""Tests for the Groq integration, with Groq's HTTP API replaced by httpx.MockTransport."""

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.models import EpisodeDraft, Show
from app.services.episode_generator import (
    GROQ_BASE_URL,
    EpisodeGenerationError,
    GroqEpisodeGenerator,
    RateLimitedError,
    create_groq_client,
)

DRAFT = EpisodeDraft(title="Pilot", logline="It begins.", story="Once upon a time.\n\nThe end.")

BREAKING_BAD = Show(
    id="breaking-bad", title="Breaking Bad", year=2008, network="AMC", genres=["Drama"], summary="Chemistry."
)
THE_OFFICE = Show(id="the-office", title="The Office", year=2005, network="NBC", genres=["Comedy"], summary="Paper.")
NO_DETAILS = Show(id="x", title="Mystery Show", year=None, network=None, genres=[], summary="Unknown.")

# What the fake Groq returns per model: a draft, an HTTP status code, or an exception to raise.
Reply = EpisodeDraft | int | Exception | str


def completion(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class FakeGroq:
    """Answers /chat/completions per model, recording each request body."""

    def __init__(self, replies: dict[str, Reply]) -> None:
        self.replies = replies
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body | {"_auth": request.headers.get("authorization"), "_path": request.url.path})
        reply = self.replies[body["model"]]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, int):
            return httpx.Response(reply, json={"error": {"message": f"status {reply}", "type": "x"}})
        content = reply if isinstance(reply, str) else reply.model_dump_json()
        return httpx.Response(200, json=completion(content))

    @property
    def models_called(self) -> list[str]:
        return [request["model"] for request in self.requests]


def run(fake: FakeGroq, shows: list[Show], models: tuple[str, ...] = ("main",)) -> Any:
    http = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler), base_url=GROQ_BASE_URL)
    return asyncio.run(GroqEpisodeGenerator(http, models).generate(shows))


def test_generates_episode_from_structured_output() -> None:
    fake = FakeGroq({"main": DRAFT})

    episode = run(fake, [BREAKING_BAD])

    assert (episode.show_ids, episode.title, episode.logline) == (["breaking-bad"], "Pilot", "It begins.")
    assert episode.story == "Once upon a time.\n\nThe end."


def test_sends_prompt_and_json_schema() -> None:
    fake = FakeGroq({"main": DRAFT})

    run(fake, [BREAKING_BAD, THE_OFFICE])

    request = fake.requests[0]
    assert request["_path"] == "/openai/v1/chat/completions"
    system, user = request["messages"]
    assert system["role"] == "system" and "TV writer" in system["content"]
    assert "crossover" in user["content"]
    assert "Breaking Bad (2008, AMC): Chemistry." in user["content"]
    schema = request["response_format"]["json_schema"]["schema"]
    assert request["response_format"]["type"] == "json_schema"
    assert set(schema["properties"]) == set(schema["required"]) == {"title", "logline", "story"}
    assert schema["additionalProperties"] is False


def test_prompt_omits_missing_year_and_network() -> None:
    fake = FakeGroq({"main": DRAFT})

    run(fake, [NO_DETAILS])

    assert "- Mystery Show: Unknown." in fake.requests[0]["messages"][1]["content"]


def test_client_sends_api_key() -> None:
    fake = FakeGroq({"main": DRAFT})
    http = create_groq_client("secret-key")
    http._transport = httpx.MockTransport(fake.handler)  # noqa: SLF001 - keep the real base URL and headers

    asyncio.run(GroqEpisodeGenerator(http, ["main"]).generate([BREAKING_BAD]))

    assert fake.requests[0]["_auth"] == "Bearer secret-key"


FALLBACK_CHAIN = ("main", "backup", "last-resort")


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(503, id="unavailable"),
        pytest.param(500, id="server error"),
        pytest.param(498, id="over capacity"),
        pytest.param(429, id="rate limited"),
        pytest.param(httpx.ReadTimeout("slow"), id="timeout"),
        pytest.param(httpx.ConnectError("no route"), id="connection error"),
        pytest.param("not json", id="unparseable"),
        pytest.param('{"title": "Only a title"}', id="incomplete"),
    ],
)
def test_falls_back_to_next_model(failure: Reply) -> None:
    fake = FakeGroq({"main": failure, "backup": DRAFT})

    episode = run(fake, [BREAKING_BAD], FALLBACK_CHAIN)

    assert episode.title == "Pilot"
    assert fake.models_called == ["main", "backup"]


def test_reports_busy_when_every_model_fails() -> None:
    fake = FakeGroq({"main": 503, "backup": httpx.ReadTimeout("slow"), "last-resort": 429})

    with pytest.raises(EpisodeGenerationError, match="tried main, backup, last-resort") as raised:
        run(fake, [BREAKING_BAD], FALLBACK_CHAIN)

    assert not isinstance(raised.value, RateLimitedError)
    assert fake.models_called == list(FALLBACK_CHAIN)


def test_reports_rate_limit_only_when_every_model_is_rate_limited() -> None:
    fake = FakeGroq({"main": 429, "backup": 429, "last-resort": 429})

    with pytest.raises(RateLimitedError):
        run(fake, [BREAKING_BAD], FALLBACK_CHAIN)


@pytest.mark.parametrize(
    ("status", "message"),
    [
        pytest.param(400, "status 400", id="bad request"),
        pytest.param(404, "status 404", id="unknown model"),
        pytest.param(401, "GROQ_API_KEY", id="bad key"),
    ],
)
def test_does_not_fall_back_on_errors_another_model_wont_fix(status: int, message: str) -> None:
    fake = FakeGroq({"main": status, "backup": DRAFT})

    with pytest.raises(EpisodeGenerationError, match=message):
        run(fake, [BREAKING_BAD], FALLBACK_CHAIN)

    assert fake.models_called == ["main"]


def test_duplicate_models_are_tried_once() -> None:
    fake = FakeGroq({"main": 503})

    with pytest.raises(EpisodeGenerationError):
        run(fake, [BREAKING_BAD], ("main", "main"))

    assert fake.models_called == ["main"]


def test_requires_a_model() -> None:
    with pytest.raises(ValueError, match="at least one model"):
        GroqEpisodeGenerator(httpx.AsyncClient(), [])


def test_fallback_models_setting_accepts_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "main")
    monkeypatch.setenv("GROQ_FALLBACK_MODELS", " backup, last-resort ,")

    assert Settings(_env_file=None).groq_models == ["main", "backup", "last-resort"]
