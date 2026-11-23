"""End-to-end tests of the HTTP API, with the LLM replaced by a fake generator."""

import pytest
from fastapi.testclient import TestClient

from app import dependencies
from app.config import Settings
from app.main import create_app
from app.services.episode_generator import EpisodeGenerationError, RateLimitedError
from tests.conftest import offline_settings
from tests.fakes import FakeEpisodeGenerator


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lists_first_page_of_shows(client: TestClient) -> None:
    response = client.get("/api/shows", params={"limit": 5})

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 32
    assert page["nextOffset"] == 5
    assert page["syncing"] is False
    assert len(page["items"]) == 5
    assert page["items"][0].keys() == {"id", "title", "year", "network", "genres", "summary", "imageUrl", "popularity"}


def test_pages_through_all_shows_without_repeats(client: TestClient) -> None:
    ids: list[str] = []
    offset: int | None = 0
    while offset is not None:
        page = client.get("/api/shows", params={"offset": offset, "limit": 10, "seed": 7}).json()
        ids += [show["id"] for show in page["items"]]
        offset = page["nextOffset"]

    assert len(ids) == len(set(ids)) == 32


def test_searches_and_filters_shows(client: TestClient) -> None:
    office = client.get("/api/shows", params={"q": "office"}).json()
    animation = client.get("/api/shows", params={"genre": "Animation"}).json()

    assert [show["id"] for show in office["items"]] == ["the-office"]
    assert {"rick-and-morty", "the-simpsons"} <= {show["id"] for show in animation["items"]}
    assert all("Animation" in show["genres"] for show in animation["items"])


def test_lists_genres(client: TestClient) -> None:
    genres = client.get("/api/genres").json()

    assert "Animation" in genres
    assert genres == sorted(genres)


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_rejects_invalid_paging(client: TestClient, params: dict[str, int]) -> None:
    assert client.get("/api/shows", params=params).status_code == 422


def test_generates_new_episode_for_one_show(client: TestClient, fake_generator: FakeEpisodeGenerator) -> None:
    response = client.post("/api/episodes", json={"showIds": ["breaking-bad"]})

    assert response.status_code == 200
    episode = response.json()
    assert episode["showIds"] == ["breaking-bad"]
    assert episode["title"] == "Breaking Bad: The Lost Episode"
    assert "imageDataUrl" not in episode
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
    monkeypatch.setattr(dependencies, "get_settings", lambda: Settings(_env_file=None, groq_api_key=None))
    dependencies.get_episode_generator.cache_clear()

    with TestClient(create_app(offline_settings())) as client:
        response = client.post("/api/episodes", json={"showIds": ["friends"]})

    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]
