"""Downloads the TVmaze show index (https://www.tvmaze.com/api, data licensed CC BY-SA)."""

import asyncio
import html
import logging
import re
import time
from typing import Any

import httpx

from app.models import Show

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tvmaze.com"
USER_AGENT = "episode-generator (+https://www.tvmaze.com/api)"

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def clean_summary(raw: str | None) -> str:
    """TVmaze summaries are HTML fragments like "<p><b>Lost</b> follows ...</p>"."""
    if not raw:
        return ""
    return _WHITESPACE.sub(" ", html.unescape(_TAG.sub(" ", raw))).strip()


def to_show(raw: dict[str, Any]) -> Show | None:
    """Map a TVmaze show to our model, or None for shows not worth offering (no summary or no popularity)."""
    summary = clean_summary(raw.get("summary"))
    weight = raw.get("weight") or 0
    if not summary or weight <= 0 or not raw.get("name"):
        return None

    premiered = raw.get("premiered") or ""
    channel = raw.get("network") or raw.get("webChannel") or {}
    image = raw.get("image") or {}
    return Show(
        id=str(raw["id"]),
        title=raw["name"],
        year=int(premiered[:4]) if premiered[:4].isdigit() else None,
        network=channel.get("name"),
        genres=raw.get("genres") or [],
        summary=summary,
        image_url=image.get("medium"),
        popularity=weight,
    )


class _Pacer:
    """Spaces out request starts: TVmaze allows roughly 20 calls per 10 seconds per IP."""

    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self._interval
        if delay > 0:
            await asyncio.sleep(delay)


class TvmazeClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        request_interval: float = 0.5,
        concurrency: int = 4,
        max_attempts: int = 5,
        backoff: float = 2.0,
    ) -> None:
        self._http = http
        self._pacer = _Pacer(request_interval)
        self._concurrency = concurrency
        self._max_attempts = max_attempts
        self._backoff = backoff

    async def fetch_all_shows(self) -> list[Show]:
        """Fetch every page of /shows until TVmaze returns 404 (past the last page)."""
        pages: dict[int, list[Show]] = {}
        next_page = 0
        last_page: int | None = None

        async def worker() -> None:
            nonlocal next_page, last_page
            while True:
                page = next_page
                if last_page is not None and page > last_page:
                    return
                next_page += 1
                raw_shows = await self._fetch_page(page)
                if raw_shows is None:
                    last_page = page - 1 if last_page is None else min(last_page, page - 1)
                    return
                pages[page] = [show for raw in raw_shows if (show := to_show(raw)) is not None]
                if page % 25 == 0:
                    logger.info("TVmaze sync: fetched page %d", page)

        await asyncio.gather(*(worker() for _ in range(self._concurrency)))
        shows = [show for page in sorted(pages) for show in pages[page]]
        logger.info("TVmaze sync: %d pages, kept %d shows", len(pages), len(shows))
        return shows

    async def _fetch_page(self, page: int) -> list[dict[str, Any]] | None:
        for attempt in range(1, self._max_attempts + 1):
            await self._pacer.wait()
            try:
                response = await self._http.get("/shows", params={"page": page})
            except httpx.TransportError:
                if attempt == self._max_attempts:
                    raise
            else:
                if response.status_code == 404:
                    return None
                if response.status_code != 429 and response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                if attempt == self._max_attempts:
                    response.raise_for_status()
            await asyncio.sleep(self._backoff * attempt)
        raise AssertionError("unreachable")


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=30, headers={"User-Agent": USER_AGENT})
