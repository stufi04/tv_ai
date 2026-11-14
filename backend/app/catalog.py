from collections.abc import Iterable
from pathlib import Path

from pydantic import TypeAdapter

from app.models import Show

_shows_adapter = TypeAdapter(list[Show])


class UnknownShowError(LookupError):
    def __init__(self, show_ids: Iterable[str]) -> None:
        self.show_ids = list(show_ids)
        super().__init__(f"Unknown show id(s): {', '.join(self.show_ids)}")


class ShowCatalog:
    """Read-only, in-memory collection of TV shows."""

    def __init__(self, shows: Iterable[Show]) -> None:
        self._shows = {show.id: show for show in shows}

    @classmethod
    def from_json_file(cls, path: Path) -> "ShowCatalog":
        return cls(_shows_adapter.validate_json(path.read_bytes()))

    def all(self) -> list[Show]:
        return sorted(self._shows.values(), key=lambda show: show.title)

    def get_many(self, show_ids: Iterable[str]) -> list[Show]:
        show_ids = list(show_ids)
        missing = [show_id for show_id in show_ids if show_id not in self._shows]
        if missing:
            raise UnknownShowError(missing)
        return [self._shows[show_id] for show_id in show_ids]
