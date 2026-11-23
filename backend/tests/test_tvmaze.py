"""TVmaze download and the cached catalogue store, with the network replaced by httpx.MockTransport."""

import asyncio
import os
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.models import Show
from app.services.catalog_store import CatalogStore
from app.services.tvmaze import TvmazeClient, clean_summary, to_show

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def raw_show(show_id: int, **overrides: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "id": show_id,
        "name": f"Show {show_id}",
        "premiered": "2008-01-20",
        "genres": ["Drama", "Crime"],
        "weight": 97,
        "network": {"name": "AMC"},
        "webChannel": None,
        "image": {"medium": f"https://static.tvmaze.com/{show_id}.jpg", "original": "x"},
        "summary": "<p><b>Breaking Bad</b> follows a chemistry teacher &amp; his partner.</p>",
    }
    return raw | overrides


def test_to_show_maps_fields() -> None:
    show = to_show(raw_show(169))

    assert show == Show(
        id="169",
        title="Show 169",
        year=2008,
        network="AMC",
        genres=["Drama", "Crime"],
        summary="Breaking Bad follows a chemistry teacher & his partner.",
        image_url="https://static.tvmaze.com/169.jpg",
        popularity=97,
    )


def test_to_show_falls_back_to_web_channel_and_tolerates_missing_fields() -> None:
    show = to_show(raw_show(1, network=None, webChannel={"name": "Netflix"}, premiered=None, image=None, genres=None))

    assert show is not None
    assert (show.network, show.year, show.image_url, show.genres) == ("Netflix", None, None, [])


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"summary": None}, id="no summary"),
        pytest.param({"summary": "<p> </p>"}, id="empty summary"),
        pytest.param({"weight": 0}, id="no popularity"),
        pytest.param({"name": ""}, id="no name"),
    ],
)
def test_to_show_drops_unusable_shows(overrides: dict[str, Any]) -> None:
    assert to_show(raw_show(1, **overrides)) is None


def test_clean_summary() -> None:
    assert clean_summary("<p>One<br>two&nbsp;&quot;three&quot;</p>\n<p>four</p>") == 'One two "three" four'


def fake_tvmaze(pages: int, flaky: set[int] | None = None) -> tuple[httpx.AsyncClient, list[int]]:
    """A TVmaze stand-in with `pages` pages of 3 shows; pages in `flaky` answer 429 once."""
    requested: list[int] = []
    flaky = set(flaky or ())

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        requested.append(page)
        if page in flaky:
            flaky.discard(page)
            return httpx.Response(429)
        if page >= pages:
            return httpx.Response(404)
        return httpx.Response(200, json=[raw_show(page * 3 + n) for n in range(3)] + [raw_show(999, weight=0)])

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.tvmaze.test"), requested


def fast_client(http: httpx.AsyncClient) -> TvmazeClient:
    return TvmazeClient(http, request_interval=0, backoff=0)


async def test_fetches_every_page_until_404() -> None:
    http, requested = fake_tvmaze(pages=10)

    shows = await fast_client(http).fetch_all_shows()

    assert [show.id for show in shows] == [str(n) for n in range(30)]  # in id order, dropped shows removed
    assert 10 in requested
    assert max(requested) < 10 + 4, "should stop shortly after the first 404"


async def test_retries_rate_limited_pages() -> None:
    http, requested = fake_tvmaze(pages=3, flaky={1})

    shows = await fast_client(http).fetch_all_shows()

    assert len(shows) == 9
    assert requested.count(1) == 2


async def test_gives_up_after_repeated_server_errors() -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)), base_url="https://x")

    with pytest.raises(httpx.HTTPStatusError):
        await TvmazeClient(http, request_interval=0, backoff=0, max_attempts=2).fetch_all_shows()


def sample_shows(*show_ids: str) -> list[Show]:
    return [Show(id=i, title=f"T{i}", year=None, network=None, genres=[], summary="s", popularity=50) for i in show_ids]


