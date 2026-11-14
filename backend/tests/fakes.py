from collections.abc import Sequence

from app.models import Episode, Show

# A 1x1 transparent PNG.
TINY_PNG_DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class FakeEpisodeGenerator:
    """Deterministic stand-in for Gemini, so tests never hit the network."""

    def __init__(self) -> None:
        self.requests: list[list[str]] = []
        self.error: Exception | None = None

    async def generate(self, shows: Sequence[Show]) -> Episode:
        self.requests.append([show.id for show in shows])
        if self.error:
            raise self.error
        titles = " x ".join(show.title for show in shows)
        return Episode(
            show_ids=[show.id for show in shows],
            title=f"{titles}: The Lost Episode",
            logline="Nothing is quite what it seems.",
            story="It started on a quiet Tuesday.\n\nBy Friday, nothing would ever be the same.",
            image_data_url=TINY_PNG_DATA_URL,
        )
