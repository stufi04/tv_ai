import asyncio
import contextlib
import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path

from app.catalog import ShowCatalog, shows_adapter
from app.models import Show

logger = logging.getLogger(__name__)

FetchShows = Callable[[], Awaitable[list[Show]]]


class CatalogStore:
    """Holds the current show catalogue, backed by a JSON cache file and refreshed from a remote source.

    Startup loads the cache (fast). Whenever the cache is missing or older than `max_age` (checked at startup
    and then every `check_interval` while running), a background refresh downloads the full catalogue, swaps
    it in and rewrites the cache; meanwhile the old catalogue (or an empty one on the very first run) keeps
    being served. A failed refresh leaves the cache stale, so the next check retries it.
    """

    def __init__(
        self,
        cache_path: Path,
        max_age: timedelta,
        fetch_shows: FetchShows,
        check_interval: timedelta = timedelta(hours=1),
    ) -> None:
        self._cache_path = cache_path
        self._max_age = max_age
        self._fetch_shows = fetch_shows
        self._check_interval = check_interval
        self._catalog = ShowCatalog([])
        self._refresh_task: asyncio.Task[None] | None = None
        self._watch_task: asyncio.Task[None] | None = None

    @property
    def catalog(self) -> ShowCatalog:
        return self._catalog

    @property
    def syncing(self) -> bool:
        """True while a refresh is running and there is nothing to serve yet."""
        return self.refreshing and len(self._catalog) == 0

    @property
    def refreshing(self) -> bool:
        return self._refresh_task is not None and not self._refresh_task.done()

    def load_cache(self) -> bool:
        """Load the cache file if present. Returns whether it was loaded."""
        try:
            self._catalog = ShowCatalog.from_json_file(self._cache_path)
        except FileNotFoundError:
            return False
        except ValueError:
            logger.warning("Ignoring unreadable show cache at %s", self._cache_path)
            return False
        logger.info("Loaded %d shows from %s", len(self._catalog), self._cache_path)
        return True

    def cache_is_stale(self) -> bool:
        try:
            age = time.time() - self._cache_path.stat().st_mtime
        except FileNotFoundError:
            return True
        return age > self._max_age.total_seconds()

    async def start(self) -> None:
        """Load the cache, refresh now if it is missing or stale, and keep checking while the app runs."""
        loaded = self.load_cache()
        if not loaded or self.cache_is_stale():
            logger.info("Show cache %s; refreshing from TVmaze in the background", "stale" if loaded else "missing")
            self._start_refresh()
        self._watch_task = asyncio.create_task(self._watch())

    async def stop(self) -> None:
        for task in (self._watch_task, self._refresh_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    def _start_refresh(self) -> None:
        self._refresh_task = asyncio.create_task(self.refresh())

    async def _watch(self) -> None:
        """Periodically re-check the cache age, so a long-running server doesn't serve week-old data forever."""
        while True:
            if self._refresh_task is not None:
                await asyncio.wait([self._refresh_task])  # let a running refresh finish (never raises)
            await asyncio.sleep(self._check_interval.total_seconds())
            if self.cache_is_stale():
                logger.info("Show cache is stale; refreshing from TVmaze in the background")
                self._start_refresh()

    async def refresh(self) -> None:
        try:
            shows = await self._fetch_shows()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Show catalogue refresh failed; keeping the current catalogue")
            return
        if not shows:
            logger.warning("Show catalogue refresh returned no shows; keeping the current catalogue")
            return
        self._catalog = ShowCatalog(shows)
        try:
            self._write_cache(shows)
        except OSError:
            # The new data is still served; the cache stays stale, so the next check refreshes again.
            logger.exception("Could not write the show cache to %s", self._cache_path)

    def _write_cache(self, shows: list[Show]) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._cache_path.with_suffix(".tmp")
        tmp_path.write_bytes(shows_adapter.dump_json(shows, by_alias=True))
        os.replace(tmp_path, self._cache_path)  # atomic, so a crash never leaves a half-written cache
        logger.info("Wrote %d shows to %s", len(shows), self._cache_path)
