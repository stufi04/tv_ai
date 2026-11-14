"""End-to-end tests of the HTTP API, with Gemini replaced by a fake generator."""

import pytest
from fastapi.testclient import TestClient

from app import dependencies
from app.config import Settings
from app.main import create_app
from app.services.episode_generator import EpisodeGenerationError, RateLimitedError
from tests.fakes import FakeEpisodeGenerator


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lists_shows_sorted_by_title(client: TestClient) -> None:
    response = client.get("/api/shows")

    assert response.status_code == 200
    shows = response.json()
    assert len(shows) > 20
    titles = [show["title"] for show in shows]
    assert titles == sorted(titles)
    assert shows[0].keys() == {"id", "title", "year", "network", "genres", "summary"}


def test_generates_new_episode_for_one_show(client: TestClient, fake_generator: FakeEpisodeGenerator) -> None:
    response = client.post("/api/episodes", json={"showIds": ["breaking-bad"]})

    assert response.status_code == 200
    episode = response.json()
    assert episode["showIds"] == ["breaking-bad"]
    assert episode["title"] == "Breaking Bad: The Lost Episode"
    assert episode["imageDataUrl"].startswith("data:image/png;base64,")
    assert fake_generator.requests == [["breaking-bad"]]


def test_generates_crossover_for_two_shows(client: TestClient, fake_generator: FakeEpisodeGenerator) -> None:
    response = client.post("/api/episodes", json={"showIds": ["the-office", "stranger-things"]})

    assert response.status_code == 200
    assert response.json()["title"] == "The Office x Stranger Things: The Lost Episode"
    assert fake_generator.requests == [["the-office", "stranger-things"]]


@pytest.mark.parametrize(
    "show_ids",
    [
        pytest.param([], id="no shows"),
        pytest.param(["friends", "seinfeld", "lost"], id="too many shows"),
        pytest.param(["friends", "friends"], id="duplicate shows"),
    ],
)
def test_rejects_invalid_selection(
    client: TestClient, fake_generator: FakeEpisodeGenerator, show_ids: list[str]
) -> None:
    response = client.post("/api/episodes", json={"showIds": show_ids})

    assert response.status_code == 422
    assert fake_generator.requests == []


def test_unknown_show_returns_404(client: TestClient, fake_generator: FakeEpisodeGenerator) -> None:
    response = client.post("/api/episodes", json={"showIds": ["friends", "not-a-show"]})

    assert response.status_code == 404
    assert "not-a-show" in response.json()["detail"]
    assert fake_generator.requests == []


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        pytest.param(RateLimitedError("Slow down"), 429, id="rate limited"),
        pytest.param(EpisodeGenerationError("Model failed"), 502, id="upstream failure"),
    ],
)
def test_generation_errors_are_reported(
    client: TestClient, fake_generator: FakeEpisodeGenerator, error: Exception, expected_status: int
) -> None:
    fake_generator.error = error

    response = client.post("/api/episodes", json={"showIds": ["friends"]})

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


def test_missing_api_key_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "get_settings", lambda: Settings(_env_file=None, gemini_api_key=None))
    dependencies.get_episode_generator.cache_clear()

    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.post("/api/episodes", json={"showIds": ["friends"]})

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]
