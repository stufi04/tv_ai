import asyncio
from collections.abc import Sequence

from app.models import Episode, Show


class FakeEpisodeGenerator:
    """Deterministic stand-in for the LLM, so tests never hit the network."""

    def __init__(self) -> None:
        self.requests: list[list[str]] = []
        self.error: Exception | None = None
        # Seconds to wait before answering, to test what happens while a request is in flight.
        self.delay = 0.0

    async def generate(self, shows: Sequence[Show]) -> Episode:
        self.requests.append([show.id for show in shows])
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        titles = " x ".join(show.title for show in shows)
        return Episode(
            show_ids=[show.id for show in shows],
            title=f"{titles}: The Lost Episode",
            logline="Nothing is quite what it seems.",
            story="It started on a quiet Tuesday.\n\nBy Friday, nothing would ever be the same.",
        )
