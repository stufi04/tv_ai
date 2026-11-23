from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_episode_generator
from app.main import create_app
from tests.fakes import FakeEpisodeGenerator

SHOWS_FIXTURE = Path(__file__).parent / "data" / "shows.json"


def offline_settings(**overrides: object) -> Settings:
    """Settings that serve the fixture catalogue and never contact TVmaze."""
    return Settings(_env_file=None, catalog_cache_path=SHOWS_FIXTURE, sync_catalog=False, **overrides)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Playwright's sync API keeps an event loop running on the main thread for the rest of the session,
    # which breaks `asyncio.run` in later tests, so browser tests always run last.
    items.sort(key=lambda item: item.get_closest_marker("e2e") is not None)


@pytest.fixture
def fake_generator() -> FakeEpisodeGenerator:
    return FakeEpisodeGenerator()


@pytest.fixture
def app(fake_generator: FakeEpisodeGenerator) -> FastAPI:
    app = create_app(offline_settings())
    app.dependency_overrides[get_episode_generator] = lambda: fake_generator
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client