class FakeSource:
    """Returns the given results in order (repeating the last); an Exception result is raised."""

    def __init__(self, *results: list[Show] | Exception) -> None:
        self._results = list(results)
        self.calls = 0

    async def __call__(self) -> list[Show]:
        result = self._results[min(self.calls, len(self._results) - 1)]
        self.calls += 1
        await asyncio.sleep(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_store(tmp_path: Path, source: FakeSource, check_interval: float = 3600) -> CatalogStore:
    return CatalogStore(tmp_path / "cache" / "shows.json", timedelta(days=7), source, timedelta(seconds=check_interval))


@asynccontextmanager
async def running(store: CatalogStore) -> AsyncIterator[CatalogStore]:
    await store.start()
    try:
        yield store
    finally:
        await store.stop()


def age_cache(tmp_path: Path, days: float) -> None:
    then = time.time() - days * 24 * 3600
    os.utime(tmp_path / "cache" / "shows.json", (then, then))


async def wait_for(condition: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        await asyncio.sleep(0.005)


async def test_store_downloads_and_caches_on_first_run(tmp_path: Path) -> None:
    async with running(make_store(tmp_path, FakeSource(sample_shows("1", "2")))) as store:
        assert store.syncing
        await wait_for(lambda: not store.refreshing)

        assert not store.syncing
        assert len(store.catalog) == 2
        assert (tmp_path / "cache" / "shows.json").exists()


async def test_store_uses_fresh_cache_without_downloading(tmp_path: Path) -> None:
    await make_store(tmp_path, FakeSource(sample_shows("1", "2", "3"))).refresh()

    source = FakeSource(sample_shows("9"))
    async with running(make_store(tmp_path, source, check_interval=0.01)) as store:
        await asyncio.sleep(0.1)  # several periodic checks

        assert len(store.catalog) == 3
        assert source.calls == 0


async def test_store_serves_stale_cache_while_refreshing(tmp_path: Path) -> None:
    await make_store(tmp_path, FakeSource(sample_shows("1"))).refresh()
    age_cache(tmp_path, days=8)

    async with running(make_store(tmp_path, FakeSource(sample_shows("1", "2")))) as store:
        assert len(store.catalog) == 1
        assert store.refreshing and not store.syncing  # old data is served meanwhile
        await wait_for(lambda: len(store.catalog) == 2)


async def test_running_store_refreshes_once_the_cache_goes_stale(tmp_path: Path) -> None:
    await make_store(tmp_path, FakeSource(sample_shows("1"))).refresh()
    source = FakeSource(sample_shows("1", "2"))

    async with running(make_store(tmp_path, source, check_interval=0.01)) as store:
        await asyncio.sleep(0.05)
        assert source.calls == 0  # still fresh

        age_cache(tmp_path, days=8)  # a week passes while the server is up
        await wait_for(lambda: len(store.catalog) == 2)

        await asyncio.sleep(0.05)
        assert source.calls == 1, "the refresh rewrote the cache, so it is fresh again"


async def test_failed_refresh_is_retried_on_the_next_check(tmp_path: Path) -> None:
    source = FakeSource(RuntimeError("TVmaze is down"), sample_shows("1", "2"))

    async with running(make_store(tmp_path, source, check_interval=0.01)) as store:
        await wait_for(lambda: len(store.catalog) == 2)

        assert source.calls == 2


async def test_store_keeps_current_catalogue_when_refresh_fails(tmp_path: Path) -> None:
    await make_store(tmp_path, FakeSource(sample_shows("1"))).refresh()

    store = make_store(tmp_path, FakeSource(RuntimeError("TVmaze is down")))
    store.load_cache()
    await store.refresh()

    assert len(store.catalog) == 1


async def test_store_stop_cancels_refresh(tmp_path: Path) -> None:
    async def never_finishes() -> list[Show]:
        await asyncio.Event().wait()
        return []

    store = CatalogStore(tmp_path / "shows.json", timedelta(days=7), never_finishes)
    await store.start()
    assert store.refreshing
    await store.stop()

    assert not store.refreshing
