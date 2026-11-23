"""Fixtures for browser tests: the real FastAPI app serving the built React app, with the LLM faked."""

import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from app.dependencies import get_episode_generator
from app.main import create_app
from tests.conftest import offline_settings
from tests.fakes import FakeEpisodeGenerator

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


@pytest.fixture(scope="session")
def frontend_dist() -> Path:
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm not found: Node.js is required for browser tests")
    if not (FRONTEND_DIR / "node_modules").is_dir():
        pytest.fail("Frontend dependencies missing: run `npm install` in the frontend directory")

    subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR, check=True, capture_output=True)
    return FRONTEND_DIR / "dist"


@pytest.fixture(scope="session")
def session_generator() -> FakeEpisodeGenerator:
    return FakeEpisodeGenerator()


@pytest.fixture
def e2e_generator(session_generator: FakeEpisodeGenerator) -> FakeEpisodeGenerator:
    """The fake behind the live server, reset before each test."""
    session_generator.requests.clear()
    session_generator.error = None
    return session_generator


@pytest.fixture(scope="session")
def live_server_url(frontend_dist: Path, session_generator: FakeEpisodeGenerator) -> Iterator[str]:
    app = create_app(offline_settings(frontend_dist=frontend_dist))
    app.dependency_overrides[get_episode_generator] = lambda: session_generator

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("Test server did not start in time")
        time.sleep(0.05)

    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def base_url(live_server_url: str) -> str:
    """Overrides pytest-base-url so `page.goto("/")` targets the live server."""
    return live_server_url
